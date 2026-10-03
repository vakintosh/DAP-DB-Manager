"""Regression tests: `update` must detect in-place tag edits.

Root cause (see docs/superpowers or the ddm-parity-audit journal entry): the
update algorithm computed added/deleted/renamed purely from *path* set
differences. A file whose path doesn't change -- i.e. the overwhelming
majority of real-world edits, where you retag a file without renaming it --
fell into the "unchanged" bucket and was never rescanned, silently
contradicting the documented behaviour ("only processes new or modified
files") and diverging from Rockbox's own `tagcache_update`/`add_tagcache`,
which compares stored vs on-disk mtime per file and re-tags on a mismatch.
"""

import os
import shutil
import time

import pytest
from mutagen.easyid3 import EasyID3

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


def _retag_title(path, new_title):
    audio = EasyID3(str(path))
    audio["title"] = [new_title]
    audio.save()
    # Ensure the new mtime is unambiguously different (FAT timestamps are
    # 2-second resolution) and clearly after "now".
    future = time.time() + 1000
    os.utime(path, (future, future))


def _title_for(db, path_str):
    """Look up the title tag text for a given (unnormalized) db path."""
    for entry in db.index.entries:
        if entry.is_deleted():
            continue
        if entry["path"].data.lower().endswith(path_str.lower()):
            return entry["title"].data
    return None


class TestUpdateDetectsModifiedFiles:
    def test_inplace_tag_edit_is_reflected_after_update(self, tmp_path):
        music_dir = _copy_fixture_mp3s(tmp_path)
        target = sorted(music_dir.glob("*.mp3"))[0]

        db = Database()
        db.add_dir(str(music_dir), recursive=True)
        db.generate_database(callback=lambda *a, **k: None, parallel=False)

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        assert _title_for(db, target.name) != "REGRESSION-TEST-NEW-TITLE"

        _retag_title(target, "REGRESSION-TEST-NEW-TITLE")

        db2 = Database.read(str(db_dir), callback=lambda *a, **k: None)
        stats = db2.update_database(str(music_dir), callback=lambda *a, **k: None)

        assert stats["added"] == 0
        assert stats["deleted"] == 0
        assert stats.get("modified", 0) == 1, (
            "update_database() must classify an in-place tag edit as "
            "'modified', not silently fold it into 'unchanged'"
        )

        assert _title_for(db2, target.name) == "REGRESSION-TEST-NEW-TITLE", (
            "update did not re-read tags for a file whose path was "
            "unchanged but whose mtime/content changed on disk"
        )

    def test_modified_file_preserves_playcount(self, tmp_path):
        music_dir = _copy_fixture_mp3s(tmp_path)
        target = sorted(music_dir.glob("*.mp3"))[0]

        db = Database()
        db.add_dir(str(music_dir), recursive=True)
        db.generate_database(callback=lambda *a, **k: None, parallel=False)

        # Simulate listening history before the file is retagged.
        for entry in db.index.entries:
            if entry["path"].data.lower().endswith(target.name.lower()):
                entry["playcount"] = 42
                entry["rating"] = 7

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        _retag_title(target, "REGRESSION-TEST-NEW-TITLE-2")

        db2 = Database.read(str(db_dir), callback=lambda *a, **k: None)
        db2.update_database(str(music_dir), callback=lambda *a, **k: None)

        found = None
        for entry in db2.index.entries:
            if entry.is_deleted():
                continue
            if entry["path"].data.lower().endswith(target.name.lower()):
                found = entry
        assert found is not None, "modified file missing from active entries"
        assert found["playcount"] == 42, (
            "retagging a file in place must not reset its listening "
            "statistics (playcount, rating, etc.) -- same mechanism as the "
            "rename-detection / generate --preserve-stats path"
        )
        assert found["rating"] == 7
