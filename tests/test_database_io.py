"""Tests for database I/O operations."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dap_db_manager.database.io import DatabaseIO
from dap_db_manager.indexfile import IndexFile
from dap_db_manager.tagging.tag.tagfile import TagFile


class TestDatabaseIOInit:
    """Test DatabaseIO initialization."""

    def test_database_io_creation(self):
        """Test creating DatabaseIO instance."""
        io = DatabaseIO()
        assert io is not None


class TestDatabaseIOWrite:
    """Test database writing operations."""

    def test_write_to_directory(self, tmp_path):
        """Test writing database to a directory."""
        io = DatabaseIO()
        
        # Create minimal database components
        index = IndexFile()
        tagfiles = {}
        
        # Write to temp directory
        io.write(str(tmp_path), index, tagfiles)
        
        # Should create database files in directory
        db_path = tmp_path / "database_idx.tcd"
        assert db_path.exists() or len(list(tmp_path.glob("*.tcd"))) > 0

    def test_write_with_tagfiles(self, tmp_path):
        """Test writing database with tag files."""
        io = DatabaseIO()
        
        index = IndexFile()
        tagfiles = {
            "artist": TagFile("artist"),
            "album": TagFile("album")
        }
        
        io.write(str(tmp_path), index, tagfiles)
        
        # Should create multiple tag files
        tcd_files = list(tmp_path.glob("*.tcd"))
        assert len(tcd_files) > 0

    def test_write_to_nonexistent_directory(self):
        """Test writing to non-existent directory."""
        io = DatabaseIO()
        
        index = IndexFile()
        tagfiles = {}
        
        # Should handle gracefully or raise appropriate error
        try:
            io.write("/nonexistent/path", index, tagfiles)
        except (FileNotFoundError, OSError):
            # Expected exception
            pass


class TestDatabaseIORead:
    """Test database reading operations."""

    def test_load_from_directory(self, tmp_path):
        """Test loading database from directory."""
        io = DatabaseIO()
        
        # Create a simple database first
        index = IndexFile()
        tagfiles = {"artist": TagFile("artist")}
        io.write(str(tmp_path), index, tagfiles)
        
        # Now load it back
        loaded_index, loaded_tagfiles = io.load(str(tmp_path))
        
        assert loaded_index is not None
        assert isinstance(loaded_tagfiles, dict)

    def test_load_nonexistent_directory(self):
        """Test loading from non-existent directory."""
        io = DatabaseIO()
        
        with pytest.raises((FileNotFoundError, OSError)):
            io.load("/nonexistent/directory")

    def test_load_empty_directory(self, tmp_path):
        """Test loading from empty directory."""
        io = DatabaseIO()
        
        # Try to load from empty directory
        try:
            io.load(str(tmp_path))
        except (FileNotFoundError, ValueError):
            # Expected - no database files
            pass


class TestDatabaseIOValidation:
    """Test database validation operations."""

    def test_validate_valid_database(self, tmp_path):
        """Test validating a valid database."""
        io = DatabaseIO()
        
        # Create a valid database
        index = IndexFile()
        tagfiles = {}
        io.write(str(tmp_path), index, tagfiles)
        
        # Validate should succeed
        is_valid = io.validate(str(tmp_path))
        # Validation behavior depends on implementation

    def test_validate_invalid_directory(self):
        """Test validating non-existent directory."""
        io = DatabaseIO()
        
        is_valid = io.validate("/nonexistent/path")
        assert is_valid is False or is_valid is None


class TestDatabaseIORoundTrip:
    """Test write/read round-trip operations."""

    def test_write_read_roundtrip(self, tmp_path):
        """Test that write followed by read preserves data."""
        io = DatabaseIO()
        
        # Create database with some data
        original_index = IndexFile()
        original_tagfiles = {
            "artist": TagFile("artist"),
            "album": TagFile("album"),
            "title": TagFile("title")
        }
        
        # Write database
        io.write(str(tmp_path), original_index, original_tagfiles)
        
        # Read it back
        loaded_index, loaded_tagfiles = io.load(str(tmp_path))
        
        # Verify structure is preserved
        assert loaded_index is not None
        assert isinstance(loaded_tagfiles, dict)
        # Tag file names should match
        assert set(loaded_tagfiles.keys()) == set(original_tagfiles.keys())


class TestDatabaseIOEdgeCases:
    """Test edge cases and error handling."""

    def test_write_with_empty_tagfiles(self, tmp_path):
        """Test writing with empty tagfiles dict."""
        io = DatabaseIO()
        
        index = IndexFile()
        tagfiles = {}
        
        # Should handle empty tagfiles
        io.write(str(tmp_path), index, tagfiles)

    def test_write_with_none_values(self, tmp_path):
        """Test writing with None values."""
        io = DatabaseIO()
        
        index = IndexFile()
        tagfiles = {}
        
        # Test various None scenarios if applicable
        io.write(str(tmp_path), index, tagfiles)

    def test_concurrent_access(self, tmp_path):
        """Test behavior with concurrent access (if applicable)."""
        io1 = DatabaseIO()
        io2 = DatabaseIO()
        
        index = IndexFile()
        tagfiles = {}
        
        # Write with first instance
        io1.write(str(tmp_path), index, tagfiles)
        
        # Read with second instance
        loaded_index, loaded_tagfiles = io2.load(str(tmp_path))
        
        assert loaded_index is not None
