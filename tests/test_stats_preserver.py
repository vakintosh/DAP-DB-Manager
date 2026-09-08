"""Tests for preserving runtime stats across a full rebuild.

See docs/superpowers/specs/2026-09-08-preserve-stats-design.md.

`generate` rebuilds from the music files and has no stats source, so before
this feature every rebuild silently destroyed playcount, rating, playtime,
lastplayed and the resume position.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from dap_db_manager.database.stats_preserver import (
    STAT_TAGS,
    StatsPreserver,
    read_existing_stats,
)
from dap_db_manager.database import Database
from dap_db_manager.database.io import DatabaseIO
from dap_db_manager.indexfile import IndexEntry
from tests.conftest import music_test_folder

REPO_ROOT = Path(__file__).parent.parent


def _entry(path, **stats):
    """Build an IndexEntry carrying a path and optional stats."""
    e = IndexEntry()
    e.flag = 0
    for k, v in stats.items():
        e[k] = v
    return e


class TestStatTags:
    def test_carries_exactly_the_six_runtime_fields(self):
        assert set(STAT_TAGS) == {
            "playcount",
            "rating",
            "playtime",
            "lastplayed",
            "lastelapsed",
            "lastoffset",
        }

    def test_does_not_carry_commitid_or_mtime(self):
        """These describe the database and the file, not the listening.

        Carrying them forward would produce a database that lies about when it
        was built and when its files last changed.
        """
        assert "commitid" not in STAT_TAGS
        assert "mtime" not in STAT_TAGS


class TestStatsPreserver:
    def test_exact_path_match_carries_all_six_fields(self):
        p = StatsPreserver(
            {
                "/<hdd0>/music/a.mp3": {
                    "playcount": 7,
                    "rating": 5,
                    "playtime": 1234,
                    "lastplayed": 999,
                    "lastelapsed": 42,
                    "lastoffset": 17,
                }
            }
        )
        e = _entry("/<HDD0>/Music/a.mp3")
        assert p.apply("/<HDD0>/Music/a.mp3", e) is True
        assert e["playcount"] == 7
        assert e["rating"] == 5
        assert e["playtime"] == 1234
        assert e["lastplayed"] == 999
        assert e["lastelapsed"] == 42
        assert e["lastoffset"] == 17

    def test_match_is_case_insensitive(self):
        p = StatsPreserver({"/<hdd0>/music/a.mp3": {"playcount": 3}})
        e = _entry("/<HDD0>/MUSIC/A.mp3")
        assert p.apply("/<HDD0>/MUSIC/A.mp3", e) is True
        assert e["playcount"] == 3

    def test_new_file_gets_no_stats_and_reports_unmatched(self):
        p = StatsPreserver({"/<hdd0>/music/a.mp3": {"playcount": 3}})
        e = _entry("/<HDD0>/Music/brand-new.mp3")
        assert p.apply("/<HDD0>/Music/brand-new.mp3", e) is False
        assert e["playcount"] == 0

    def test_counts_are_reported(self):
        """A partial restore that looks complete is the failure mode this
        feature must not have."""
        p = StatsPreserver(
            {
                "/<hdd0>/music/a.mp3": {"playcount": 1},
                "/<hdd0>/music/gone.mp3": {"playcount": 9},
            }
        )
        p.apply("/<HDD0>/Music/a.mp3", _entry("/<HDD0>/Music/a.mp3"))
        p.apply("/<HDD0>/Music/new.mp3", _entry("/<HDD0>/Music/new.mp3"))

        assert p.matched == 1
        assert p.unmatched_new == 1
        assert p.unmatched_old == 1  # "gone.mp3" was never claimed

    def test_empty_source_is_a_clean_no_op(self):
        p = StatsPreserver({})
        e = _entry("/<HDD0>/Music/a.mp3")
        assert p.apply("/<HDD0>/Music/a.mp3", e) is False
        assert p.matched == 0
        assert e["playcount"] == 0

    def test_missing_fields_default_to_zero(self):
        """An old entry that only has a playcount must not corrupt the rest."""
        p = StatsPreserver({"/<hdd0>/music/a.mp3": {"playcount": 4}})
        e = _entry("/<HDD0>/Music/a.mp3")
        p.apply("/<HDD0>/Music/a.mp3", e)
        assert e["playcount"] == 4
        assert e["rating"] == 0


class TestReadExistingStats:
    def test_missing_directory_returns_empty(self, tmp_path):
        """A rebuild must proceed when there is no previous database."""
        stats = read_existing_stats(str(tmp_path / "nope"))
        assert stats == {}

    def test_directory_without_a_database_returns_empty(self, tmp_path):
        (tmp_path / "unrelated.txt").write_text("hi")
        assert read_existing_stats(str(tmp_path)) == {}

    def test_corrupt_database_returns_empty_and_does_not_raise(self, tmp_path):
        """A corrupt old database must not abort the rebuild."""
        for name in ("database_idx.tcd", "database_4.tcd"):
            (tmp_path / name).write_bytes(b"\x00\x01\x02not a tagcache")
        assert read_existing_stats(str(tmp_path)) == {}


@pytest.mark.skipif(
    not music_test_folder().exists(), reason="music fixture folder not available"
)
class TestPreserveStatsIntegration:
    """End-to-end: generate, inject stats, regenerate, assert they survive.

    The unit tests above all cover *absent* data, so they stayed green while
    read_existing_stats silently returned {} for every real database --
    DatabaseIO.read calls its callback unconditionally, so callback=None raised
    and the broad except swallowed it. Only exercising a real database catches
    that class of bug.
    """

    def _generate(self, music_dir, out_dir, extra_args=()):
        # 'python -m dap_db_manager.cli' does not work: the package has no
        # __main__ guard. Use the installed console script from this venv.
        ddm = Path(sys.executable).parent / "ddm"
        cmd = [
            str(ddm), "generate",
            "--music-dir", str(music_dir), "--output", str(out_dir), *extra_args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)

    def test_stats_are_preserved_across_a_full_rebuild(self, tmp_path):
        out = tmp_path / "db"
        out.mkdir()

        assert self._generate(music_test_folder(), out).returncode == 0

        # Inject known stats into every third entry.
        db = Database.read(str(out), callback=lambda *a, **k: None)
        expected = {}
        for i, e in enumerate(db.index.entries):
            if i % 3 == 0:
                e["playcount"] = 10 + i
                e["rating"] = (i % 5) + 1
                e["playtime"] = 1000 + i
                e["lastplayed"] = 5000 + i
                expected[str(e.path).lower()] = (10 + i, (i % 5) + 1, 1000 + i, 5000 + i)
        DatabaseIO.write(db.tagfiles, db.index, str(out), callback=lambda *a, **k: None)
        assert expected, "fixture produced no entries to inject into"

        # Rebuild over the top.
        result = self._generate(music_test_folder(), out)
        assert result.returncode == 0
        assert "Preserved stats" in result.stdout, result.stdout

        # The reported count must be non-zero and must match what was injected.
        # Asserting only on the string is not enough: an earlier version printed
        # the summary before generation ran, so it truthfully reported
        # "Preserved stats for 0 of N" while the stats were in fact applied.
        m = re.search(r"Preserved stats for ([\d,]+) of", result.stdout)
        assert m, result.stdout
        reported = int(m.group(1).replace(",", ""))
        assert reported == len(expected), (
            f"reported {reported} preserved, injected {len(expected)}"
        )

        rebuilt = Database.read(str(out), callback=lambda *a, **k: None)
        checked = 0
        for e in rebuilt.index.entries:
            key = str(e.path).lower()
            if key in expected:
                pc, rating, playtime, lastplayed = expected[key]
                assert e["playcount"] == pc, f"playcount lost for {key}"
                assert e["rating"] == rating, f"rating lost for {key}"
                assert e["playtime"] == playtime, f"playtime lost for {key}"
                assert e["lastplayed"] == lastplayed, f"lastplayed lost for {key}"
                checked += 1
        assert checked == len(expected), f"only {checked}/{len(expected)} preserved"

    def test_no_preserve_stats_discards_them(self, tmp_path):
        out = tmp_path / "db"
        out.mkdir()
        assert self._generate(music_test_folder(), out).returncode == 0

        db = Database.read(str(out), callback=lambda *a, **k: None)
        for e in db.index.entries:
            e["playcount"] = 99
        DatabaseIO.write(db.tagfiles, db.index, str(out), callback=lambda *a, **k: None)

        assert self._generate(
            music_test_folder(), out, ("--no-preserve-stats",)
        ).returncode == 0

        rebuilt = Database.read(str(out), callback=lambda *a, **k: None)
        assert all(e["playcount"] == 0 for e in rebuilt.index.entries)

    def test_conflicting_flags_are_rejected(self, tmp_path):
        out = tmp_path / "db"
        out.mkdir()
        result = self._generate(
            music_test_folder(), out,
            ("--no-preserve-stats", "--preserve-stats-from", str(out)),
        )
        assert result.returncode != 0
        assert "cannot be combined" in (result.stdout + result.stderr).lower()
