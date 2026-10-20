"""Regression tests: `update` must correct NFD-stored paths to NFC in place.

Root cause (see [[concepts/unicode-nfd-nfc-rockbox-database-mismatch]] in the
wiki / docs/reports/ipod_nfd_affected_tracks.txt): macOS always hands
decomposed (NFD) Unicode to programs reading a FAT/exFAT volume, regardless of
what is actually stored on disk. ddm's scanner stored whatever macOS handed
it with no normalization, so accented filenames ended up NFD in the
database's filename tag while Rockbox's own FAT code reads/compares paths in
precomposed (NFC) form via a byte-exact strcasecmp (file_internal.c:462).
Net effect: the track plays fine from the file browser but is silently
unopenable from Database.

This must be fixed via `update_database()`, not a full rebuild, so listening
stats (playcount, rating, playtime, lastplayed, lastelapsed, lastoffset)
survive the correction. The existing fuzzy rename-detector is deliberately
NOT used for this (see the wiki page) -- its 3-char filename prefix
pre-filter breaks on names with an accent near the start, and its fallback
mtime/similarity heuristic risks merging stats onto the wrong track on a
library with many identical-mtime batch imports. Instead this reuses the
v0.9.1 "modified file" re-tag + stats-preserve pipeline
(test_update_modified_files.py), extended with a second (Unicode-mismatch)
trigger alongside its existing mtime-mismatch trigger.
"""

import shutil
import unicodedata

import pytest

from dap_db_manager.database import Database
from tests.conftest import music_test_folder

TEST_DATA_DIR = music_test_folder()
pytestmark = pytest.mark.skipif(
    not TEST_DATA_DIR.exists(), reason="Test data not available"
)


def _copy_fixture_mp3s(tmp_path, count=3):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    mp3s = sorted(TEST_DATA_DIR.glob("**/*.mp3"))[:count]
    assert mp3s, "fixture folder has no mp3 files"
    for f in mp3s:
        shutil.copy(f, music_dir / f.name)
    return music_dir


def _force_nfd_entry(db, filename_suffix):
    """Simulate the historic bug: decompose a stored path's Unicode form to
    NFD, as if it had been written by the pre-fix scanner on a real FAT
    volume, while the file itself remains on disk unchanged (the real file
    is never renamed -- only the stale database bytes are wrong)."""
    found = None
    for entry in db.index.entries:
        if entry.is_deleted():
            continue
        if entry["path"].data.lower().endswith(filename_suffix.lower()):
            found = entry
            break
    assert found is not None, "fixture entry not found to corrupt"
    nfd_path = unicodedata.normalize("NFD", found["path"].data)
    assert nfd_path != found["path"].data, (
        "fixture filename has no decomposable characters -- rename the "
        "fixture file to include an accented character (e.g. 'é') before "
        "this helper can do anything"
    )
    found["path"].data = nfd_path
    return found


def _active_entry_for(db, filename_suffix):
    for entry in db.index.entries:
        if entry.is_deleted():
            continue
        if entry["path"].data.lower().endswith(filename_suffix.lower()):
            return entry
    return None


class TestUpdateCorrectsNfdPaths:
    def test_nfd_path_is_renormalized_to_nfc(self, tmp_path):
        music_dir = _copy_fixture_mp3s(tmp_path)
        target = sorted(music_dir.glob("*.mp3"))[0]
        accented_name = "é" + target.name
        accented_path = music_dir / accented_name
        target.rename(accented_path)

        db = Database()
        db.add_dir(str(music_dir), recursive=True)
        db.generate_database(callback=lambda *a, **k: None, parallel=False)

        _force_nfd_entry(db, accented_name)

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        db2 = Database.read(str(db_dir), callback=lambda *a, **k: None)
        stats = db2.update_database(str(music_dir), callback=lambda *a, **k: None)

        assert stats["added"] == 0, (
            "an NFD/NFC path mismatch must not be classified as a new file "
            "(that would lose the old entry's stats and show up as a "
            "spurious 'added' count)"
        )
        assert stats["deleted"] == 0, (
            "the real on-disk file still exists -- it must never be marked "
            "deleted just because its stored path used the wrong Unicode form"
        )
        assert stats.get("renormalized", 0) == 1, (
            "update_database() must report the Unicode-form correction as "
            "its own 'renormalized' stat, distinct from mtime-triggered "
            "'modified', per the project's 'reporting is a correctness "
            "feature' convention"
        )

        corrected = _active_entry_for(db2, accented_name)
        assert corrected is not None, "corrected entry missing from active entries"
        stored_path = corrected["path"].data
        assert stored_path == unicodedata.normalize("NFC", stored_path), (
            "the corrected entry's stored path must be NFC, matching what "
            "Rockbox's FAT code reads/compares on-device"
        )

    def test_nfd_correction_preserves_stats(self, tmp_path):
        music_dir = _copy_fixture_mp3s(tmp_path)
        target = sorted(music_dir.glob("*.mp3"))[0]
        accented_name = "é" + target.name
        accented_path = music_dir / accented_name
        target.rename(accented_path)

        db = Database()
        db.add_dir(str(music_dir), recursive=True)
        db.generate_database(callback=lambda *a, **k: None, parallel=False)

        entry = _force_nfd_entry(db, accented_name)
        entry["playcount"] = 42
        entry["rating"] = 7

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        db2 = Database.read(str(db_dir), callback=lambda *a, **k: None)
        db2.update_database(str(music_dir), callback=lambda *a, **k: None)

        corrected = _active_entry_for(db2, accented_name)
        assert corrected is not None
        assert corrected["playcount"] == 42, (
            "correcting a path's Unicode form must not reset listening "
            "statistics -- same guarantee as the mtime-triggered 'modified' "
            "path and the rename-detection path"
        )
        assert corrected["rating"] == 7

    def test_second_update_is_a_steady_state_noop(self, tmp_path):
        music_dir = _copy_fixture_mp3s(tmp_path)
        target = sorted(music_dir.glob("*.mp3"))[0]
        accented_name = "é" + target.name
        accented_path = music_dir / accented_name
        target.rename(accented_path)

        db = Database()
        db.add_dir(str(music_dir), recursive=True)
        db.generate_database(callback=lambda *a, **k: None, parallel=False)

        _force_nfd_entry(db, accented_name)

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        db2 = Database.read(str(db_dir), callback=lambda *a, **k: None)
        db2.update_database(str(music_dir), callback=lambda *a, **k: None)
        db2.write(str(db_dir))

        db3 = Database.read(str(db_dir), callback=lambda *a, **k: None)
        stats3 = db3.update_database(str(music_dir), callback=lambda *a, **k: None)

        assert stats3.get("renormalized", 0) == 0, (
            "once a path has been corrected to NFC, a subsequent update "
            "run must not keep re-flagging it -- the comparison key must "
            "be stable, not re-trigger every run"
        )
        assert stats3["added"] == 0
        assert stats3["deleted"] == 0
