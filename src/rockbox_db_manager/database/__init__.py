"""Rockbox Database Manager - Core Database class.

This package provides the main Database class and supporting components.
The original large database.py file has been refactored into focused modules:

Modules:
    cache.py: Tag caching for improved performance (TagCache class)
    file_scanner.py: File and directory scanning (FileScanner class)
    generator.py: Database generation logic (DatabaseGenerator class)
    io.py: Database read/write operations (DatabaseIO class)

The Database class coordinates all these components to provide a high-level
interface for creating and managing Rockbox database files.
"""

import multiprocessing
from typing import Optional, Callable, List
import logging

from ..constants import FORMATTED_TAGS, FILE_TAGS, FLAG_DELETED
from ..tagging.tag.tagfile import TagFile
from ..indexfile import IndexFile
from ..config import Config

from .cache import TagCache
from .file_scanner import FileScanner, myprint
from .generator import DatabaseGenerator
from .io import DatabaseIO


def warn_no_tags():
    """Warn when tagging support is unavailable."""
    logging.warning(
        "Tagging support is disabled!\n"
        + "Please install the mutagen tag library.\n"
        + "(Available from https://github.com/quodlibet/mutagen)"
    )


try:
    from .. import tagging
    from ..tagging import titleformat
except ImportError:
    warn_no_tags()
    tagging = None  # type: ignore[assignment]
    titleformat = None  # type: ignore[assignment]


