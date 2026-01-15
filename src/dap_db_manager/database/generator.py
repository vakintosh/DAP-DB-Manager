"""Database generation logic for DAP DB Manager.

This module handles generating the Rockbox database structure from cached
music file tags with support for parallel processing.
"""

import os
import gc
import sys
from itertools import product
from typing import Optional, Callable, Dict, Tuple, List, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
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


# Worker-level cache for compiled formats (persists across batches in same process)
_worker_format_cache = {}
_worker_cache_key = None


def process_batch_task(
    entries_data: List[Dict[str, Any]],
    format_strings: Dict[str, Tuple[str, Optional[str]]],
    multiple_fields_config: List[str],
) -> List[Dict[str, Any]]:
    """Worker function to process a batch of entries in a separate process.

    This function handles the CPU-intensive task of formatting tags using titleformat.

    Args:
        entries_data: List of dicts containing {'path', 'mtime', 'tags'}
        format_strings: Dictionary of {field: (format_str, sort_str)}
        multiple_fields_config: List of fields that support multiple values

    Returns:
        List of processed entry dictionaries ready for assembly
    """
    # Import locally to avoid pickling issues if module not loaded
    try:
        from ..tagging import titleformat
    except ImportError:
        return []

    # Use cached compiled formats if available
    global _worker_format_cache, _worker_cache_key
    cache_key = (
        frozenset(format_strings.items()),
        tuple(sorted(multiple_fields_config)),
    )

    if _worker_cache_key != cache_key:
        # Compile formats (only once per worker process per format configuration)
        compiled_formats = {}
        multiple_fields_map = {}  # field -> blank_tag

        for field, (fmt_str, sort_str) in format_strings.items():
            # Check if field is multiple based on config passed from main process
            if field in multiple_fields_config:
                multiple_fields_map[field] = "<BLANK>"

            fmt = titleformat.compile(f"$if2({fmt_str},'<Untagged>')")
            if sort_str is not None:
                sort = titleformat.compile(f"$if2({sort_str},{fmt_str})")
            else:
                sort = None
            compiled_formats[field] = (fmt, sort)

        # Standard formats
        compiled_formats["date"] = titleformat.compile("$if2($year(%date%),0)")
        compiled_formats["discnumber"] = titleformat.compile("$if2(%discnumber%,0)")
        compiled_formats["tracknumber"] = titleformat.compile("$if2(%tracknumber%,0)")
        compiled_formats["bitrate"] = titleformat.compile("$if2(%bitrate%,0)")

        # Cache for future batches
        _worker_format_cache = (compiled_formats, multiple_fields_map)
        _worker_cache_key = cache_key
    else:
        compiled_formats, multiple_fields_map = _worker_format_cache

    processed_results = []

    for entry_data in entries_data:
        path = entry_data["path"]
        mtime = entry_data["mtime"]
        tags = entry_data["tags"]

        result = {"path": path, "mtime": mtime, "fields": {}, "multiple_fields": {}}

        # 1. Process standard fields checks (tracknumber, length)
        # Length (ms)
        try:
            length_val = float(tags.get("length", [0])[0]) * 1000
            result["length"] = int(length_val)
        except (ValueError, TypeError, IndexError, KeyError):
            result["length"] = 0

        # Tracknumber
        try:
            tracknumber = int(tags.get("tracknumber", [0])[0])
            if tracknumber < 0:
                result["tracknumber"] = 0
                result["flag_trknumgen"] = True
            else:
                result["tracknumber"] = tracknumber
                result["flag_trknumgen"] = False
        except (ValueError, TypeError, IndexError):
            result["tracknumber"] = 0
            result["flag_trknumgen"] = True

        # Tag title (special case in original code)
        try:
            result["title_tag"] = tags["title"][0]
        except (KeyError, IndexError):
            result["title_tag"] = "<Untagged>"

        # 2. Process Embedded Tags (numeric)
        embedded_values = {}
        for field in EMBEDDED_TAGS:
            if field in ("tracknumber", "flag", "mtime", "length"):
                continue

            try:
                # Use compiled format from map if available (should be there for standard formats)
                # But EMBEDDED_TAGS might not be in format_strings
                # Actually, standard formats like bitrate are added to compiled_formats above
                if field in compiled_formats:
                    fmt = compiled_formats[field]
                    # fmt is (format, sort), we want format
                    if isinstance(fmt, tuple):
                        formatted_value = str(fmt[0].format(tags))
                    else:
                        formatted_value = str(fmt.format(tags))
                else:
                    # Fallback if not in list?
                    formatted_value = "0"

                formatted_value = formatted_value.strip()
                if formatted_value and formatted_value not in (
                    "True",
                    "False",
                    "<Untagged>",
                ):
                    embedded_values[field] = int(formatted_value)
                else:
                    embedded_values[field] = 0
            except (KeyError, ValueError, AttributeError):
                embedded_values[field] = 0
        result["embedded"] = embedded_values

        # 3. Process formatted fields
        multiple_tags_data = {}
        for field in multiple_fields_map:
            multiple_tags_data[field] = []

        # Helper state for canonicalartist/grouping logic
        has_artist = False
        artist_value = None
        albumartist_value = None

        # We need to process in order of FILE_TAGS to maintain logic dependencies
        # (artist before canonicalartist)

        # Note: FILE_TAGS is imported from constants.
        # We iterate FILE_TAGS and check if we have a format for it.

        processed_fields = {}

        for field in FILE_TAGS:
            if field not in compiled_formats:
                continue

            fmt, sort = compiled_formats[field]

            # Special handling for canonicalartist
            if field == "canonicalartist":
                if has_artist and artist_value:
                    value = artist_value
                else:
                    value = albumartist_value if albumartist_value else "<Untagged>"

                sort_val = None
                if sort is not None:
                    sort_val = (
                        sort.format(tags)
                        if has_artist
                        else (albumartist_value or "<Untagged>")
                    )

                processed_fields[field] = {"value": value, "sort": sort_val}
                continue

            # Store artist/albumartist
            if field == "artist":
                artist_value = fmt.format(tags)
                has_artist = bool(
                    artist_value
                    and artist_value.strip()
                    and artist_value != "<Untagged>"
                )
            elif field == "album artist":
                albumartist_value = fmt.format(tags)

            # Special handling for grouping
            if field == "grouping":
                grouping_value = fmt.format(tags)
                has_grouping = bool(
                    grouping_value
                    and grouping_value.strip()
                    and grouping_value != "<Untagged>"
                )

                if not has_grouping:
                    try:
                        value = tags["title"][0]
                    except (KeyError, IndexError):
                        value = "<Untagged>"
                else:
                    value = grouping_value

                sort_val = None
                if sort is not None:
                    sort_val = sort.format(tags) if has_grouping else value

                processed_fields[field] = {"value": value, "sort": sort_val}
                continue

            # Normal field processing
            if field not in multiple_tags_data:
                value = fmt.format(tags)
                sort_val = sort.format(tags) if sort is not None else None
                processed_fields[field] = {"value": value, "sort": sort_val}
            else:
                # Multiple value field
                if sort is not None:
                    s_val = sort.format(tags)
                    sort_vals = s_val if isinstance(s_val, (tuple, list)) else [s_val]
                else:
                    sort_vals = [None]

                d_val = fmt.format(tags)
                data_vals = d_val if isinstance(d_val, (tuple, list)) else [d_val]

                # Zip and store
                # We need to handle length mismatch conceptually, zip truncates
                field_entries = []
                for v, s in zip(data_vals, sort_vals):
                    field_entries.append({"value": v, "sort": s})

                multiple_tags_data[field] = field_entries

        result["fields"] = processed_fields
        result["multiple_fields"] = multiple_tags_data

        processed_results.append(result)

    return processed_results


