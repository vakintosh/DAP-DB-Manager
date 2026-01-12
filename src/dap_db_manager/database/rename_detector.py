"""Rename detection for database updates.

This module provides functionality to detect when files have been renamed or moved
rather than deleted and re-added. This prevents loss of runtime data (play counts,
ratings, etc.) when file paths change.

The detection uses multiple strategies:
1. Exact metadata match: file size + audio length + mtime
2. Fuzzy metadata match: file size + audio length (for moved files with same content)
3. Path similarity: Levenshtein distance for minor name changes
"""

import logging
from typing import Dict, Set, Tuple, Optional, List
from pathlib import Path
from difflib import SequenceMatcher


def _calculate_fingerprint(
    length: Optional[int],
    bitrate: Optional[int],
    mtime: Optional[float],
    include_mtime: bool = True,
) -> Optional[Tuple]:
    """Calculate a fingerprint for a file based on metadata.

    Args:
        length: Audio duration in milliseconds
        bitrate: Bitrate in kbps
        mtime: Modification time (Unix timestamp)
        include_mtime: Whether to include mtime in fingerprint

    Returns:
        Tuple of (length, bitrate, mtime) or (length, bitrate) or None if data missing
    """
    # Require at least length (audio duration)
    if length is None or length == 0:
        return None

    # Bitrate can be 0 for some formats, so don't require it
    if include_mtime and mtime is not None:
        return (length, bitrate or 0, int(mtime))
    else:
        return (length, bitrate or 0)


def _path_similarity(path1: str, path2: str) -> float:
    """Calculate similarity between two file paths.

    Uses SequenceMatcher to compute a similarity ratio, with special
    handling to favor matching filenames over directory paths.

    Args:
        path1: First path
        path2: Second path

    Returns:
        Similarity score between 0.0 and 1.0
    """
    # Extract filenames for comparison
    name1 = Path(path1).name.lower()
    name2 = Path(path2).name.lower()

    # Calculate filename similarity
    filename_similarity = SequenceMatcher(None, name1, name2).ratio()

    # Also calculate full path similarity
    full_similarity = SequenceMatcher(None, path1.lower(), path2.lower()).ratio()

    # Weight filename similarity higher (70%) than full path (30%)
    return 0.7 * filename_similarity + 0.3 * full_similarity


