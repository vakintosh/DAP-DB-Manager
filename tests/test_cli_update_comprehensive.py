"""Comprehensive tests for the update CLI command."""

import sys
import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock, ANY
import argparse
import json
import time

from dap_db_manager.cli.commands.update import cmd_update
from dap_db_manager.cli.utils import ExitCode

@pytest.fixture
def mock_args(tmp_path):
    """Create basic mock arguments."""
    return argparse.Namespace(
        db_dir=str(tmp_path / "db"),
        music_dir=str(tmp_path / "music"),
        output=None,
        json=False,
        dap_root=None,
        verbose=False
    )

@pytest.fixture
def mock_db_class():
    """Mock the Database class."""
    with patch("dap_db_manager.cli.commands.update.Database") as mock:
        db_instance = mock.read.return_value
        db_instance.index.count = 500
        db_instance.update_database.return_value = {
            "added": 10,
            "renamed": 5,
            "deleted": 2,
            "unchanged": 480,
            "failed": 0,
            "final_active": 490,
            "final_deleted": 10
        }
        db_instance.config = Mock()
        db_instance.config.get_mount_notation.return_value = None
        # Mock paths
        db_instance.paths = ["file1", "file2"]
        yield mock

@pytest.fixture
def mock_config_class():
    """Mock the Config class."""
    with patch("dap_db_manager.config.Config") as mock:
        yield mock

class TestUpdatePathValidation:
    """Tests for path validation logic."""
    
    def test_db_path_not_exists(self, mock_args):
        """Test exit code when database path does not exist."""
        mock_args.db_dir = "/nonexistent"
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_db_path_not_dir(self, tmp_path, mock_args):
        """Test exit code when database path is a file."""
        f = tmp_path / "file"
        f.touch()
        mock_args.db_dir = str(f)
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_music_path_not_exists(self, tmp_path, mock_args):
        """Test exit code when music path does not exist."""
        # Create valid db dir first
        Path(mock_args.db_dir).mkdir(parents=True)
        
        mock_args.music_dir = "/nonexistent"
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_music_path_not_dir(self, tmp_path, mock_args):
        """Test exit code when music path is a file."""
        Path(mock_args.db_dir).mkdir(parents=True)
        
        f = tmp_path / "music_file"
        f.touch()
        mock_args.music_dir = str(f)
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_dap_root_validation(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test DAP root validation."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        # Valid case
        mock_args.dap_root = tmp_path
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        # Invalid case (music not under root)
        mock_args.dap_root = Path("/other/root")
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

class TestUpdateConfiguration:
    """Tests for configuration handling."""

    def test_auto_detect_mount(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test auto detection of mount notation."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        config = mock_config_class.return_value
        config.is_mount_notation_configured.return_value = False
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        config.auto_detect_mount_notation.assert_called_once()

    def test_db_loading_failure(self, tmp_path, mock_args, mock_db_class):
        """Test handling of database loading failure."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        mock_db_class.read.side_effect = Exception("Read error")
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.DATA_ERROR

class TestUpdateExecution:
    """Tests for update execution flow."""

    def setUp(self):
        self.tmp_path = Path("/tmp/test_update")
        self.tmp_path.mkdir(exist_ok=True)

    def test_successful_update(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test successful update execution."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db = mock_db_class.read.return_value
        db.update_database.assert_called_with(mock_args.music_dir, callback=ANY)
        db.write.assert_called_with(mock_args.db_dir, callback=ANY)

    def test_update_failure(self, tmp_path, mock_args, mock_db_class):
        """Test handling of update failure."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        db = mock_db_class.read.return_value
        db.update_database.side_effect = Exception("Update error")
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.GENERATION_FAILED

    def test_write_failure(self, tmp_path, mock_args, mock_db_class):
        """Test handling of write failure."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        db = mock_db_class.read.return_value
        db.write.side_effect = Exception("Write error")
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.WRITE_FAILED

    def test_custom_output_dir(self, tmp_path, mock_args, mock_db_class):
        """Test writing to custom output directory."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        output_dir = tmp_path / "output"
        mock_args.output = str(output_dir)
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db = mock_db_class.read.return_value
        db.write.assert_called_with(str(output_dir), callback=ANY)

class TestUpdateCallback:
    """Tests for progress callback handling."""
    
    def test_callback_logic(self, tmp_path, mock_args, mock_db_class):
        """Test the callback function logic via side_effect/mock."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        # Capture the callback passed to update_database
        def capture_callback(*args, **kwargs):
            callback = kwargs.get('callback')
            if callback:
                # Test diverse callback signatures
                callback("Updating description")
                callback(10) # Set total
                callback(5, 100) # Current, Total
                callback(1) # Advance
            return {
                "added": 0, "renamed": 0, "deleted": 0, 
                "unchanged": 0, "failed": 0,
                "final_active": 0, "final_deleted": 0
            }
            
        db = mock_db_class.read.return_value
        db.update_database.side_effect = capture_callback
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS

class TestUpdateOutput:
    """Tests for JSON and Console output."""

    def test_json_output(self, tmp_path, mock_args, mock_db_class, capsys):
        """Test JSON output format."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        mock_args.json = True
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        
        assert "original_entries" in data
        assert "final_entries" in data
        assert "added" in data
        assert "renamed" in data
        assert data["renamed"] == 5

    def test_console_summary(self, tmp_path, mock_args, mock_db_class, capsys):
        """Test console summary output (implicit verify via success)."""
        Path(mock_args.db_dir).mkdir(parents=True)
        Path(mock_args.music_dir).mkdir(parents=True)
        
        with pytest.raises(SystemExit) as exc:
            cmd_update(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        captured = capsys.readouterr()
        assert "Update Summary" in captured.out
        assert "Renamed/Moved" in captured.out
