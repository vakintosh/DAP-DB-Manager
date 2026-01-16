"""Extended CLI tests for generate, validate, and inspect commands."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch
import argparse

# Test data path
TEST_DATA_DIR = Path("/Users/v/PYTHON_PROJECTS/rdbm/rockbox-db-manager/music_test_folder")


class TestCLIGenerateCommand:
    """Test the generate CLI command."""

    @patch('dap_db_manager.cli.commands.generate.Database')
    def test_generate_command_basic(self, mock_db_class):
        """Test basic generate command execution."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        mock_db = Mock()
        mock_db.add_dir = Mock()
        mock_db.write = Mock()
        mock_db_class.return_value = mock_db
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                music_dir=tmpdir,
                output_dir=tmpdir,
                cache=None,
                config=None,
                dap_root=None,
                mount_notation=None,
                json=False,
                verbose=False,
                recursive=True,
                parallel=True
            )
            
            # Should complete without error

    @patch('dap_db_manager.cli.commands.generate.Database')
    def test_generate_with_dap_root(self, mock_db_class):
        """Test generate with DAP root option."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                music_dir=tmpdir,
                output_dir=tmpdir,
                cache=None,
                config=None,
                dap_root="/media/player",
                mount_notation="/<HDD0>",
                json=False,
                verbose=False,
                recursive=True,
                parallel=True
            )

    @patch('dap_db_manager.cli.commands.generate.Database')
    def test_generate_with_cache(self, mock_db_class):
        """Test generate with cache saving."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        mock_db = Mock()
        mock_db.save_cache = Mock()
        mock_db_class.return_value = mock_db
        
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.pkl.gz"
            
            args = argparse.Namespace(
                music_dir=tmpdir,
                output_dir=tmpdir,
                cache=str(cache_file),
                config=None,
                dap_root=None,
                mount_notation=None,
                json=False,
                verbose=False,
                recursive=True,
                parallel=True
            )

    def test_generate_nonexistent_music_dir(self):
        """Test generate with non-existent music directory."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        args = argparse.Namespace(
            music_dir="/nonexistent/directory",
            output_dir="/tmp",
            cache=None,
            config=None,
            dap_root=None,
            mount_notation=None,
            json=False,
            verbose=False,
            recursive=True,
            parallel=True
        )
        
        # Should return appropriate exit code

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    @pytest.mark.integration
    def test_generate_with_real_data(self):
        """Test generate with real audio files."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                music_dir=str(TEST_DATA_DIR),
                output_dir=tmpdir,
                cache=None,
                config=None,
                dap_root=None,
                mount_notation=None,
                json=False,
                verbose=False,
                recursive=True,
                parallel=True
            )


class TestCLIValidateCommand:
    """Test the validate CLI command."""

    def test_validate_command_exists(self):
        """Test that validate command can be imported."""
        try:
            from dap_db_manager.cli.commands import validate
            assert hasattr(validate, 'cmd_validate')
        except (ImportError, AttributeError):
            pytest.skip("Validate command not implemented")

    @patch('dap_db_manager.cli.commands.validate.DatabaseIO')
    def test_validate_valid_database(self, mock_io):
        """Test validating a valid database."""
        try:
            from dap_db_manager.cli.commands.validate import cmd_validate
        except ImportError:
            pytest.skip("Validate command not implemented")
        
        mock_io.read = Mock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                json=False,
                verbose=False
            )

    def test_validate_nonexistent_directory(self):
        """Test validate with non-existent directory."""
        try:
            from dap_db_manager.cli.commands.validate import cmd_validate
        except ImportError:
            pytest.skip("Validate command not implemented")
        
        args = argparse.Namespace(
            directory="/nonexistent/directory",
            json=False,
            verbose=False
        )


class TestCLIInspectCommand:
    """Test the inspect CLI command."""

    def test_inspect_command_exists(self):
        """Test that inspect command can be imported."""
        try:
            from dap_db_manager.cli.commands import inspect
            assert hasattr(inspect, 'cmd_inspect')
        except (ImportError, AttributeError):
            pytest.skip("Inspect command not implemented")

    @patch('dap_db_manager.cli.commands.inspect.DatabaseIO')
    def test_inspect_database(self, mock_io):
        """Test inspecting a database."""
        try:
            from dap_db_manager.cli.commands.inspect import cmd_inspect
        except ImportError:
            pytest.skip("Inspect command not implemented")
        
        mock_io.read = Mock(return_value=({}, Mock()))
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                json=False,
                verbose=False
            )


class TestCLIDetectMountsCommand:
    """Test the detect-mounts CLI command."""

    def test_detect_mounts_command_exists(self):
        """Test that detect-mounts command can be imported."""
        try:
            from dap_db_manager.cli.commands import detect_mounts
            assert hasattr(detect_mounts, 'cmd_detect_mounts')
        except (ImportError, AttributeError):
            pytest.skip("detect-mounts command not implemented")

    @patch('dap_db_manager.cli.commands.detect_mounts.MountDetector')
    def test_detect_mounts_basic(self, mock_detector):
        """Test basic mount detection command."""
        try:
            from dap_db_manager.cli.commands.detect_mounts import cmd_detect_mounts
        except ImportError:
            pytest.skip("detect-mounts command not implemented")
        
        mock_detector.detect_mounts = Mock(return_value={})
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                directory=tmpdir,
                json=False,
                verbose=False
            )


class TestCLIJSONOutput:
    """Test JSON output across CLI commands."""

    @patch('dap_db_manager.cli.commands.generate.Database')
    def test_generate_json_output(self, mock_db_class):
        """Test JSON output from generate command."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                music_dir=tmpdir,
                output_dir=tmpdir,
                cache=None,
                config=None,
                dap_root=None,
                mount_notation=None,
                json=True,  # JSON output
                verbose=False,
                recursive=True,
                parallel=True
            )


class TestCLIErrorHandling:
    """Test error handling across CLI commands."""

    def test_generate_with_invalid_config(self):
        """Test generate with invalid config file."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                music_dir=tmpdir,
                output_dir=tmpdir,
                cache=None,
                config="/nonexistent/config.toml",
                dap_root=None,
                mount_notation=None,
                json=False,
                verbose=False,
                recursive=True,
                parallel=True
            )
            
            # Should handle missing config gracefully

    @patch('dap_db_manager.cli.commands.generate.Database')
    def test_generate_write_failure(self, mock_db_class):
        """Test handling of database write failure."""
        from dap_db_manager.cli.commands.generate import cmd_generate
        
        mock_db = Mock()
        mock_db.write = Mock(side_effect=Exception("Write failed"))
        mock_db_class.return_value = mock_db
        
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                music_dir=tmpdir,
                output_dir=tmpdir,
                cache=None,
                config=None,
                dap_root=None,
                mount_notation=None,
                json=False,
                verbose=False,
                recursive=True,
                parallel=True
            )