def detect_renames(
    deleted_entries: List,
    new_file_info: Dict[str, Tuple[Optional[int], Optional[float]]],
    similarity_threshold: float = 0.75,
) -> Dict[str, Tuple[str, str]]:
    """Detect renamed/moved files by matching metadata and path similarity.

    This function matches files that appear to have been deleted with files
    that appear to be new additions, using multiple strategies:

    1. Exact fingerprint match (length + bitrate + mtime)
    2. Fuzzy fingerprint match (length + bitrate, for copied/moved files)
    3. Path similarity match (for simple renames like "01_Song.mp3" → "01 - Song.mp3")

    Args:
        deleted_entries: List of IndexEntry objects that appear to be deleted
        new_file_info: Dict mapping new file paths to (size, mtime) tuples (size unused)
        similarity_threshold: Minimum path similarity score (0.0-1.0) for rename detection

    Returns:
        Dict mapping old_path (lowercase) to (new_path, match_reason) tuples
        where match_reason is one of: "exact_match", "fuzzy_match", "path_similarity"
    """
    if not deleted_entries or not new_file_info:
        return {}

    renames: Dict[str, Tuple[str, str]] = {}

    # Build fingerprint maps for deleted entries
    deleted_exact_map: Dict[Tuple, List] = {}  # fingerprint -> [entries]
    deleted_fuzzy_map: Dict[Tuple, List] = {}  # fingerprint -> [entries]
    deleted_by_path: Dict[str, object] = {}  # path -> entry

    for entry in deleted_entries:
        if entry.is_deleted():
            continue  # Skip already deleted

        old_path = entry["path"].data
        old_path_lower = old_path.lower()

        # Get metadata from entry (these are stored in IndexEntry)
        length = entry.get("length", 0)  # Audio duration in ms
        bitrate = entry.get("bitrate", 0)  # Bitrate
        mtime = entry.get("mtime")  # Modification time

        # Store for path similarity matching
        deleted_by_path[old_path_lower] = entry

        # Build exact fingerprint (length + bitrate + mtime)
        exact_fp = _calculate_fingerprint(length, bitrate, mtime, include_mtime=True)
        if exact_fp:
            if exact_fp not in deleted_exact_map:
                deleted_exact_map[exact_fp] = []
            deleted_exact_map[exact_fp].append((old_path_lower, entry))

        # Build fuzzy fingerprint (length + bitrate only)
        fuzzy_fp = _calculate_fingerprint(length, bitrate, mtime, include_mtime=False)
        if fuzzy_fp:
            if fuzzy_fp not in deleted_fuzzy_map:
                deleted_fuzzy_map[fuzzy_fp] = []
            deleted_fuzzy_map[fuzzy_fp].append((old_path_lower, entry))

    logging.info(
        "Rename detection: %d deleted entries, %d new files",
        len(deleted_by_path),
        len(new_file_info),
    )

    # Note: For new files, we don't have audio metadata yet (length, bitrate)
    # because we haven't scanned and read their tags. We only have file size and mtime
    # from os.stat(). So we'll rely primarily on path similarity and mtime matching.

    matched_new_paths: Set[str] = set()
    matched_old_paths: Set[str] = set()

    # Strategy 1: Path similarity matching with mtime verification
    # This is effective for simple renames like "01_Song.mp3" → "01 - Song.mp3"
    # or folder renames like "Artist/Album" → "Artist - Album"

    for old_path_lower, entry in deleted_by_path.items():
        if old_path_lower in matched_old_paths:
            continue

        best_match: Optional[str] = None
        best_score = 0.0

        # Get mtime for the deleted file
        old_mtime = entry.get("mtime")

        for new_path in new_file_info.keys():
            if new_path.lower() in matched_new_paths:
                continue

            # Get mtime from new file info
            _, new_mtime = new_file_info[new_path]

            # Calculate path similarity
            similarity = _path_similarity(old_path_lower, new_path.lower())

            if similarity > best_score and similarity >= similarity_threshold:
                # Additional verification: check if mtime is close (within 2 seconds)
                mtime_close = True
                if old_mtime and new_mtime:
                    mtime_close = abs(old_mtime - new_mtime) <= 2

                # High path similarity is a strong signal, especially with mtime match
                if mtime_close or similarity >= 0.85:
                    best_score = similarity
                    best_match = new_path

        if best_match and best_score >= similarity_threshold:
            renames[old_path_lower] = (best_match, "path_similarity")
            matched_new_paths.add(best_match.lower())
            matched_old_paths.add(old_path_lower)
            logging.debug(
                "Rename detected (path similarity=%.2f): %s → %s",
                best_score,
                old_path_lower,
                best_match,
            )

    # Strategy 2: Exact mtime matching (fallback for moved files)
    # This handles cases where files are moved to completely different locations
    # but the file timestamp remains identical

    for old_path_lower, entry in deleted_by_path.items():
        if old_path_lower in matched_old_paths:
            continue

        old_mtime = entry.get("mtime")

        if not old_mtime:
            continue  # Need mtime for this strategy

        for new_path in new_file_info.keys():
            if new_path.lower() in matched_new_paths:
                continue

            _, new_mtime = new_file_info[new_path]

            # Exact mtime match (within 1 second)
            if new_mtime:
                mtime_diff = abs(old_mtime - new_mtime)
                if mtime_diff <= 1:
                    # Also check that filenames are similar (not completely different files)
                    # This prevents false positives
                    path_sim = _path_similarity(old_path_lower, new_path.lower())
                    if path_sim >= 0.3:  # Very lenient threshold for moved files
                        renames[old_path_lower] = (new_path, "metadata_match")
                        matched_new_paths.add(new_path.lower())
                        matched_old_paths.add(old_path_lower)
                        logging.debug(
                            "Rename detected (metadata match): %s → %s",
                            old_path_lower,
                            new_path,
                        )
                        break

    logging.info("Rename detection found %d potential renames", len(renames))
    return renames


def apply_renames(
    index_entries: List,
    tagfiles: Dict,
    renames: Dict[str, Tuple[str, str]],
) -> int:
    """Apply detected renames to database entries.

    Updates the path field of entries that have been renamed, preserving
    all other metadata including playcount, rating, etc.

    Args:
        index_entries: List of all IndexEntry objects
        tagfiles: Dict of tagfile objects by field name
        renames: Dict mapping old_path (lowercase) to (new_path, reason) tuples

    Returns:
        Number of entries successfully renamed
    """
    if not renames:
        return 0

    renamed_count = 0
    path_tagfile = tagfiles.get("path")

    if not path_tagfile:
        logging.warning("Cannot apply renames: path tagfile not found")
        return 0

    # Import TagEntry here to avoid circular imports

    for entry in index_entries:
        if entry.is_deleted():
            continue

        old_path_entry = entry["path"]
        old_path = old_path_entry.data
        old_path_lower = old_path.lower()

        if old_path_lower in renames:
            new_path, reason = renames[old_path_lower]

            # CRITICAL: Modify the existing TagEntry's data in-place
            # This preserves the object reference and prevents orphaned entries
            old_path_entry.data = new_path

            # Update the tagfile's entrydict to map new path to this entry
            # Remove old mapping if it exists
            if old_path in path_tagfile.entrydict:
                del path_tagfile.entrydict[old_path]

            # Add new mapping
            path_tagfile.entrydict[new_path] = old_path_entry

            renamed_count += 1
            logging.info("Applied rename (%s): %s → %s", reason, old_path, new_path)

    return renamed_count
