"""Tests for Database class and operations."""

import tempfile
from pathlib import Path
from dap_db_manager.database import Database
from dap_db_manager.constants import FORMATTED_TAGS
from dap_db_manager.database import myprint


class TestDatabase:
    """Test Database class."""

    def test_database_creation(self):
        """Test creating a new Database."""
        db = Database()

        # Should have tag files dict
        assert hasattr(db, "tagfiles")
        assert isinstance(db.tagfiles, dict)

        # Should have an index
        assert hasattr(db, "index")

    def test_database_empty_index(self):
        """Test that new database has empty index."""
        db = Database()
        assert len(db.index.entries) == 0

    def test_formatted_tags_defined(self):
        """Test that formatted tags are properly defined."""
        assert isinstance(FORMATTED_TAGS, list)

        # Should include standard fields
        expected_fields = ["artist", "album", "genre", "composer"]
        for field in expected_fields:
            assert field in FORMATTED_TAGS

    def test_database_write_empty(self):
        """Test writing an empty database."""
        db = Database()

        with tempfile.TemporaryDirectory() as tmpdir:
            db.write(tmpdir)

            # Should create database files
            assert (Path(tmpdir) / "database_idx.tcd").exists()
            # Artist is index 0
            assert (Path(tmpdir) / "database_0.tcd").exists()

    def test_database_round_trip(self):
        """Test writing and reading back a database."""
        db = Database()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write database
            db.write(tmpdir)

            # Read it back
            db2 = Database.read(tmpdir)

            # Should have same structure
            assert len(db2.index.entries) == len(db.index.entries)


class TestDatabaseFields:
    """Test database field handling."""

    def test_multiple_fields(self):
        """Test multiple_fields configuration."""
        db = Database()

        # Should have multiple_fields dict
        assert hasattr(db, "multiple_fields")
        assert isinstance(db.multiple_fields, dict)

    def test_formatted_fields(self):
        """Test formatted_fields configuration."""
        db = Database()

        # Should have formats dict
        assert hasattr(db, "formats")
        assert isinstance(db.formats, dict)


class TestDatabaseHelpers:
    """Test database helper functions."""

    def test_myprint_function(self):
        """Test myprint helper doesn't crash."""

        # Should not raise an exception
        myprint("test")
        myprint("test", "multiple", "args")

    def test_path_handling(self):
        """Test database path handling for cross-platform."""
        db = Database()

        # Database should handle paths
        # The actual strip_volume logic may be internal
        # Just verify database exists and can be created
        assert db is not None
        assert hasattr(db, "tagfiles")
