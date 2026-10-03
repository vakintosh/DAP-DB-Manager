"""Regression test: mtime must survive a generate -> write -> read round trip.

Root cause: `_assemble_entry` stored `mtime_to_fat(raw_mtime)` directly on the
in-memory `IndexEntry`, but `IndexEntry.to_file` FAT-encodes the in-memory
value again on write (matching the invariant `from_file` relies on: the
in-memory value is always the raw unix-like mtime, FAT encoding happens only
at the serialization boundary). The result was every entry written straight
from `generate` getting its stored mtime double-FAT-encoded into a bogus
timestamp -- silently, since nothing compared it back to the source file's
real mtime.
"""

import os
import shutil
import time

import pytest

from dap_db_manager.database import Database
from dap_db_manager.utils import mtime_to_fat
from tests.conftest import music_test_folder

TEST_DATA_DIR = music_test_folder()
pytestmark = pytest.mark.skipif(
    not TEST_DATA_DIR.exists(), reason="Test data not available"
)


def test_mtime_round_trips_through_generate_write_read(tmp_path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    mp3 = sorted(TEST_DATA_DIR.glob("**/*.mp3"))[0]
    target = music_dir / mp3.name
    shutil.copy(mp3, target)

    # Pin the mtime to something unambiguous and FAT-representable.
    fixed = time.mktime((2020, 6, 15, 12, 30, 0, -1, -1, -1))
    os.utime(target, (fixed, fixed))
    expected_fat = mtime_to_fat(fixed)

    db = Database()
    db.add_dir(str(music_dir), recursive=True)
    db.generate_database(callback=lambda *a, **k: None, parallel=False)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db.write(str(db_dir))

    db2 = Database.read(str(db_dir), callback=lambda *a, **k: None)
    entries = [e for e in db2.index.entries if not e.is_deleted()]
    assert len(entries) == 1
    stored_fat = mtime_to_fat(entries[0]["mtime"])

    assert stored_fat == expected_fat, (
        "mtime was corrupted across a generate -> write -> read round trip "
        f"(expected FAT {expected_fat:#x}, got {stored_fat:#x}) -- this is "
        "the double-FAT-encoding bug in generator._assemble_entry"
    )
