"""File and directory scanning for the DAP DB Manager.

This module handles scanning music directories and reading tag information
from audio files with support for parallel processing using multiprocessing
to bypass the GIL for CPU-intensive tag parsing.
"""

import os
from pathlib import Path
import sys
import logging
from typing import Optional, Callable, List, Any, Tuple, Dict, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from threading import Lock
from ..tagging.tag.formats import SUPPORTED_EXTENSIONS as audio_formats
from .cache import TagCache


def is_excluded_name(name: str) -> bool:
    """Return True for filesystem entries that must never be treated as audio.

    macOS writes an AppleDouble sidecar (``._<name>``) next to every file it
    modifies on filesystems without native xattr support (exFAT/FAT, which is
    what most removable media and portable players are formatted with). The
    sidecar keeps the original extension, so a suffix-only filter enqueues
    ``._track.mp3`` as if it were a track. It is not an audio stream, so the
    tag read fails and it is reported as a failed file.

    Excluding these by name is a deliberate divergence from Rockbox, which
    filters on suffix alone (``probe_file_format``) and lets the metadata
    parser reject the file afterwards. Both approaches produce the same
    database; skipping by name avoids opening and parsing a file that cannot
    possibly be audio, and keeps the failure count meaningful.

    ``__MACOSX`` is the archive-extraction equivalent and is excluded for the
    same reason.

    Args:
        name: A bare entry name (not a full path).

    Returns:
        True if the entry should be skipped entirely.
    """
    return name.startswith("._") or name == "__MACOSX"


def warn_no_tags():
    logging.warning(
        "Tagging support is disabled!\n"
        + "Please install the mutagen tag library.\n"
        + "(Available from http://code.google.com/p/mutagen/)"
    )


try:
    from .. import tagging
except ImportError:
    tagging = None  # type: ignore[assignment]
    warn_no_tags()


def myprint(*args, **kwargs):
    """Simple print wrapper for scanner callback functions.

    This is used as the default callback function for scanner functions
    that ask for a callback.
    """
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")

    sys.stdout.write(sep.join(str(a) for a in args) + end)


def read_single_file_tags(
    path: str,
) -> Tuple[str, Optional[int], Optional[int], Optional[Any]]:
    """Read tags from a single file (standalone function for multiprocessing).

    This function is defined at module level to be picklable for multiprocessing.

    Args:
        path: Path to the audio file

    Returns:
        Tuple of (path, size, mtime, tags) or (path, None, None, None) on error
    """
    try:
        # Import tagging here to avoid import issues in worker processes
        try:
            from dap_db_manager import tagging
        except ImportError:
            return (path, None, None, None)

        path_obj = Path(path)
        stat = path_obj.stat()
        size, mtime = stat.st_size, int(stat.st_mtime)

        # Check if file is in cache and unchanged
        # Note: Cache access from worker processes - they get a copy of the cache
        lowerpath = path.lower()
        if TagCache.contains(lowerpath):
            cached_size, cached_mtime = TagCache.get(lowerpath)[0]
            if mtime == cached_mtime and size == cached_size:
                # File unchanged, use cached tags
                cached_tags = TagCache.get(lowerpath)[1]
                return (path, size, mtime, cached_tags)

        # File is new or modified, read tags
        tags = tagging.read(path)
        if tags is None:
            return (path, None, None, None)
        return (path, size, mtime, tags)
    except Exception as e:
        logging.debug("Error reading tags from %s: %s", path, e)
        return (path, None, None, None)


