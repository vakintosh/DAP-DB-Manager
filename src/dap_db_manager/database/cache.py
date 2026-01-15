"""Tag cache management for the DAP DB Manager.

This module handles efficient caching of music file tags to speed up
database generation by avoiding repeated file reads.
"""

import pickle
import gzip
import gc
import logging
from collections import OrderedDict
from typing import Optional, Callable, Any

try:
    import msgpack

    USE_MSGPACK = True
except ImportError:
    msgpack = None  # type: ignore[assignment]
    USE_MSGPACK = False
    logging.debug("msgpack not available, falling back to pickle")


class SimpleTag(dict):
    """Lightweight dict-like wrapper for tag data that supports item access and get_string method.

    This class is used to restore minimal tag dictionaries to a format compatible with
    database generation code, which expects tag objects with item access and get_string() method.
    """

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            # Match mutagen behavior - raise KeyError for missing fields
            raise KeyError(key)

    def get_string(self, key):
        """Get field value as a string list for titleformat compatibility."""
        try:
            value = self[key]
            # Convert value to list of strings
            if isinstance(value, (list, tuple)):
                return [str(v) for v in value]
            elif value is None:
                return []
            else:
                return [str(value)]
        except KeyError:
            raise KeyError(key)


class TagCache:
    """Manages a shared cache of music file tags with LRU eviction.

    The tag cache is shared between Database instances and uses an
    OrderedDict for efficient LRU (Least Recently Used) cache eviction.
    Supports compressed pickle storage with minimal memory footprint.
    Uses memory-based limits to prevent OOM issues.
    """

    # Shared cache across all instances
    _cache: OrderedDict[str, bytes] = OrderedDict()
    MAX_CACHE_MEMORY_MB = 512  # Maximum memory usage in MB (default: 512MB)
    _auto_trim = True  # Control automatic trimming during adds
    _memory_tracking_enabled = True  # Enable memory-based limits
    _current_memory_bytes = 0  # Estimated current memory usage

    @classmethod
    def get_cache(cls):
        """Get the shared cache instance."""
        return cls._cache

    @classmethod
    def set_max_cache_memory(cls, memory_mb: int) -> None:
        """Set the maximum cache memory usage.

        Args:
            memory_mb: Maximum memory in megabytes (minimum: 100MB)

        Raises:
            ValueError: If memory_mb is less than 100
        """
        if memory_mb < 100:
            raise ValueError("Cache memory must be at least 100 MB")
        cls.MAX_CACHE_MEMORY_MB = memory_mb
        # Trim cache if it now exceeds the new limit
        if cls._memory_tracking_enabled:
            cls._check_memory_and_trim()

    @classmethod
    def get_max_cache_memory(cls) -> int:
        """Get the current maximum cache memory in MB.

        Returns:
            Maximum memory in megabytes
        """
        return cls.MAX_CACHE_MEMORY_MB

    @classmethod
    def get_current_memory_usage(cls) -> tuple:
        """Get current memory usage of the cache.

        Returns:
            Tuple of (bytes, megabytes, entry_count)
        """
        if not cls._memory_tracking_enabled:
            # Recalculate if tracking was disabled
            cls._recalculate_memory_usage()

        memory_mb = cls._current_memory_bytes / (1024 * 1024)
        return (cls._current_memory_bytes, memory_mb, len(cls._cache))

    @classmethod
    def set_memory_tracking(cls, enabled: bool) -> None:
        """Enable or disable memory tracking.

        Args:
            enabled: True to enable memory tracking, False to disable
        """
        cls._memory_tracking_enabled = enabled
        if enabled:
            cls._recalculate_memory_usage()

    @classmethod
    def clear(cls):
        """Clear all entries from the cache."""
        cls._cache.clear()
        cls._current_memory_bytes = 0
        gc.collect()  # Free memory

    @classmethod
    def _recalculate_memory_usage(cls) -> None:
        """Recalculate total memory usage of the cache."""
        cls._current_memory_bytes = sum(
            cls._get_estimated_entry_size(value) for value in cls._cache.values()
        )

    @classmethod
    def _check_memory_and_trim(cls) -> None:
        """Check if memory limit is exceeded and trim if necessary."""
        if not cls._memory_tracking_enabled:
            return

        max_bytes = cls.MAX_CACHE_MEMORY_MB * 1024 * 1024
        if cls._current_memory_bytes > max_bytes:
            # Trim to 80% of memory limit
            target_bytes = int(max_bytes * 0.8)
            removed = 0

            while cls._current_memory_bytes > target_bytes and cls._cache:
                # Remove oldest item (LRU)
                _, value = cls._cache.popitem(last=False)
                entry_size = cls._get_estimated_entry_size(value)
                cls._current_memory_bytes -= entry_size
                removed += 1

            if removed > 0:
                logging.debug(
                    "Trimmed %d entries due to memory limit (%.1f MB -> %.1f MB)",
                    removed,
                    (cls._current_memory_bytes + removed * 1024) / (1024 * 1024),
                    cls._current_memory_bytes / (1024 * 1024),
                )
                gc.collect()

    @classmethod
    def set_auto_trim(cls, enabled: bool) -> None:
        """Enable or disable automatic cache trimming.

        Args:
            enabled: True to enable auto-trim, False to disable
        """
        cls._auto_trim = enabled

    @staticmethod
    def _get_estimated_entry_size(value: Any) -> int:
        """Estimate memory size of a cache entry in bytes.

        Args:
            value: Cache value (tuple of metadata and tags)

        Returns:
            Estimated size in bytes
        """
        try:
            if USE_MSGPACK:
                # msgpack is faster and more compact than pickle
                # Add overhead for dict/tuple structures (~200 bytes per entry)
                return len(msgpack.packb(value, use_bin_type=True)) + 200
            else:
                # Fallback to pickle
                return len(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)) + 200
        except Exception:
            # Fallback: assume ~1KB per entry if serialization fails
            return 1024

    @staticmethod
    def extract_essential_tags(tag_obj: Any) -> Optional[dict]:
        """Extract only essential fields from a Tag object to minimize cache size.

        Returns a lightweight dictionary instead of the full mutagen object.
        This reduces pickle size dramatically (from ~117KB to ~1KB per file).

        Args:
            tag_obj: Tag object (typically from mutagen)

        Returns:
            Dictionary with essential tag fields, or None if tag_obj is None
        """
        if tag_obj is None:
            return None

        # Fields needed for rockbox database generation
        essential_fields = [
            "artist",
            "album",
            "genre",
            "title",
            "composer",
            "comment",
            "grouping",
            "date",
            "discnumber",
            "tracknumber",
            "bitrate",
            "length",
            "path",
            "albumartist",
            "performer",
        ]

        result = {}
        for field in essential_fields:
            try:
                result[field] = tag_obj[field]
            except (KeyError, AttributeError):
                pass

        return result

    @staticmethod
    def restore_tag_dict(tag_dict: Optional[dict]) -> Optional[dict]:
        """Convert minimal tag dictionary back to a format compatible with database generation.

        The database generation code expects tag objects, but we can provide
        a lightweight dict-like wrapper instead of the full mutagen object.

        Args:
            tag_dict: Minimal tag dictionary

        Returns:
            Simple dict that supports item access, or None if tag_dict is None
        """
        if tag_dict is None:
            return None

        # Return a SimpleTag instance that supports item access and get_string method
        return SimpleTag(tag_dict)

    @classmethod
    def load(
        cls, path: str, paths_set: set, callback: Optional[Callable] = None
    ) -> None:
        """Load tags from a pickled file into the cache.

        Loads tags efficiently with error handling for corrupted files.
        Supports both compressed (.gz) and uncompressed formats.
        Restores minimal tag dictionaries to memory-efficient format.

        Args:
            path: Path to the pickle file to load
            paths_set: Set to update with loaded file paths
            callback: Optional callback for progress updates
        """
        try:
            # Detect if file is gzip compressed
            opener = gzip.open if path.endswith(".gz") else open
            open_mode = "rb"

            with opener(path, open_mode) as f:
                raw_data = f.read()

            # Try msgpack first, fall back to pickle for backward compatibility
            try:
                if USE_MSGPACK:
                    unpacker = msgpack.Unpacker(raw=False, use_list=True)
                    unpacker.feed(raw_data)
                    nItems = next(unpacker)
                    assert isinstance(nItems, int)
                    if callback:
                        callback(nItems)

                    # Bulk load optimization: bypass individual checks and load directly
                    for i in range(nItems):
                        try:
                            data = next(unpacker)
                            file_path, ((size, mtime), tags) = data
                        except StopIteration:
                            break
                        except (ValueError, TypeError) as e:
                            # Skip corrupted entries
                            if callback:
                                callback(
                                    f"Warning: Skipped corrupted entry {i + 1}/{nItems}: {e}"
                                )
                            continue
                        else:
                            if callback:
                                callback(file_path)

                            # Restore tags to usable format and cache
                            lowerpath = file_path.lower()
                            restored_tags = (
                                cls.restore_tag_dict(tags)
                                if isinstance(tags, dict)
                                else tags
                            )
                            cls._cache[lowerpath] = ((size, mtime), restored_tags)  # type: ignore[assignment]
                            paths_set.add(lowerpath)
                else:
                    raise ImportError("msgpack not available")
            except (
                (ImportError, msgpack.exceptions.ExtraData, StopIteration)
                if USE_MSGPACK
                else (ImportError,)
            ):
                # Fall back to pickle for backward compatibility
                import io

                f = io.BytesIO(raw_data)
                nItems = pickle.load(f)
                assert isinstance(nItems, int)
                if callback:
                    callback(nItems)

                # Bulk load optimization: bypass individual checks and load directly
                for i in range(nItems):
                    try:
                        data = pickle.load(f)
                        file_path, ((size, mtime), tags) = data
                    except EOFError:
                        break
                    except (pickle.UnpicklingError, ValueError) as e:
                        # Skip corrupted entries
                        if callback:
                            callback(
                                f"Warning: Skipped corrupted entry {i + 1}/{nItems}: {e}"
                            )
                        continue
                    else:
                        if callback:
                            callback(file_path)

                        # Restore tags to usable format and cache
                        lowerpath = file_path.lower()
                        restored_tags = (
                            cls.restore_tag_dict(tags)
                            if isinstance(tags, dict)
                            else tags
                        )
                        cls._cache[lowerpath] = ((size, mtime), restored_tags)  # type: ignore[assignment]
                        paths_set.add(lowerpath)

                # Recalculate memory usage after bulk load and trim if needed
                if cls._memory_tracking_enabled:
                    cls._recalculate_memory_usage()
                    cls._check_memory_and_trim()
        except (OSError, IOError):
            pass

    @classmethod
    def save(
        cls, path: str, paths_set: set, callback: Optional[Callable] = None
    ) -> tuple:
        """Save cached tags to a compressed pickled file.

        Args:
            path: Path to save the pickled tags file (will add .gz if not present)
            paths_set: Set of paths to save
            callback: Optional callback function for progress updates

        Returns:
            Tuple of (actual_path_used, number_of_entries_saved)

        Uses gzip compression and pickle protocol 5 for efficient storage.
        Stores only essential tag fields to minimize file size.
        """
        # Add .gz extension if not present
        if not path.endswith(".gz"):
            path = path + ".gz"

        # Only save paths that exist in tag_cache (some may have been trimmed)
        valid_paths = [p for p in paths_set if p in cls._cache]
        missing_count = len(paths_set) - len(valid_paths)
        if missing_count > 0:
            logging.warning(
                f"Cache trimmed during scan: {missing_count} files not in cache. "
                f"Consider increasing MAX_CACHE_MEMORY_MB (current: {cls.MAX_CACHE_MEMORY_MB} MB) "
                f"or disabling auto-trim during scan."
            )
        if callback:
            callback(len(valid_paths))

        # Use msgpack for faster serialization (2-3x faster than pickle)
        if USE_MSGPACK:
            packer = msgpack.Packer(use_bin_type=True)
            with gzip.open(path, "wb", compresslevel=6) as f:
                f.write(packer.pack(len(valid_paths)))
                for path_entry in sorted(valid_paths):
                    if callback:
                        callback(path_entry)
                    # Extract essential tags only before packing
                    size_mtime, tags = cls._cache[path_entry]
                    if not isinstance(tags, dict):  # type: ignore[unreachable]
                        essential_tags = cls.extract_essential_tags(tags)
                    else:
                        essential_tags = tags  # type: ignore[unreachable]
                    f.write(packer.pack((path_entry, (size_mtime, essential_tags))))
        else:
            # Fallback to pickle if msgpack not available
            with gzip.open(path, "wb", compresslevel=6) as f:
                pickle.dump(len(valid_paths), f, pickle.HIGHEST_PROTOCOL)
                for path_entry in sorted(valid_paths):
                    if callback:
                        callback(path_entry)
                    # Extract essential tags only before pickling
                    size_mtime, tags = cls._cache[path_entry]
                    if not isinstance(tags, dict):  # type: ignore[unreachable]
                        essential_tags = cls.extract_essential_tags(tags)
                    else:
                        essential_tags = tags  # type: ignore[unreachable]
                    pickle.dump(
                        (path_entry, (size_mtime, essential_tags)),
                        f,
                        pickle.HIGHEST_PROTOCOL,
                    )

        return (path, len(valid_paths))

    @classmethod
    def cleanup(cls, keep_paths: Optional[set] = None) -> None:
        """Remove unused entries from the shared tag_cache to free memory.

        Args:
            keep_paths: Optional set of paths to keep. If None, keeps all paths
                       from all Database instances currently in use.
        """
        if keep_paths is not None:
            # Remove entries not in keep_paths
            keys_to_remove = [k for k in cls._cache if k not in keep_paths]
            for key in keys_to_remove:
                if cls._memory_tracking_enabled:
                    entry_size = cls._get_estimated_entry_size(cls._cache[key])
                    cls._current_memory_bytes -= entry_size
                del cls._cache[key]

            # Force garbage collection to free memory immediately
            if keys_to_remove:
                gc.collect()

    @classmethod
    def trim(cls) -> None:
        """Trim cache to 80% of MAX_CACHE_MEMORY_MB by removing least recently used entries.

        This is called when cache exceeds memory limit to prevent unbounded growth.
        Uses LRU (Least Recently Used) eviction strategy with OrderedDict.
        """
        if not cls._memory_tracking_enabled:
            # If tracking disabled, can't trim based on memory
            return

        max_bytes = cls.MAX_CACHE_MEMORY_MB * 1024 * 1024
        if cls._current_memory_bytes > max_bytes:
            target_bytes = int(max_bytes * 0.8)
            removed = 0

            while cls._current_memory_bytes > target_bytes and cls._cache:
                _, value = cls._cache.popitem(last=False)
                entry_size = cls._get_estimated_entry_size(value)
                cls._current_memory_bytes -= entry_size
                removed += 1

            if removed > 0:
                logging.debug(
                    "Trimmed %d entries to 80%% of memory limit (%.1f MB -> %.1f MB)",
                    removed,
                    (cls._current_memory_bytes + removed * 1024) / (1024 * 1024),
                    cls._current_memory_bytes / (1024 * 1024),
                )
            gc.collect()

    @classmethod
    def get(cls, key: str, default=None):
        """Get a value from the cache and mark it as recently used.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        if key in cls._cache:
            # Move to end for LRU (mark as recently used)
            cls._cache.move_to_end(key)
            return cls._cache[key]
        return default

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache (tuple of (size, mtime), tags)
        """
        # Track if this is a new entry or update
        is_new = key not in cls._cache
        old_size = 0

        if not is_new and cls._memory_tracking_enabled:
            # Subtract old entry size before replacing
            old_size = cls._get_estimated_entry_size(cls._cache[key])
            cls._current_memory_bytes -= old_size

        # If value is a tuple with tags, wrap the tags in SimpleTag
        if isinstance(value, tuple) and len(value) == 2:
            metadata, tags = value
            if isinstance(tags, dict) and not hasattr(tags, "get_string"):
                # Wrap plain dict tags in SimpleTag for titleformat compatibility
                tags = cls.restore_tag_dict(tags)
                value = (metadata, tags)

        cls._cache[key] = value

        # Update memory tracking
        if cls._memory_tracking_enabled:
            entry_size = cls._get_estimated_entry_size(value)
            cls._current_memory_bytes += entry_size

        # Check memory-based limit and trim if needed (only if auto_trim is enabled)
        if cls._auto_trim and cls._memory_tracking_enabled:
            cls._check_memory_and_trim()

    @classmethod
    def contains(cls, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        return key in cls._cache

    @classmethod
    def move_to_end(cls, key: str) -> None:
        """Mark a key as recently used by moving it to the end.

        Args:
            key: Cache key
        """
        if key in cls._cache:
            cls._cache.move_to_end(key)