class Database:
    """Main Database class for Rockbox Database Manager.

    This class coordinates tag caching, file scanning, database generation,
    and I/O operations. It provides a high-level interface for creating and
    managing Rockbox database files.
    """

    def __init__(
        self, config: Optional[Config] = None, ipod_root: Optional[str] = None
    ):
        """Initialize a new Database instance.

        Args:
            config: Optional Config object. If None, loads default config.
            ipod_root: Optional iPod mount point for cross-compilation.
                      When set, paths are translated from laptop paths to iPod-relative paths.
                      Example: ipod_root="/Volumes/IPOD" converts "/Volumes/IPOD/Music/Song.mp3"
                      to "/Music/Song.mp3" in the database.
        """
        # Load or use provided config
        self.config = config if config is not None else Config()
        self.ipod_root = ipod_root

        # Get mount notation from config (auto-detected via detect-mounts command)
        mount_notation = self.config.get_mount_notation()

        # Set database version from config BEFORE calling clear()
        db_version = self.config.get_database_version()
        if db_version == 16:
            self.db_magic = 1413695504  # 0x54434810
        else:
            # Default to version 16 for invalid values
            self.db_magic = 1413695504
            print(f"Warning: Invalid database version {db_version}, using version 16")

        # Now initialize the database structures
        self.clear()
        self.formats: dict[str, tuple] = {}

        # Files added to *this* instance
        self.paths: set[str] = set()
        self.failed: list[str] = []

        # Parallelization configuration
        # Auto-detect optimal worker count based on CPU count (I/O-bound workload)
        # Formula: min(32, cpu_count + 4) allows for efficient I/O concurrency
        cpu_count = multiprocessing.cpu_count()
        self.max_workers = min(32, cpu_count + 4)
        self.use_parallel = True  # Can be toggled via parameters

        # Initialize scanner and generator with configured workers and ipod_root
        self._scanner = FileScanner(max_workers=self.max_workers)
        self._generator = DatabaseGenerator(
            max_workers=self.max_workers,
            ipod_root=ipod_root,
            mount_notation=mount_notation,
        )

        # Set default formats
        for field in FORMATTED_TAGS:
            self.set_format(field, "%" + field + "%")
        # canonicalartist defaults to artist (will fallback to albumartist if artist is empty)
        self.set_format("canonicalartist", "%artist%")
        # grouping defaults to itself (will fallback to title if grouping is empty)
        self.set_format("grouping", "%grouping%")

    def clear(self):
        """Clear the database tagfiles and index."""
        # Create tagfiles and index
        self.tagfiles = dict((field, TagFile()) for field in FILE_TAGS)
        self.index = IndexFile(tagfiles=self.tagfiles)

        # Set magic version if already configured (use __dict__ to avoid __getattr__)
        if "db_magic" in self.__dict__:
            for tagfile in self.tagfiles.values():
                tagfile.magic = self.db_magic
            self.index.magic = self.db_magic

        self.multiple_fields = {}

    def set_format(self, field: str, format: str, sortformat: Optional[str] = None):
        """Set the format and the sorting format for a field.

        field must be present in FORMATTED_TAGS. This function will attempt to
        compile the titleformat strings and will raise an exception if they do
        not correctly compile.

        Args:
            field: Field name from FORMATTED_TAGS
            format: Format string for the field
            sortformat: Optional sort format string
        """
        assert field in FORMATTED_TAGS
        self.formats[field] = (
            titleformat.compile(format),
            titleformat.compile(sortformat) if sortformat is not None else None,
        )

    def __getattr__(self, key):
        """Allow access to self.tagfiles[field] via self.field."""
        return self.tagfiles[key]

    def __getitem__(self, key):
        """Allow access to self.tagfiles[field] via self[field]."""
        if key == "index":
            return self.index
        else:
            return self.tagfiles[key]

    # ---------------------------------------------------------------------------
    # Tag cache operations (delegated to TagCache)
    # ---------------------------------------------------------------------------

    @staticmethod
    def _extract_essential_tags(tag_obj):
        """Extract only essential fields from a Tag object to minimize cache size."""
        return TagCache.extract_essential_tags(tag_obj)

    @staticmethod
    def _restore_tag_dict(tag_dict):
        """Convert minimal tag dictionary back to a format compatible with database generation."""
        return TagCache.restore_tag_dict(tag_dict)

    def load_tags(self, path: str, callback: Optional[Callable] = None):
        """Update paths and tag_cache from a pickled file.

        Args:
            path: Path to the pickled tags file
            callback: Optional callback for progress updates
        """
        TagCache.load(path, self.paths, callback)

    def save_tags(self, path: str, callback: Optional[Callable] = None) -> tuple:
        """Save tags in self.paths to a compressed pickled file.

        Args:
            path: Path to save the pickled tags file
            callback: Optional callback for progress updates

        Returns:
            Tuple of (actual_path_used, number_of_entries_saved)
        """
        return TagCache.save(path, self.paths, callback)

    @classmethod
    def cleanup_cache(cls, keep_paths: Optional[set] = None):
        """Remove unused entries from the shared tag_cache to free memory.

        Args:
            keep_paths: Optional set of paths to keep
        """
        TagCache.cleanup(keep_paths)

    @classmethod
    def _trim_cache(cls):
        """Trim cache to prevent unbounded growth."""
        TagCache.trim()

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown persistent executor pools to free resources.

        Args:
            wait: If True, wait for all pending tasks to complete
        """
        if hasattr(self, "_scanner"):
            self._scanner.shutdown(wait=wait)
        if hasattr(self, "_generator"):
            self._generator.shutdown(wait=wait)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - shutdown executor pools."""
        self.shutdown(wait=True)
        return False

    def __del__(self):
        """Cleanup executor pools on object destruction."""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass  # Ignore errors during cleanup

    # ---------------------------------------------------------------------------
    # File operations (delegated to FileScanner)
    # ---------------------------------------------------------------------------

    def add_file(self, file: str, callback: Callable = myprint) -> None:
        """Add a file and update the tag_cache.

        Args:
            file: Path to the file to add
            callback: Callback function for progress updates
        """
        self._scanner.add_file(file, self.paths, self.failed, callback)

    def add_files(self, files: List[str], callback: Callable = myprint) -> None:
        """Add a list of files.

        Args:
            files: List of file paths to add
            callback: Callback function for progress updates
        """
        self._scanner.add_files(files, self.paths, self.failed, callback)

    def add_dir(
        self,
        path: str,
        recursive: bool = True,
        dircallback: Optional[Callable] = myprint,
        filecallback: Optional[Callable] = None,
        estimatecallback: Optional[Callable] = None,
        parallel: Optional[bool] = None,
    ) -> None:
        """Add a directory (recursively by default) with optional parallel processing.

        Args:
            path: Directory path to scan
            recursive: Whether to scan recursively (default: True)
            dircallback: Callback function called for each directory
            filecallback: Callback function called for each file
            estimatecallback: Callback function for progress estimation
            parallel: Override parallel processing (default: uses self.use_parallel)
        """
        use_parallel = parallel if parallel is not None else self.use_parallel
        self._scanner.add_dir(
            path,
            self.paths,
            self.failed,
            recursive,
            use_parallel,
            dircallback,
            filecallback,
            estimatecallback,
        )

    # ---------------------------------------------------------------------------
    # Database generation (delegated to DatabaseGenerator)
    # ---------------------------------------------------------------------------

    def generate_database(
        self, callback: Callable = myprint, parallel: Optional[bool] = None
    ):
        """Generate the database from files or dirs that have been added.

        This creates an IndexFile and TagFiles for each formatted field.
        Use write() to write the database to files.

        Args:
            callback: Progress callback function
            parallel: Override parallel processing (default: uses self.use_parallel)
        """
        use_parallel = parallel if parallel is not None else self.use_parallel
        self.clear()

        self.multiple_fields = self._generator.generate(
            self.paths, self.formats, self.tagfiles, self.index, use_parallel, callback
        )

    def update_database(
        self,
        music_dir: str,
        callback: Callable = myprint,
        parallel: Optional[bool] = None,
    ) -> dict:
        """Update database with new/deleted files (delta update).

        Similar to Rockbox's Q_UPDATE:
        - Scans for new files not in the database
        - Detects renamed/moved files to preserve statistics
        - Marks missing files with FLAG_DELETED
        - Preserves existing entries and statistics (playcount, rating, etc.)
        - Faster than full rebuild

        Args:
            music_dir: Directory to scan for music files
            callback: Progress callback function
            parallel: Override parallel processing (default: uses self.use_parallel)

        Returns:
            Dictionary with statistics:
                - added: Number of new files added
                - renamed: Number of files renamed/moved (statistics preserved)
                - deleted: Number of files marked as deleted
                - unchanged: Number of existing entries preserved
                - failed: Number of files that failed to process
        """
        use_parallel = parallel if parallel is not None else self.use_parallel

        # Build a set of existing file paths (normalized)
        existing_paths = set()
        for entry in self.index.entries:
            if not entry.is_deleted():
                # entry["path"] is already a TagEntry with .data attribute
                existing_paths.add(entry["path"].data.lower())

        # Scan for all current files in music directory
        callback("Scanning music directory...")
        self._scanner.add_dir(
            music_dir,
            paths_set=self.paths,
            failed_list=self.failed,
            recursive=True,
            use_parallel=use_parallel,
            # Don't show per-directory callbacks during scan - too verbose and no total count
            dircallback=None,
        )
        callback(
            f"Scan complete: found {len(self.paths)} files ({len(self.failed)} failed)"
        )

        # Normalize new paths for comparison
        new_paths = {p.lower() for p in self.paths}

        # Determine which files to add (not in database)
        paths_to_add = new_paths - existing_paths

        # Determine which files to mark as deleted (in database but not on disk)
        paths_to_delete = existing_paths - new_paths

        # Count existing active and deleted entries before update
        initial_active = sum(1 for e in self.index.entries if not e.is_deleted())
        initial_deleted = sum(1 for e in self.index.entries if e.is_deleted())

        stats = {
            "added": 0,
            "renamed": 0,
            "deleted": 0,
            "unchanged": len(existing_paths & new_paths),
            "failed": len(self.failed),
            "initial_active": initial_active,
            "initial_deleted": initial_deleted,
        }

        # Detect renamed/moved files BEFORE marking deletions and adding new files
        # This preserves runtime data (playcount, ratings, etc.) for renamed files
        renames = {}
        if paths_to_delete and paths_to_add:
            callback("Detecting renamed/moved files...")
            from .rename_detector import detect_renames, apply_renames
            import os

            # Collect entries that appear to be deleted
            potentially_deleted_entries = [
                entry
                for entry in self.index.entries
                if not entry.is_deleted()
                and entry["path"].data.lower() in paths_to_delete
            ]

            # Build file info for new paths (size, mtime)
            new_file_info = {}
            for path in self.paths:
                path_lower = path.lower()
                if path_lower in paths_to_add:
                    try:
                        stat_result = os.stat(path)
                        new_file_info[path] = (
                            stat_result.st_size,
                            stat_result.st_mtime,
                        )
                    except (OSError, IOError):
                        # Skip files we can't stat
                        pass

            # Detect renames
            renames = detect_renames(
                potentially_deleted_entries,
                new_file_info,
                similarity_threshold=0.75,
            )

            if renames:
                callback(f"Found {len(renames)} potential renames, applying...")
                renamed_count = apply_renames(
                    self.index.entries, self.tagfiles, renames
                )
                stats["renamed"] = renamed_count

                # Update paths_to_delete and paths_to_add to exclude renamed files
                renamed_old_paths = set(renames.keys())
                renamed_new_paths = {
                    new_path.lower() for new_path, _ in renames.values()
                }

                paths_to_delete = paths_to_delete - renamed_old_paths
                paths_to_add = paths_to_add - renamed_new_paths

                callback(
                    f"Applied {renamed_count} renames (preserved statistics). "
                    f"Remaining: {len(paths_to_delete)} to delete, {len(paths_to_add)} to add"
                )

        # Mark deleted files (excluding renamed files)
        if paths_to_delete:
            callback(f"Marking {len(paths_to_delete)} deleted files...")
            for entry in self.index.entries:
                if not entry.is_deleted():
                    # entry["path"] is already a TagEntry with .data attribute
                    if entry["path"].data.lower() in paths_to_delete:
                        entry.set_flag(FLAG_DELETED)
                        stats["deleted"] += 1

        # Add new files if any (excluding renamed files)
        if paths_to_add:
            callback(f"Adding {len(paths_to_add)} new files...")

            # Filter paths to only include new files
            original_paths = self.paths.copy()
            self.paths = {p for p in original_paths if p.lower() in paths_to_add}

            # Generate database entries for new files only
            # This preserves existing entries and their indices
            old_count = self.index.count

            # Generate new entries without clearing existing data
            new_fields = self._generator.generate(
                self.paths,
                self.formats,
                self.tagfiles,
                self.index,
                use_parallel,
                callback,
                preserve_existing=True,
            )

            # Merge multiple_fields if any
            if hasattr(self, "multiple_fields"):
                self.multiple_fields.update(new_fields)
            else:
                self.multiple_fields = new_fields

            stats["added"] = self.index.count - old_count

            # Restore all paths
            self.paths = original_paths
        else:
            callback("No new files to add")
            # Signal completion with 0 total so progress bar displays properly
            callback(0, 0)

        # Calculate final counts
        final_active = sum(1 for e in self.index.entries if not e.is_deleted())
        final_deleted = sum(1 for e in self.index.entries if e.is_deleted())

        stats["final_active"] = final_active
        stats["final_deleted"] = final_deleted

        callback(
            f"Update complete: {stats['added']} added, {stats['renamed']} renamed, "
            f"{stats['deleted']} deleted, {stats['unchanged']} unchanged, "
            f"{final_active} active entries ({final_deleted} deleted)"
        )

        return stats

    # ---------------------------------------------------------------------------
    # Database I/O (delegated to DatabaseIO)
    # ---------------------------------------------------------------------------

    def write(self, out_dir: str = "", callback: Callable = myprint):
        """Write the database to a directory.

        Files that will be written:
            database_0.tcd through database_8.tcd
            database_idx.tcd

        Args:
            out_dir: Output directory path
            callback: Progress callback function
        """
        DatabaseIO.write(self.tagfiles, self.index, out_dir, callback)

    @staticmethod
    def read(
        in_dir: str = "", callback: Callable = myprint, ipod_root: Optional[str] = None
    ):
        """Read the database from a directory and return a Database object.

        Files that will be read:
            database_0.tcd through database_8.tcd
            database_idx.tcd

        Args:
            in_dir: Input directory path
            callback: Progress callback function
            ipod_root: Optional iPod mount point for cross-compilation updates

        Returns:
            Database object with loaded data
        """
        db = Database(ipod_root=ipod_root)
        db.tagfiles, db.index = DatabaseIO.read(in_dir, callback)
        return db


__all__ = [
    "Database",
    "TagCache",
    "FileScanner",
    "DatabaseGenerator",
    "DatabaseIO",
    "myprint",
]