class FileScanner:
    """Handles scanning and reading music files with multiprocessing support."""

    def __init__(
        self,
        max_workers: Optional[int] = None,
        use_multiprocessing: bool = True,
    ):
        """Initialize the file scanner.

        Args:
            max_workers: Maximum number of parallel workers for tag parsing.
                        If None, auto-detects based on CPU count.
            use_multiprocessing: Use ProcessPoolExecutor instead of ThreadPoolExecutor
                                to bypass GIL for CPU-bound tag parsing (default: True)
        """
        if max_workers is None:
            # For CPU-bound operations with multiprocessing, use CPU count
            # For I/O-bound operations with threading, use more workers
            if use_multiprocessing:
                max_workers = os.cpu_count() or 1
            else:
                max_workers = min(32, (os.cpu_count() or 1) + 4)

        self.max_workers = max_workers
        self.use_multiprocessing = use_multiprocessing
        self._lock = Lock()
        self.supported_extensions = {fmt.lower() for fmt in audio_formats}

        # Persistent executor pool - reused across operations for better performance
        # Use ProcessPoolExecutor for true parallelism (bypasses GIL)
        if use_multiprocessing:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            # Fallback to threading if multiprocessing not desired
            from concurrent.futures import ThreadPoolExecutor

            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)  # type: ignore[assignment]

        self._shutdown = False

    def _read_tags(self, path: str) -> Optional[Dict[str, Any]]:
        """Read tags from a single file.

        Args:
            path: Path to the audio file

        Returns:
            Dictionary of tags or None if reading failed
        """
        try:
            return tagging.read(path)
        except Exception as e:
            logging.debug("Failed to read tags from %s: %s", path, e)
            return None

    def add_file(
        self,
        file_path: str,
        paths_set: set,
        failed_list: list,
        callback: Optional[Callable] = myprint,
    ) -> None:
        """Add a single file to the database.

        Args:
            file_path: Path to the file to add
            paths_set: Set to add the file path to
            failed_list: List to add failed file paths to
            callback: Callback function for progress updates
        """
        if is_excluded_name(Path(file_path).name):
            logging.debug("Skipping macOS metadata sidecar: %s", file_path)
            return

        if Path(file_path).suffix.lower() not in self.supported_extensions:
            logging.debug("Skipping unsupported file format: %s", file_path)
            return

        path = str(file_path)
        if callback:
            callback(path)
        self._add_file_internal(file_path, paths_set, failed_list)

    def _add_file_internal(
        self,
        path: str,
        paths_set: set,
        failed_list: list,
        size: Optional[int] = None,
        mtime: Optional[int] = None,
        tags: Optional[Any] = None,
    ) -> None:
        """Internal method to add a file to the cache and paths set.

        Args:
            path: File path
            paths_set: Set to add the file path to
            failed_list: List to add failed file paths to
            size: Optional file size (read if not provided)
            mtime: Optional modification time (read if not provided)
            tags: Optional pre-read tags (read if not provided)
        """
        # Use absolute path but don't resolve() to preserve case from filesystem
        path_obj = Path(path).absolute()
        absolute_path = str(path_obj)
        lowerpath = absolute_path.lower()

        if size is None or mtime is None:
            stat = path_obj.stat()
            size, mtime = stat.st_size, int(stat.st_mtime)

        try:
            cached_size, cached_mtime = TagCache.get(lowerpath)[0]
            # Move to end for LRU (mark as recently used)
            TagCache.move_to_end(lowerpath)
        except (KeyError, TypeError):
            if tags is None:
                try:
                    tags = tagging.read(absolute_path)
                except Exception as e:
                    # Catch any tag reading errors (corrupted files, unsupported formats, etc.)
                    logging.debug("Failed to read tags from %s: %s", absolute_path, e)
                    tags = None
            if tags is None:
                failed_list.append(absolute_path)
                return
            # Store minimal tags to reduce memory usage
            minimal_tags = TagCache.extract_essential_tags(tags)
            TagCache.set(lowerpath, ((size, mtime), minimal_tags))
        else:
            if mtime > cached_mtime:
                # Store minimal tags to reduce memory usage
                minimal_tags = (
                    TagCache.extract_essential_tags(tags)
                    if tags is not None
                    else TagCache.get(lowerpath)[1]
                )
                TagCache.set(lowerpath, ((size, mtime), minimal_tags))
                # Move to end after update
                TagCache.move_to_end(lowerpath)

        # Add ABSOLUTE path to paths_set (normalization happens in generator during _prepare_entry_data)
        # Cache uses lowercase absolute paths as keys, so paths_set must also use absolute paths
        paths_set.add(absolute_path)

    def add_files(
        self,
        files: Sequence[str],
        paths_set: set,
        failed_list: list,
        callback: Optional[Callable] = myprint,
        use_parallel: bool = True,
    ) -> None:
        """Add a list of files with tag parsing.

        Args:
            files: Sequence of file paths to add
            paths_set: Set to add the file paths to
            failed_list: List to add failed file paths to
            callback: Callback function for progress updates
            use_parallel: Whether to use parallel processing for large batches
        """
        batch_size = 100
        # Filter files first to remove excluded or unsupported files
        valid_files: List[str] = []
        for file in files:
            file_str = str(file)
            if is_excluded_name(Path(file_str).name):
                logging.debug("Skipping macOS metadata sidecar: %s", file_str)
                continue
            if Path(file_str).suffix.lower() not in self.supported_extensions:
                logging.debug("Skipping unsupported file format: %s", file_str)
                continue
            valid_files.append(file_str)

        total_files = len(valid_files)
        if total_files == 0:
            return

        if use_parallel and total_files > batch_size:
            file_count = 0
            for i in range(0, total_files, batch_size):
                batch = valid_files[i : i + batch_size]
                results = self.read_tags_batch(batch)

                with self._lock:
                    for path, size, mtime, tags in results:
                        if size is not None and tags is not None:
                            self._add_file_internal(
                                path, paths_set, failed_list, size, mtime, tags
                            )
                            file_count += 1
                        else:
                            failed_list.append(path)

                processed = min(i + batch_size, total_files)
                if callback:
                    callback(f"Processing files... {processed}/{total_files}")
        else:
            file_count = 0
            for file_path in valid_files:
                self._add_file_internal(file_path, paths_set, failed_list)
                file_count += 1

                if callback and file_count % batch_size == 0:
                    callback(f"Processing files... {file_count}/{total_files}")

            if callback and total_files % batch_size != 0:
                callback(f"Processing files... {total_files}/{total_files}")

    def read_tags_batch(
        self, file_paths: List[str]
    ) -> List[Tuple[str, Optional[int], Optional[int], Optional[Any]]]:
        """Read tags from multiple files in parallel using multiprocessing.

        Returns list of (path, size, mtime, tags) tuples.
        Uses ProcessPoolExecutor by default to bypass GIL for CPU-intensive tag parsing.
        Optimized to skip reading tags if file is unchanged in cache.

        Args:
            file_paths: List of file paths to read

        Returns:
            List of tuples containing (path, size, mtime, tags)
        """
        results = []

        # Use persistent executor (ProcessPoolExecutor or ThreadPoolExecutor)
        if self._shutdown:
            # Pool has been shut down, return empty results
            return []

        # Submit all tasks to the process pool
        futures = {
            self._executor.submit(read_single_file_tags, path): path
            for path in file_paths
        }

        # Collect results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                # Include all results, even failed ones (size=None means failed)
                results.append(result)
            except Exception as e:
                # Handle any exceptions from worker processes
                path = futures[future]
                logging.error("Error processing %s: %s", path, e)
                results.append((path, None, None, None))

        return results

    def scan_dir_metadata(
        self,
        path: str,
        recursive: bool = True,
        dircallback: Optional[Callable[..., Any]] = None,
    ) -> dict[str, tuple[int, float]]:
        """Collect file paths, sizes, and modification times without parsing tags.

        Uses os.scandir for high-performance directory traversal.

        Args:
            path: Directory path to scan
            recursive: Whether to scan recursively (default: True)
            dircallback: Optional callback for each visited directory

        Returns:
            Dictionary mapping absolute file path to (size, mtime) tuple.
        """

        def blank(*args: Any, **kwargs: Any) -> None:
            pass

        if not dircallback:
            dircallback = blank

        original_root = str(path)
        metadata: Dict[str, Tuple[int, float]] = {}

        def scan_directory(dir_path: str) -> None:
            try:
                with os.scandir(dir_path) as entries:
                    dirs_to_scan = []
                    for entry in entries:
                        try:
                            if is_excluded_name(entry.name):
                                # AppleDouble sidecar or __MACOSX dir - never
                                # descend into it, never enqueue it.
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                dirs_to_scan.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                # Check extension using entry name (no extra syscall)
                                if (
                                    Path(entry.name).suffix.lower()
                                    in self.supported_extensions
                                ):
                                    stat_info = entry.stat(follow_symlinks=False)
                                    abs_path = str(Path(entry.path).absolute())
                                    metadata[abs_path] = (
                                        stat_info.st_size,
                                        stat_info.st_mtime,
                                    )
                        except OSError:
                            # Skip files/dirs we can't access
                            continue

                    # Recurse into subdirectories if needed
                    if recursive:
                        for subdir in sorted(dirs_to_scan):
                            dircallback(subdir)
                            scan_directory(subdir)

            except OSError as e:
                logging.warning("Cannot access directory %s: %s", dir_path, e)

        # Start scanning from root
        dircallback(original_root)
        scan_directory(original_root)
        return metadata

    def add_dir(
        self,
        path: str,
        paths_set: set[str],
        failed_list: list[str],
        recursive: bool = True,
        use_parallel: bool = True,
        dircallback: Optional[Callable[..., Any]] = myprint,
        filecallback: Optional[Callable[..., Any]] = None,
        estimatecallback: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Add a directory (recursively by default) with optional parallel processing.

        Args:
            path: Directory path to scan
            paths_set: Set to add file paths to
            failed_list: List to add failed file paths to
            recursive: Whether to scan recursively (default: True)
            use_parallel: Whether to use parallel processing
            dircallback: Callback function called for each directory
            filecallback: Callback function called for each file
            estimatecallback: Callback function for progress estimation
        """
        metadata = self.scan_dir_metadata(
            path, recursive=recursive, dircallback=dircallback
        )
        all_files = sorted(metadata.keys())

        if estimatecallback:
            estimatecallback(len(all_files))

        self.add_files(
            all_files,
            paths_set=paths_set,
            failed_list=failed_list,
            callback=filecallback,
            use_parallel=use_parallel,
        )

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the persistent executor pool (ProcessPoolExecutor or ThreadPoolExecutor).

        Args:
            wait: If True, wait for all pending tasks to complete before shutting down
        """
        if not self._shutdown:
            self._shutdown = True
            if self._executor:
                self._executor.shutdown(wait=wait)

    def __del__(self):
        """Cleanup thread pool on object destruction."""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass  # Ignore errors during cleanup

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - shutdown pool."""
        self.shutdown(wait=True)
        return False
