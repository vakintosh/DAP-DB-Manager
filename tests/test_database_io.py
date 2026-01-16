"""Tests for database I/O operations - Fixed API."""

import pytest
import tempfile
from pathlib import Path
from dap_db_manager.database.io import DatabaseIO
from dap_db_manager.indexfile import IndexFile
from dap_db_manager.tagging.tag.tagfile import TagFile
from dap_db_manager.constants import FILE_TAGS


class TestDatabaseIOWrite:
    """Test database writing operations."""

    def test_write_to_directory(self, tmp_path):
        """Test writing database to a directory."""
        # Create tagfiles and index
        tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        index = IndexFile()
        
        # Write using class method
        DatabaseIO.write(tagfiles, index, str(tmp_path))
        
        # Should create database files
        assert (tmp_path / "database_idx.tcd").exists()

    def test_write_with_parallel(self, tmp_path):
        """Test parallel writing."""
        tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        index = IndexFile()
        
        DatabaseIO.write(tagfiles, index, str(tmp_path), use_parallel=True)
        assert (tmp_path / "database_idx.tcd").exists()

    def test_write_sequential(self, tmp_path):
        """Test sequential writing."""
        tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        index = IndexFile()
        
        DatabaseIO.write(tagfiles, index, str(tmp_path), use_parallel=False)
        assert (tmp_path / "database_idx.tcd").exists()


class TestDatabaseIORead:
    """Test database reading operations."""

    def test_read_from_directory(self, tmp_path):
        """Test reading database from directory."""
        # First write a database
        tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        index = IndexFile()
        DatabaseIO.write(tagfiles, index, str(tmp_path))
        
        # Now read it back
        loaded_tagfiles, loaded_index = DatabaseIO.read(str(tmp_path))
        
        assert loaded_tagfiles is not None
        assert loaded_index is not None
        assert isinstance(loaded_tagfiles, dict)

    def test_read_nonexistent_directory(self):
        """Test reading from non-existent directory."""
        with pytest.raises((FileNotFoundError, OSError)):
            DatabaseIO.read("/nonexistent/directory")


class TestDatabaseIORoundTrip:
    """Test write/read round-trip operations."""

    def test_write_read_roundtrip(self, tmp_path):
        """Test that write followed by read preserves structure."""
        # Create database
        original_tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        original_index = IndexFile()
        
        # Write
        DatabaseIO.write(original_tagfiles, original_index, str(tmp_path))
        
        # Read back
        loaded_tagfiles, loaded_index = DatabaseIO.read(str(tmp_path))
        
        # Verify structure
        assert set(loaded_tagfiles.keys()) == set(original_tagfiles.keys())


class TestDatabaseIOCallbacks:
    """Test database I/O callback functionality."""

    def test_write_with_callback(self, tmp_path):
        """Test write with callback function."""
        tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        index = IndexFile()
        
        callback_calls = []
        def test_callback(*args, **kwargs):
            callback_calls.append((args, kwargs))
        
        DatabaseIO.write(tagfiles, index, str(tmp_path), callback=test_callback)
        
        # Should have invoked callback
        assert len(callback_calls) > 0


class TestDatabaseIOOptimizations:
    """Test I/O optimization features."""

    def test_write_optimized_alias(self, tmp_path):
        """Test write_optimized method."""
        tagfiles = {tag: TagFile(tag) for tag in FILE_TAGS}
        index = IndexFile()
        
        DatabaseIO.write_optimized(tagfiles, index, str(tmp_path))
        assert (tmp_path / "database_idx.tcd").exists()
