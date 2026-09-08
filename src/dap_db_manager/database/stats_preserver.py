"""Carry runtime statistics across a full database rebuild.

`generate` rebuilds the database from the music files on disk. Those files carry
no listening history, so without this module every rebuild silently discards the
device's playcount, rating, playtime, lastplayed and resume position.

The stats are read from the database being replaced and re-applied to the newly
built entries, matched on the normalized DAP path.

See docs/superpowers/specs/2026-09-08-preserve-stats-design.md.
"""

import logging
import os
from typing import Dict, Optional

# The runtime statistics -- what the user accumulated by listening.
#
# Deliberately excludes commitid (tag 19) and mtime (tag 20): those describe the
# database and the file on disk, not the listening, and carrying them forward
# would produce a database that lies about when it was built and when its files
# last changed.
STAT_TAGS = (
    "playcount",
    "rating",
    "playtime",
    "lastplayed",
    "lastelapsed",
    "lastoffset",
)


class StatsPreserver:
    """Applies previously recorded stats to freshly generated entries.

    Matching is on the database path, case-insensitively, consistent with how
    ``dap_root`` is handled elsewhere. Both sides come from
    ``utils.normalize_dap_path``, so they are directly comparable.

    The instance counts what happened so the caller can report it. A partial
    restore that looks like a complete one is the failure mode this feature is
    specifically meant to avoid, so the counts are not optional.
    """

    def __init__(self, stats_by_path: Dict[str, Dict[str, int]]):
        self._stats = stats_by_path
        self._claimed = set()
        self.matched = 0
        self.unmatched_new = 0

    def apply(self, path: str, entry) -> bool:
        """Copy stats onto ``entry`` if its path was in the old database.

        Returns True if stats were applied.
        """
        key = path.lower()
        stats = self._stats.get(key)
        if stats is None:
            self.unmatched_new += 1
            return False

        for tag in STAT_TAGS:
            value = stats.get(tag)
            if value:
                entry[tag] = value

        self._claimed.add(key)
        self.matched += 1
        return True

    @property
    def unmatched_old(self) -> int:
        """Old entries that no new file claimed -- files deleted or renamed."""
        return len(self._stats) - len(self._claimed)

    @property
    def available(self) -> int:
        return len(self._stats)

    def summary(self, total_entries: int) -> str:
        """A one-line, non-silent account of what happened."""
        return (
            f"Preserved stats for {self.matched:,} of {total_entries:,} entries "
            f"({self.unmatched_new:,} new files, "
            f"{self.unmatched_old:,} old entries unmatched)"
        )


def read_existing_stats(
    db_dir: str, dap_root: Optional[str] = None
) -> Dict[str, Dict[str, int]]:
    """Read runtime stats from the database in ``db_dir``.

    Returns a mapping of lowercased database path to its stats. Returns an empty
    mapping -- never raises -- when the directory is absent, holds no database,
    or holds one that cannot be parsed: a rebuild must not be blocked by the
    state of the database it is replacing.
    """
    if not db_dir or not os.path.isdir(db_dir):
        return {}

    if not os.path.exists(os.path.join(db_dir, "database_idx.tcd")):
        return {}

    try:
        # Imported here to avoid a circular import at module load.
        from . import Database

        # DatabaseIO.read calls its callback unconditionally, so None raises.
        # Passing a no-op keeps this silent without tripping the except below --
        # which would otherwise swallow the failure and quietly preserve nothing.
        db = Database.read(db_dir, callback=lambda *a, **k: None, dap_root=dap_root)
    except Exception as exc:  # noqa: BLE001 -- any failure means "no stats"
        logging.warning(
            "Could not read existing database in %s (%s); "
            "rebuilding without preserved stats.",
            db_dir,
            exc,
        )
        return {}

    stats: Dict[str, Dict[str, int]] = {}
    try:
        for entry in db.index.entries:
            if entry.is_deleted():
                continue
            path = str(entry.path)
            if not path:
                continue
            values = {}
            for tag in STAT_TAGS:
                try:
                    value = entry[tag]
                except (KeyError, AttributeError):
                    continue
                if value:
                    values[tag] = value
            if values:
                stats[path.lower()] = values
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Existing database in %s could not be walked (%s); "
            "rebuilding without preserved stats.",
            db_dir,
            exc,
        )
        return {}

    return stats