class DatabaseGenerator:
    """Handles database generation from cached tags with parallel processing."""

    def __init__(
        self,
        max_workers: Optional[int] = None,
        dap_root: Optional[str] = None,
        mount_notation: Optional[str] = None,
    ):
        """Initialize the database generator.

        Args:
            max_workers: Maximum number of parallel workers.
                        If None, auto-detects based on CPU count (recommended).
            dap_root: Optional DAP mount point for path translation.
                      When set, strips this prefix from file paths to create DAP-relative paths.
                      Example: dap_root="/Volumes/DAP" converts "/Volumes/DAP/Music/Song.mp3"
                      to "/Music/Song.mp3" (before mount_notation is added).
            mount_notation: Optional mount notation to prepend to paths.
                           Example: mount_notation="/<HDD0>" results in "/<HDD0>/Music/Song.mp3"
        """
        if max_workers is None:
            # For CPU-bound operations (formatting), use CPU count
            max_workers = os.cpu_count() or 1

        self.max_workers = max_workers
        self.dap_root = self._normalize_dap_root(dap_root)
        # Pre-normalize dap_root for path operations to avoid repeated string operations
        self.dap_root_normalized = (
            self.dap_root.replace("\\", "/").lower() if self.dap_root else None
        )
        self.mount_notation = mount_notation.rstrip("/") if mount_notation else None
        self._lock = Lock()

        # Persistent pool - reused across operations for better performance
        # Using ProcessPoolExecutor to bypass GIL for CPU-intensive string formatting
        self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self._shutdown = False

    @staticmethod
    def _normalize_dap_root(dap_root: Optional[str]) -> Optional[str]:
        """Normalize the DAP root path for consistent path translation."""
        if dap_root is None:
            return None
        root = str(dap_root).rstrip("/").rstrip("\\")
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
        """Generate the database from cached tags."""

        # Prepare format strings for workers (pickle-safe dicts strings)
        format_strings = {}
        multiple_fields_list = []
        multiple_fields = {}  # For checks in main thread return

        for field, (format, sort) in formats.items():
            if format.is_multiple:
                multiple_fields[field] = TagEntry("<BLANK>")
                multiple_fields_list.append(field)

            # Extract raw strings from titleformat objects
            # Assuming titleformat objects have to_string() method as seen in original code
            # We pass these strings to workers to re-compile
            fmt_str = format.to_string()
            sort_str = sort.to_string() if sort is not None else None
            format_strings[field] = (fmt_str, sort_str)

        # Batch progress updates
        # Adaptive batch size balances parallelization overhead vs processing efficiency
        # - Smaller batches: more frequent updates, higher overhead
        # - Larger batches: fewer updates, better throughput
        total_paths = len(paths)
        # Adaptive batch sizing: scale with dataset size and worker count
        # Aim for ~4 batches per worker to balance overhead and parallelism
        batch_size = min(max(total_paths // (self.max_workers * 4), 100), 500)
        sorted_paths = sorted(paths)

        if use_parallel and total_paths > 200:
            self._generate_parallel(
                sorted_paths,
                format_strings,
                multiple_fields_list,
                tagfiles,
                index,
                multiple_fields,
                callback,
                batch_size,
            )
        else:
            # For sequential, we can use the same worker logic but run it synchronously
            # Or use legacy method. Let's use the new logic for consistency but run locally
            # We just need to fake the "parallel" call
            self._generate_sequential(
                sorted_paths,
                format_strings,
                multiple_fields_list,
                tagfiles,
                index,
                multiple_fields,
                callback,
                batch_size,
            )

        if callback:
            callback(total_paths, total_paths)

        for field in FILE_TAGS:
            tagfiles[field].sort()

        TagCache.cleanup(keep_paths=paths)
        gc.collect()

        return multiple_fields

    def _prepare_entry_data(
        self, path: str, cache_entry: Tuple
    ) -> Optional[Dict[str, Any]]:
        """Helper to prepare entry data from cache for processing."""
        (size, mtime), tags = cache_entry

        # Path translation
        if self.dap_root:
            normalized_path = path.replace("\\", "/")

            if normalized_path.lower().startswith(self.dap_root_normalized):
                clean_path = normalized_path[len(self.dap_root) :]
                if not clean_path.startswith("/"):
                    clean_path = "/" + clean_path
            else:
                logging.warning(
                    "File path '%s' does not start with dap_root '%s'. Skipping.",
                    path,
                    self.dap_root,
                )
                return None
        else:
            from pathlib import PureWindowsPath, PurePosixPath

            path_obj = PureWindowsPath(path) if ":" in path else PurePosixPath(path)
            clean_path = str(
                PurePosixPath(
                    *path_obj.parts[1:] if path_obj.anchor else path_obj.parts
                )
            )
            if not clean_path.startswith("/"):
                clean_path = "/" + clean_path

        # Prepend mount notation if configured
        if self.mount_notation:
            clean_path = self.mount_notation + clean_path

        return {"path": clean_path, "mtime": mtime, "tags": tags}

    def _generate_sequential(
        self,
        sorted_paths,
        format_strings,
        multiple_fields_list,
        tagfiles,
        index,
        multiple_fields,
        callback,
        batch_size,
    ):
        """Sequential generation using the new worker logic (running in main process)."""
        cache = TagCache.get_cache()
        total_paths = len(sorted_paths)

        # We process in batches even sequentially to reuse the logic
        for i in range(0, total_paths, batch_size):
            batch_paths = sorted_paths[i : i + batch_size]
            batch_data = []

            # Pre-filter cache entries for batch to reduce repeated lookups
            for path in batch_paths:
                path_lower = path.lower()
                cache_entry = cache.get(path_lower)
                if cache_entry:
                    entry_data = self._prepare_entry_data(path, cache_entry)
                    if entry_data:
                        batch_data.append(entry_data)
                else:
                    logging.warning("File not in cache, skipping: %s", path)

            # Process synchronously
            results = process_batch_task(
                batch_data, format_strings, multiple_fields_list
            )

            for result in results:
                self._assemble_entry(result, tagfiles, index, multiple_fields)

            if callback:
                callback(min(i + batch_size, total_paths), total_paths)

    def _generate_parallel(
        self,
        sorted_paths,
        format_strings,
        multiple_fields_list,
        tagfiles,
        index,
        multiple_fields,
        callback,
        batch_size,
    ):
        """Parallel generation using ProcessPoolExecutor with sliding window."""
        total_paths = len(sorted_paths)
        processed = 0
        cache = TagCache.get_cache()

        if self._shutdown:
            logging.warning("Pool shut down, falling back to sequential")
            self._generate_sequential(
                sorted_paths,
                format_strings,
                multiple_fields_list,
                tagfiles,
                index,
                multiple_fields,
                callback,
                batch_size,
            )
            return

        # Sliding window: keep max 2x workers worth of futures in flight
        max_futures_in_flight = self.max_workers * 2
        futures = {}
        batch_index = 0
        total_batches = (total_paths + batch_size - 1) // batch_size

        def submit_batch(batch_start):
            """Helper to prepare and submit a batch."""
            batch_paths = sorted_paths[batch_start : batch_start + batch_size]
            batch_data = []

            # Pre-filter cache entries for batch to reduce repeated lookups
            for path in batch_paths:
                path_lower = path.lower()
                cache_entry = cache.get(path_lower)
                if cache_entry:
                    entry_data = self._prepare_entry_data(path, cache_entry)
                    if entry_data:
                        batch_data.append(entry_data)
                else:
                    logging.warning("File not in cache, skipping: %s", path)

            if batch_data:
                future = self._executor.submit(
                    process_batch_task, batch_data, format_strings, multiple_fields_list
                )
                return future, len(batch_data)
            return None, 0

        # Submit initial window of batches
        while batch_index < min(max_futures_in_flight, total_batches):
            future, count = submit_batch(batch_index * batch_size)
            if future:
                futures[future] = count
            batch_index += 1

        # Process completed futures and submit new ones
        while futures:
            for future in as_completed(futures):
                try:
                    results = future.result()

                    # Assemble entries in main thread (fast)
                    for result in results:
                        self._assemble_entry(result, tagfiles, index, multiple_fields)

                    processed += len(results)
                    if callback:
                        callback(processed, total_paths)
                except Exception as e:
                    logging.error("Batch processing failed: %s", e)
                finally:
                    # Remove completed future and submit new batch if available
                    del futures[future]

                    if batch_index < total_batches:
                        new_future, count = submit_batch(batch_index * batch_size)
                        if new_future:
                            futures[new_future] = count
                        batch_index += 1

                    # Break inner loop to restart as_completed with updated futures dict
                    break

    def _assemble_entry(self, result: Dict[str, Any], tagfiles, index, multiple_fields):
        """Assemble IndexEntry and TagEntries from processed result."""
        entry = IndexEntry()

        # Path
        entry.path = TagEntry(result["path"], is_path=True)
        entry.path.index = index.count
        tagfiles["path"].append_sorted(entry.path)

        # Title
        try:
            entry.title = TagEntry(result["title_tag"])
        except KeyError:
            entry.title = TagEntry("<Untagged>")
        entry.title.index = index.count
        tagfiles["title"].append_sorted(entry.title)

        # Metadata
        entry.mtime = mtime_to_fat(result["mtime"])
        entry.length = result["length"]
        entry.flag = 0
        entry.tracknumber = result["tracknumber"]
        if result["flag_trknumgen"]:
            entry.set_flag(FLAG_TRKNUMGEN)

        # Embedded fields
        for field, value in result["embedded"].items():
            entry[field] = value

        # Formatted fields
        multiple_tags_entries = {}
        for field, blank_tag in multiple_fields.items():
            multiple_tags_entries[field] = [blank_tag]

        processed_fields = result["fields"]
        multiple_processed = result["multiple_fields"]

        for field in FILE_TAGS:
            if field not in processed_fields and field not in multiple_processed:
                continue

            if field in multiple_processed:
                # Handle multiple
                entries = multiple_processed[field]
                tag_entries = []
                for item in entries:
                    val = item["value"]
                    sort = item["sort"]
                    tag_entries.append(TagEntry(val, sort))
                multiple_tags_entries[field] = tag_entries
            else:
                # Handle single
                item = processed_fields[field]
                val = item["value"]
                sort = item["sort"]

                try:
                    tagentry = tagfiles[field][val]
                except KeyError:
                    tagentry = TagEntry(val, sort)
                    tagfiles[field].append_sorted(tagentry)
                entry[field] = tagentry

        # Combinations logic
        combinations = []
        for field, tagentries in multiple_tags_entries.items():
            combinations.append([(field, tagentry) for tagentry in tagentries])

        for fields in product(*combinations):
            index_entry = entry.copy()
            for field, value in fields:
                try:
                    # If it's a new TagEntry created in this loop, it won't be in tagfiles yet
                    # But for multiple fields, we created new TagEntry objects above
                    # For non-multiple fields, we used existing or created new ones

                    # For lookups, we use value.key.
                    tagentry = tagfiles[field][value.key]
                except KeyError:
                    tagentry = value
                    tagfiles[field].append_sorted(tagentry)
                index_entry[field] = tagentry
            index.append(index_entry)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the persistent thread pool."""
        if not self._shutdown:
            self._shutdown = True
            self._executor.shutdown(wait=wait)

    def __del__(self):
        """Cleanup pool."""
        try:
            self.shutdown(wait=False)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False
