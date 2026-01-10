"""Database generation logic for Rockbox Database Manager.

This module handles generating the Rockbox database structure from cached
music file tags with support for parallel processing.
"""

import os
import gc
import sys
from itertools import product
from typing import Optional, Callable, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging

try:
    from ..tagging import titleformat
except ImportError:
    titleformat = None  # type: ignore[assignment]

from ..constants import FILE_TAGS, EMBEDDED_TAGS, FLAG_TRKNUMGEN
from ..utils import mtime_to_fat
from ..tagging.tag.tagfile import TagEntry
from ..indexfile import IndexEntry
from .cache import TagCache


def myprint(*args, **kwargs):
    """Simple print wrapper for generator callback functions."""
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")

    sys.stdout.write(sep.join(str(a) for a in args) + end)


class DatabaseGenerator:
    """Handles database generation from cached tags with parallel processing."""

    def __init__(
        self,
        max_workers: Optional[int] = None,
        ipod_root: Optional[str] = None,
        mount_notation: Optional[str] = None,
    ):
        """Initialize the database generator.

        Args:
            max_workers: Maximum number of parallel workers.
                        If None, auto-detects based on CPU count (recommended).
            ipod_root: Optional iPod mount point for path translation.
                      When set, strips this prefix from file paths to create iPod-relative paths.
                      Example: ipod_root="/Volumes/IPOD" converts "/Volumes/IPOD/Music/Song.mp3"
                      to "/Music/Song.mp3" in the database.
            mount_notation: Optional Rockbox mount notation to prepend to paths.
                           Example: "/<HDD0>" prepends "/<HDD0>" to all paths.
                           Typically auto-detected from existing database via detect-mounts command.
        """
        if max_workers is None:
            # For mixed I/O and CPU-bound operations, use moderate worker count
            # Formula: min(32, (cpu_count or 1) + 4)
            max_workers = min(32, (os.cpu_count() or 1) + 4)
        self.max_workers = max_workers
        self.ipod_root = self._normalize_ipod_root(ipod_root)
        self.mount_notation = mount_notation.rstrip("/") if mount_notation else ""
        self._lock = Lock()

        # Persistent thread pool - reused across operations for better performance
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._shutdown = False

    @staticmethod
    def _normalize_ipod_root(ipod_root: Optional[str]) -> Optional[str]:
        """Normalize the iPod root path for consistent path translation.

        Args:
            ipod_root: Raw iPod root path (e.g., "/Volumes/IPOD", "E:", "E:\\")

        Returns:
            Normalized path with trailing slash removed, or None if ipod_root is None
        """
        if ipod_root is None:
            return None

        # Convert to string and normalize
        root = str(ipod_root).rstrip("/").rstrip("\\")

        # Ensure it's an absolute path or drive letter
        if not root:
            return None

        return root

    def generate(
        self,
        paths: set,
        formats: Dict[str, Tuple],
        tagfiles: dict,
        index,
        use_parallel: bool = True,
        callback: Optional[Callable] = myprint,
        preserve_existing: bool = False,
    ) -> Dict[str, TagEntry]:
        """Generate the database from cached tags.

        Args:
            paths: Set of file paths to process
            formats: Dictionary of format strings for each field
            tagfiles: Dictionary of TagFile objects
            index: IndexFile object to populate
            use_parallel: Whether to use parallel processing
            callback: Progress callback function
            preserve_existing: If True, don't clear existing entries (for updates)

        Returns:
            Dictionary of multiple_fields with blank TagEntry values
        """
        compiled_formats = {}
        multiple_fields = {}

        for field, (format, sort) in formats.items():
            if format.is_multiple:
                multiple_fields[field] = TagEntry("<BLANK>")
            format = titleformat.compile(f"$if2({format.to_string()},'<Untagged>')")
            if sort is not None:
                sort = titleformat.compile(
                    f"$if2({sort.to_string()},{format.to_string()})"
                )
            compiled_formats[field] = (format, sort)

        # Standard formats (compiled once and reused for all files)
        compiled_formats["date"] = titleformat.compile("$if2(%date%,0)")
        compiled_formats["discnumber"] = titleformat.compile("$if2(%discnumber%,0)")
        compiled_formats["tracknumber"] = titleformat.compile("$if2(%tracknumber%,0)")
        compiled_formats["bitrate"] = titleformat.compile("$if2(%bitrate%,0)")

        # Batch progress updates to reduce callback overhead
        batch_size = 100  # Update every 100 paths
        total_paths = len(paths)
        sorted_paths = sorted(paths)

        # Choose processing strategy based on dataset size and parallel flag
        if use_parallel and total_paths > 1000:
            self._generate_parallel(
                sorted_paths,
                compiled_formats,
                tagfiles,
                index,
                multiple_fields,
                callback,
                batch_size,
            )
        else:
            self._generate_sequential(
                sorted_paths,
                compiled_formats,
                tagfiles,
                index,
                multiple_fields,
                callback,
                batch_size,
            )

        # Final progress update
        if callback:
            callback(total_paths, total_paths)

        for field in FILE_TAGS:
            tagfiles[field].sort()

        # Clean up cache after generation to free memory
        TagCache.cleanup(keep_paths=paths)

        # Force garbage collection to free memory immediately
        gc.collect()

        return multiple_fields

    def _generate_sequential(
        self,
        sorted_paths,
        formats,
        tagfiles,
        index,
        multiple_fields,
        callback,
        batch_size,
    ):
        """Sequential database generation (optimized logic)."""
        total_paths = len(sorted_paths)
        cache = TagCache.get_cache()

        for i, path in enumerate(sorted_paths, 1):
            # Cache uses lowercase keys for case-insensitive lookups
            lowerpath = path.lower()
            (size, mtime), tags = cache[lowerpath]

            # Path translation for cross-compilation
            # When building on a laptop for an iPod, we need to translate paths
            if self.ipod_root:
                # Normalize path for comparison (handle backslashes)
                normalized_path = path.replace("\\", "/")
                normalized_root = self.ipod_root.replace("\\", "/")

                # Strip the iPod mount point prefix
                if normalized_path.startswith(normalized_root):
                    clean_path = normalized_path[len(normalized_root) :]
                    # Ensure path starts with /
                    if not clean_path.startswith("/"):
                        clean_path = "/" + clean_path

                    # Prepend mount notation if specified
                    if self.mount_notation:
                        clean_path = self.mount_notation + clean_path
                else:
                    # Path doesn't start with ipod_root - log warning and skip
                    logging.warning(
                        "File path '%s' does not start with ipod_root '%s'. Skipping.",
                        path,
                        self.ipod_root,
                    )
                    continue
            else:
                # No ipod_root specified - use original path processing
                # Remove drive letter and convert to Unix-style path for Rockbox
                from pathlib import PureWindowsPath, PurePosixPath

                path_obj = PureWindowsPath(path) if ":" in path else PurePosixPath(path)
                # Get path without drive (anchor) and convert to POSIX
                clean_path = str(
                    PurePosixPath(
                        *path_obj.parts[1:] if path_obj.anchor else path_obj.parts
                    )
                )
                if not clean_path.startswith("/"):
                    clean_path = "/" + clean_path

                # Prepend mount notation if specified
                if self.mount_notation:
                    clean_path = self.mount_notation + clean_path

            if callback and i % batch_size == 0:
                callback(i, total_paths)

            self._process_entry(
                {"path": clean_path, "mtime": mtime, "tags": tags},
                formats,
                tagfiles,
                index,
                multiple_fields,
            )

    def _generate_parallel(
        self,
        sorted_paths,
        formats,
        tagfiles,
        index,
        multiple_fields,
        callback,
        batch_size,
    ):
        """Parallel database generation using thread pool.

        Note: Due to titleformat objects and GIL, we use threading to process
        batches in parallel while maintaining thread-safe access to shared data.
        """
        total_paths = len(sorted_paths)
        processed = 0
        cache = TagCache.get_cache()

        def process_batch(paths_batch):
            """Process a batch of paths and return intermediate results."""
            batch_results = []
            for path in paths_batch:
                try:
                    # Cache uses lowercase keys for case-insensitive lookups
                    lowerpath = path.lower()
                    (size, mtime), tags = cache[lowerpath]
                except KeyError:
                    # File not in cache - skip it (should not happen if cache is up to date)
                    # This occurs when scanning a folder that wasn't included in the tag cache
                    logging.warning("File not in cache, skipping: %s", path)
                    continue

                try:
                    # Path translation for cross-compilation
                    # When building on a laptop for an iPod, we need to translate paths:
                    # - On laptop: /Volumes/IPOD/Music/Song.mp3
                    # - In database: /Music/Song.mp3 (iPod-relative)

                    if self.ipod_root:
                        # Normalize path for comparison (handle backslashes)
                        normalized_path = path.replace("\\", "/")
                        normalized_root = self.ipod_root.replace("\\", "/")

                        # Strip the iPod mount point prefix
                        if normalized_path.startswith(normalized_root):
                            # Remove the mount point prefix
                            clean_path = normalized_path[len(normalized_root) :]
                            # Ensure path starts with /
                            if not clean_path.startswith("/"):
                                clean_path = "/" + clean_path
                        else:
                            # Path doesn't start with ipod_root - log warning and skip
                            logging.warning(
                                "File path '%s' does not start with ipod_root '%s'. Skipping.",
                                path,
                                self.ipod_root,
                            )
                            continue
                    else:
                        # No ipod_root specified - use original path processing
                        # Remove drive letter and convert to Unix-style path for Rockbox
                        # Use pathlib to handle path components, then convert to Unix-style
                        from pathlib import PureWindowsPath, PurePosixPath

                        path_obj = (
                            PureWindowsPath(path)
                            if ":" in path
                            else PurePosixPath(path)
                        )
                        # Get path without drive (anchor) and convert to POSIX
                        clean_path = str(
                            PurePosixPath(
                                *path_obj.parts[1:]
                                if path_obj.anchor
                                else path_obj.parts
                            )
                        )
                        if not clean_path.startswith("/"):
                            clean_path = "/" + clean_path

                    # Prepend mount notation if specified
                    if self.mount_notation:
                        clean_path = self.mount_notation + clean_path

                    # Create entry data
                    entry_data = {"path": clean_path, "mtime": mtime, "tags": tags}
                    batch_results.append(entry_data)
                except Exception as e:
                    # Skip problematic entries but log the error
                    logging.debug(
                        "Skipped entry %s due to processing error: %s", path, e
                    )
                    pass
            return batch_results

        # Split into batches for parallel processing
        batches = [
            sorted_paths[i : i + batch_size] for i in range(0, total_paths, batch_size)
        ]

        # Process batches with persistent thread pool
        if self._shutdown:
            # Pool has been shut down, fall back to sequential processing
            logging.warning(
                "Thread pool shut down, falling back to sequential processing"
            )
            self._generate_sequential(
                sorted_paths,
                formats,
                tagfiles,
                index,
                multiple_fields,
                callback,
                batch_size,
            )
            return

        futures = {
            self._executor.submit(process_batch, batch): batch for batch in batches
        }

        for future in as_completed(futures):
            batch_results = future.result()

            # Process results sequentially to maintain data structure integrity
            with self._lock:
                for entry_data in batch_results:
                    self._process_entry(
                        entry_data, formats, tagfiles, index, multiple_fields
                    )
                    processed += 1

            if callback:
                callback(processed, total_paths)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the persistent thread pool.

        Args:
            wait: If True, wait for all pending tasks to complete before shutting down
        """
        if not self._shutdown:
            self._shutdown = True
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

    def _process_entry(
        self,
        entry_data: dict,
        formats: dict,
        tagfiles: dict,
        index,
        multiple_fields: dict,
    ) -> None:
        """Process a single entry for database generation.

        Args:
            entry_data: Dictionary with 'path', 'mtime', and 'tags'
            formats: Compiled format strings
            tagfiles: TagFile objects
            index: IndexFile object
            multiple_fields: Dictionary of fields with multiple values
        """
        path = entry_data["path"]
        mtime = entry_data["mtime"]
        tags = entry_data["tags"]

        entry = IndexEntry()

        entry.path = TagEntry(path, is_path=True)
        entry.path.index = index.count
        tagfiles["path"].append(entry.path)

        try:
            entry.title = TagEntry(tags["title"][0])
        except KeyError:
            entry.title = TagEntry("<Untagged>")
        entry.title.index = index.count
        tagfiles["title"].append(entry.title)

        entry.mtime = mtime_to_fat(mtime)
        # Length is milliseconds
        entry.length = int(tags["length"][0] * 1000)

        # Initialize flag field (cleared by IndexEntry.__init__)
        entry.flag = 0

        # Handle track number - if missing or < 0, set FLAG_TRKNUMGEN
        # (Matches Rockbox logic from add_tagcache() in tagcache.c)
        try:
            tracknumber = int(tags.get("tracknumber", [0])[0])
            if tracknumber < 0:
                entry.tracknumber = 0
                entry.set_flag(FLAG_TRKNUMGEN)
            else:
                entry.tracknumber = tracknumber
        except (ValueError, TypeError, IndexError):
            entry.tracknumber = 0
            entry.set_flag(FLAG_TRKNUMGEN)

        # Process other numeric embedded tags
        for field in EMBEDDED_TAGS:
            if field in ("tracknumber", "flag", "mtime", "length"):
                continue  # Already handled above

            try:
                formatted_value = str(formats[field].format(tags))
                formatted_value = formatted_value.strip()
                if formatted_value and formatted_value not in (
                    "True",
                    "False",
                    "<Untagged>",
                ):
                    entry[field] = int(formatted_value)
                else:
                    entry[field] = 0
            except (KeyError, ValueError, AttributeError):
                entry[field] = 0

        multiple_tags = {}
        for field, blank_tag in multiple_fields.items():
            multiple_tags[field] = [blank_tag]

        # Handle artist, albumartist, and canonicalartist
        # (Matches Rockbox logic from add_tagcache())
        has_artist = False
        artist_value = None
        albumartist_value = None

        for field in FILE_TAGS:
            try:
                fmt, sort = formats[field]
            except KeyError:
                continue

            # Special handling for canonicalartist
            if field == "canonicalartist":
                # canonicalartist = artist if artist exists, else albumartist
                # This matches Rockbox: ADD_TAG(entry, tag_virt_canonicalartist, &id3.artist) or &id3.albumartist
                if has_artist and artist_value:
                    value = artist_value
                else:
                    # Fall back to album artist
                    value = albumartist_value if albumartist_value else "<Untagged>"

                try:
                    tagentry = tagfiles[field][value]
                except KeyError:
                    tagentry = TagEntry(value)
                    if sort is not None:
                        tagentry.sort = (
                            sort.format(tags)
                            if has_artist
                            else (albumartist_value or "<Untagged>")
                        )
                    tagfiles[field].append(tagentry)
                entry[field] = tagentry
                continue

            # Store artist and albumartist for canonicalartist logic
            if field == "artist":
                artist_value = fmt.format(tags)
                has_artist = bool(
                    artist_value
                    and artist_value.strip()
                    and artist_value != "<Untagged>"
                )
            elif field == "album artist":
                albumartist_value = fmt.format(tags)

            # Special handling for grouping field
            # (Matches Rockbox: if has_grouping then id3.grouping else id3.title)
            if field == "grouping":
                grouping_value = fmt.format(tags)
                has_grouping = bool(
                    grouping_value
                    and grouping_value.strip()
                    and grouping_value != "<Untagged>"
                )
                if not has_grouping:
                    # Fall back to title
                    try:
                        value = tags["title"][0]
                    except (KeyError, IndexError):
                        value = "<Untagged>"
                else:
                    value = grouping_value

                try:
                    tagentry = tagfiles[field][value]
                except KeyError:
                    tagentry = TagEntry(value)
                    if sort is not None:
                        tagentry.sort = sort.format(tags) if has_grouping else value
                    tagfiles[field].append(tagentry)
                entry[field] = tagentry
                continue

            # Normal field processing
            if field not in multiple_tags:
                value = fmt.format(tags)
                try:
                    tagentry = tagfiles[field][value]
                except KeyError:
                    tagentry = TagEntry(value)
                    if sort is not None:
                        tagentry.sort = sort.format(tags)
                    tagfiles[field].append(tagentry)
                entry[field] = tagentry
            else:
                if sort is not None:
                    sort = sort.format(tags)
                    if not isinstance(sort, (tuple, list)):
                        sort = [sort]
                else:
                    sort = [None]
                data = fmt.format(tags)
                if not isinstance(data, (tuple, list)):
                    data = [data]

                for v, s in zip(data, sort):
                    multiple_tags[field].append(TagEntry(v, s))

        # Make all combinations of the IndexEntry
        combinations = []
        for field, tagentries in multiple_tags.items():
            combinations.append([(field, tagentry) for tagentry in tagentries])

        for fields in product(*combinations):
            index_entry = entry.copy()
            for field, value in fields:
                # Make sure the TagEntry is present in the TagFile
                try:
                    tagentry = tagfiles[field][value.key]
                except KeyError:
                    tagentry = value
                    tagfiles[field].append(tagentry)
                index_entry[field] = tagentry
            index.append(index_entry)
