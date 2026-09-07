
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from dap_db_manager.database.io import DatabaseIO
from dap_db_manager.constants import FILE_TAGS, FILE_TAG_INDICES
import sys

# Constants for testing
TEST_FIELDS = FILE_TAGS
TEST_INDICES = FILE_TAG_INDICES

class TestDatabaseIO:
    """Test suite for DatabaseIO."""

    @pytest.fixture
    def mock_objects(self):
        """Create mock tagfiles and index objects."""
        tagfiles = {}
        for field in TEST_FIELDS:
            mock_tf = MagicMock()
            mock_tf.write = MagicMock()
            tagfiles[field] = mock_tf
            
        mock_index = MagicMock()
        mock_index.write = MagicMock()
        
        return tagfiles, mock_index

    def test_write_sequential(self, tmp_path, mock_objects):
        """Test sequential writing logic."""
        tagfiles, index = mock_objects
        callback = MagicMock()
        
        DatabaseIO.write(tagfiles, index, out_dir=str(tmp_path), callback=callback, use_parallel=False)
        
        # Verify tagfiles write calls
        for i, field in enumerate(TEST_FIELDS):
            file_num = TEST_INDICES[i]
            expected_path = tmp_path / f"database_{file_num}.tcd"
            tagfiles[field].write.assert_called_with(str(expected_path), buffer_size=DatabaseIO.BUFFER_SIZE)
            
        # Verify index write call
        expected_idx_path = tmp_path / "database_idx.tcd"
        index.write.assert_called_with(str(expected_idx_path), buffer_size=DatabaseIO.BUFFER_SIZE)
        
        # Check callbacks
        assert callback.call_count >= len(TEST_FIELDS) * 2 + 2 # start/done calls

    def test_write_parallel(self, tmp_path, mock_objects):
        """Test parallel writing logic."""
        tagfiles, index = mock_objects
        callback = MagicMock()
        
        # Force sequential execution in ThreadPoolExecutor for deterministic testing?
        # Or just verify it works.
        DatabaseIO.write(tagfiles, index, out_dir=str(tmp_path), callback=callback, use_parallel=True)
        
        # Verify writes occurred
        for i, field in enumerate(TEST_FIELDS):
            file_num = TEST_INDICES[i]
            expected_path = tmp_path / f"database_{file_num}.tcd"
            # Since threads are involved, we can't easily assert order, but calls should happen
            tagfiles[field].write.assert_called_with(str(expected_path), buffer_size=DatabaseIO.BUFFER_SIZE)
            
        # Index written last?
        # Ideally index.write should be called after tagfiles writes.
        # But mocking ThreadPoolExecutor is hard.
        # We trust the logic that index write is outside the With block.
        expected_idx_path = tmp_path / "database_idx.tcd"
        index.write.assert_called_with(str(expected_idx_path), buffer_size=DatabaseIO.BUFFER_SIZE)

    def test_read(self, tmp_path):
        """Test reading database files."""
        # Create dummy files
        for i in TEST_INDICES:
            (tmp_path / f"database_{i}.tcd").touch()
        (tmp_path / "database_idx.tcd").touch()
        
        # Mock TagFile.read and IndexFile.read
        with patch("dap_db_manager.database.io.TagFile.read") as mock_tf_read, \
             patch("dap_db_manager.database.io.IndexFile.read") as mock_idx_read:
             
             mock_tf_read.return_value = "MockTagFile"
             mock_idx_read.return_value = "MockIndex"
             
             callback = MagicMock()
             tagfiles, index = DatabaseIO.read(in_dir=str(tmp_path), callback=callback)
             
             # Check results
             assert len(tagfiles) == len(TEST_FIELDS)
             assert index == "MockIndex"
             
             # Check calls
             assert mock_tf_read.call_count == len(TEST_FIELDS)
             mock_idx_read.assert_called_once()

    def test_callback_helper(self, capsys):
        """Test the built-in cleanup print helper."""
        from dap_db_manager.database.io import myprint
        
        myprint("Hello", "World", sep="-", end="!")
        captured = capsys.readouterr()
        assert captured.out == "Hello-World!"

    def test_write_optimized_alias(self, tmp_path, mock_objects):
        """Test write_optimized alias."""
        from unittest.mock import ANY
        tagfiles, index = mock_objects
        with patch.object(DatabaseIO, "write") as mock_write:
            DatabaseIO.write_optimized(tagfiles, index, out_dir=str(tmp_path))
            mock_write.assert_called_with(tagfiles, index, str(tmp_path), ANY, use_parallel=True)

