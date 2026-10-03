"""Tests for two-phase scan in update: fast metadata scan + targeted tag reading."""

import os
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from mutagen.easyid3 import EasyID3

from dap_db_manager.database import Database
from dap_db_manager.database.file_scanner import FileScanner
from tests.conftest import music_test_folder

TEST_DATA_DIR = music_test_folder()
pytestmark = pytest.mark.skipif(
    not TEST_DATA_DIR.exists(), reason="Test data not available"
)


def _copy_fixture_mp3s(target_dir, count=3):
    mp3s = sorted(TEST_DATA_DIR.glob("**/*.mp3"))[:count]
    assert len(mp3s) >= count, "fixture folder has fewer mp3 files than requested"
    copied = []
    for f in mp3s:
        dest = target_dir / f.name
        shutil.copy(f, dest)
        copied.append(dest)
    return copied


class TestTwoPhaseScan:
    def test_scan_dir_metadata_basic(self, tmp_path):
        """scan_dir_metadata should return (size, mtime) for audio files and skip non-audio/sidecars."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        _copy_fixture_mp3s(music_dir, count=2)

        # Non-audio file
        (music_dir / "notes.txt").write_text("not audio")

        # AppleDouble sidecar
        (music_dir / "._song.mp3").write_text("sidecar")

        # __MACOSX directory
        macosx_dir = music_dir / "__MACOSX"
        macosx_dir.mkdir()
        (macosx_dir / "hidden.mp3").write_text("hidden")

        scanner = FileScanner(use_multiprocessing=False)
        metadata = scanner.scan_dir_metadata(str(music_dir))

        assert len(metadata) == 2
        for path, (size, mtime) in metadata.items():
            assert path.endswith(".mp3")
            assert not Path(path).name.startswith("._")
            assert "__MACOSX" not in path
            assert size > 0
            assert mtime > 0

    def test_update_database_skips_tag_reading_when_unchanged(self, tmp_path):
        """When files are unchanged, update_database should NOT read any audio tags."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        _copy_fixture_mp3s(music_dir, count=3)

        db = Database()
        db.add_dir(str(music_dir))
        db.generate_database(parallel=False)

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        # Re-read database
        db2 = Database.read(str(db_dir))

        # Spy on add_files
        with patch.object(
            db2._scanner, "add_files", wraps=db2._scanner.add_files
        ) as mock_add_files:
            stats = db2.update_database(str(music_dir), parallel=False)

            # add_files should not have been called because no files were added or modified
            mock_add_files.assert_not_called()

        assert stats["unchanged"] == 3
        assert stats["added"] == 0
        assert stats["modified"] == 0
        assert stats["deleted"] == 0

    def test_update_database_reads_tags_only_for_new_file(self, tmp_path):
        """When 1 file is added, update_database should only read tags for that new file."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        _copy_fixture_mp3s(music_dir, count=2)

        db = Database()
        db.add_dir(str(music_dir))
        db.generate_database(parallel=False)

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        # Add 3rd file
        all_mp3s = sorted(TEST_DATA_DIR.glob("**/*.mp3"))
        third_file = all_mp3s[2]
        new_file = music_dir / third_file.name
        shutil.copy(third_file, new_file)

        db2 = Database.read(str(db_dir))

        with patch.object(
            db2._scanner, "add_files", wraps=db2._scanner.add_files
        ) as mock_add_files:
            stats = db2.update_database(str(music_dir), parallel=False)

            mock_add_files.assert_called_once()
            call_files = mock_add_files.call_args[0][0]
            assert len(call_files) == 1
            assert str(new_file.resolve()) == str(Path(call_files[0]).resolve())

        assert stats["unchanged"] == 2
        assert stats["added"] == 1
        assert stats["modified"] == 0
        assert stats["deleted"] == 0

    def test_update_database_reads_tags_only_for_modified_file(self, tmp_path):
        """When 1 file is retagged in place, update_database should only read tags for that file."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        files = _copy_fixture_mp3s(music_dir, count=3)

        db = Database()
        db.add_dir(str(music_dir))
        db.generate_database(parallel=False)

        db_dir = tmp_path / "db"
        db_dir.mkdir()
        db.write(str(db_dir))

        # Modify 1 file's tags and advance mtime
        target = files[0]
        audio = EasyID3(str(target))
        audio["title"] = ["TWO-PHASE-MODIFIED-TITLE"]
        audio.save()
        future = time.time() + 2000
        os.utime(target, (future, future))

        db2 = Database.read(str(db_dir))

        with patch.object(
            db2._scanner, "add_files", wraps=db2._scanner.add_files
        ) as mock_add_files:
            stats = db2.update_database(str(music_dir), parallel=False)

            mock_add_files.assert_called_once()
            call_files = mock_add_files.call_args[0][0]
            assert len(call_files) == 1
            assert str(target.resolve()) == str(Path(call_files[0]).resolve())

        assert stats["unchanged"] == 2
        assert stats["added"] == 0
        assert stats["modified"] == 1
        assert stats["deleted"] == 0
