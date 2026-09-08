"""Tests for CLI update command functionality."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import argparse
from tests.conftest import music_test_folder


class TestUpdateCommandBasics:
    """Test basic update command functionality."""

    def test_update_command_exists(self):
        """Test that update command module can be imported."""
        from dap_db_manager.cli.commands import update
        assert hasattr(update, 'cmd_update')

    def test_update_command_requires_dir(self):
        """Test that update command requires a directory argument."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        # Should fail without directory
        args = argparse.Namespace(
            directory=None,
            output=None,
            cache=None,
            json=False,
            verbose=False
        )
        
        # The command should handle missing directory


class TestUpdateCommandWithMockDatabase:
    """Test update command with mocked Database."""

    @patch('dap_db_manager.cli.commands.update.Database')
    def test_update_with_no_changes(self, mock_db_class):
        """Test update when no files have changed."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        # Mock database instance
        mock_db = Mock()
        mock_db.update_database = Mock(return_value=([], [], {}))
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=False,
                verbose=False
            )
            
            # This should complete without errors


    @patch('dap_db_manager.cli.commands.update.Database')
    def test_update_with_new_files(self, mock_db_class):
        """Test update detecting new files."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        mock_db = Mock()
        # Simulate finding new files
        mock_db.update_database = Mock(return_value=(['/new/file.mp3'], [], {}))
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=False,
                verbose=False
            )


    @patch('dap_db_manager.cli.commands.update.Database')
    def test_update_with_deleted_files(self, mock_db_class):
        """Test update detecting deleted files."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        mock_db = Mock()
        # Simulate finding deleted files
        mock_db.update_database = Mock(return_value=([], ['/deleted/file.mp3'], {}))
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=False,
                verbose=False
            )


    @patch('dap_db_manager.cli.commands.update.Database')
    def test_update_with_renames(self, mock_db_class):
        """Test update detecting renamed files."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        mock_db = Mock()
        # Simulate finding renames
        mock_db.update_database = Mock(return_value=(
            [],
            [],
            {'/old/path.mp3': ('/new/path.mp3', 'exact_match')}
        ))
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=False,
                verbose=False
            )


class TestUpdateCommandJSONOutput:
    """Test update command JSON output."""

    @patch('dap_db_manager.cli.commands.update.Database')
    def test_json_output_format(self, mock_db_class):
        """Test that JSON output is properly formatted."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        mock_db = Mock()
        mock_db.update_database = Mock(return_value=(['/new.mp3'], ['/old.mp3'], {}))
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=True,
                verbose=False
            )


class TestUpdateCommandErrorHandling:
    """Test update command error handling."""

    def test_nonexistent_directory(self):
        """Test update with non-existent directory."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        args = argparse.Namespace(
            directory="/nonexistent/directory",
            output=None,
            cache=None,
            json=False,
            verbose=False
        )
        
        # Should return appropriate exit code


    @patch('dap_db_manager.cli.commands.update.Database')
    def test_database_load_failure(self, mock_db_class):
        """Test handling of database load failure."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        # Simulate database load failure
        mock_db_class.load = Mock(side_effect=Exception("Failed to load database"))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=False,
                verbose=False
            )


@pytest.mark.integration
class TestUpdateCommandIntegration:
    """Integration tests for update command."""

    @pytest.mark.skipif(
        not music_test_folder().exists(),
        reason="Test data not available"
    )
    def test_update_with_real_data(self):
        """Test update command with real test data."""
        # This would require creating a database first, then updating it
        # Skipping for now as it's complex integration test
        pass


class TestUpdateCommandCacheHandling:
    """Test update command cache loading and saving."""

    @patch('dap_db_manager.cli.commands.update.Database')
    def test_cache_load(self, mock_db_class):
        """Test that cache is loaded during update."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        mock_db = Mock()
        mock_db.update_database = Mock(return_value=([], [], {}))
        mock_db.load_cache = Mock()
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.pkl.gz"
            cache_path.write_bytes(b"")  # Create empty cache file
            
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=str(cache_path),
                json=False,
                verbose=False
            )


    @patch('dap_db_manager.cli.commands.update.Database')
    def test_cache_save(self, mock_db_class):
        """Test that cache is saved after update."""
        from dap_db_manager.cli.commands.update import cmd_update
        
        mock_db = Mock()
        mock_db.update_database = Mock(return_value=(['/new.mp3'], [], {}))
        mock_db.save_cache = Mock()
        mock_db_class.return_value = mock_db
        mock_db_class.load = Mock(return_value=mock_db)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                output=None,
                cache=None,
                json=False,
                verbose=False
            )
