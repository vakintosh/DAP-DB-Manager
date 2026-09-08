"""Comprehensive tests for the generate CLI command."""

import sys
import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock, ANY
import argparse
import json
import time

from dap_db_manager.cli.commands.generate import cmd_generate
from dap_db_manager.cli.utils import ExitCode
from dap_db_manager.constants import FILE_TAGS

@pytest.fixture
def mock_args(tmp_path):
    """Create basic mock arguments."""
    return argparse.Namespace(
        music_dir=str(tmp_path),
        output=None,
        json=False,
        save_tags=False,
        load_tags=False,
        config=None,
        no_parallel=False,
        workers=None,
        verbose=False
    )

@pytest.fixture
def mock_db_class():
    """Mock the Database class."""
    with patch("dap_db_manager.cli.commands.generate.Database") as mock:
        db_instance = mock.return_value
        db_instance.index.count = 500
        db_instance.paths = ["file1", "file2"]
        db_instance.failed = []
        db_instance.tagfiles = {tag: Mock(entries=[1]*10) for tag in FILE_TAGS}
        db_instance.config = Mock()
        db_instance.config.get_mount_notation.return_value = None
        yield mock

@pytest.fixture
def mock_config_class():
    """Mock the Config class."""
    with patch("dap_db_manager.cli.commands.generate.Config") as mock:
        yield mock

@pytest.fixture
def mock_tag_cache_class():
    """Mock the TagCache class."""
    with patch("dap_db_manager.cli.commands.generate.TagCache") as mock:
        mock.get_cache.return_value = {}
        yield mock

class TestGeneratePathValidation:
    """Tests for path validation logic."""

    def test_music_path_does_not_exist(self, mock_args):
        """Test exit code when music path does not exist."""
        mock_args.music_dir = "/nonexistent/path/to/music"
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_music_path_is_not_dir(self, tmp_path, mock_args):
        """Test exit code when music path is a file."""
        file_path = tmp_path / "test.file"
        file_path.touch()
        mock_args.music_dir = str(file_path)
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_dap_root_validation_success(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test successful validation when music dir is inside dap root."""
        dap_root = tmp_path
        music_dir = tmp_path / "Music"
        music_dir.mkdir()
        
        mock_args.music_dir = str(music_dir)
        mock_args.dap_root = dap_root
        
        # Should raise SystemExit with SUCCESS code
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        # Verify Database initialized with dap_root
        mock_db_class.assert_called_with(
            config=mock_config_class.return_value,
            dap_root=str(dap_root),
            stats_preserver=None,  # no existing database in the temp output dir
        )

    def test_dap_root_validation_failure(self, tmp_path, mock_args):
        """Test failure when music dir is NOT inside dap root."""
        dap_root = tmp_path / "DAP"
        dap_root.mkdir()
        music_dir = tmp_path / "Other" / "Music"
        music_dir.mkdir(parents=True)
        
        mock_args.music_dir = str(music_dir)
        mock_args.dap_root = dap_root
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.INVALID_INPUT

    def test_json_output_invalid_input(self, capsys, mock_args):
        """Test JSON error output for invalid input."""
        mock_args.json = True
        mock_args.music_dir = "/nonexistent"
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
            
        assert exc.value.code == ExitCode.INVALID_INPUT
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"
        assert data["error"] == "invalid_input"


class TestGenerateConfiguration:
    """Tests for configuration handling."""

    def test_auto_detect_mount_notation(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test that mount notation is auto-detected on first run."""
        config_instance = mock_config_class.return_value
        config_instance.is_mount_notation_configured.return_value = False
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        config_instance.auto_detect_mount_notation.assert_called_once()

    def test_load_custom_config(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test loading a custom configuration file."""
        config_file = tmp_path / "custom_config.toml"
        config_file.touch()
        mock_args.config = str(config_file)
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        config_instance = mock_config_class.return_value
        assert config_instance.load.called

    def test_custom_config_not_found(self, mock_args):
        """Test error when custom config file doesn't exist."""
        mock_args.config = "/nonexistent/config.toml"
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.INVALID_CONFIG

    def test_apply_format_settings(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test that format settings from config are applied to DB."""
        config_file = tmp_path / "config.toml"
        config_file.touch()
        mock_args.config = str(config_file)
        
        config_instance = mock_config_class.return_value
        config_instance.get_format.return_value = "%artist%"
        config_instance.get_sort_format.return_value = "%sort%"
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db_instance = mock_db_class.return_value
        assert db_instance.set_format.called

    def test_parallel_flags(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test parallel processing flags are passed to DB."""
        mock_args.no_parallel = True
        mock_args.workers = 4
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db_instance = mock_db_class.return_value
        assert db_instance.use_parallel is False
        assert db_instance.max_workers == 4


class TestGenerateCache:
    """Tests for cache management."""

    def test_load_tags_existing(self, tmp_path, mock_args, mock_db_class, mock_config_class, mock_tag_cache_class):
        """Test loading tags from existing cache file."""
        cache_file = tmp_path / "cache.pkl"
        cache_file.touch()
        mock_args.load_tags = str(cache_file)
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db_instance = mock_db_class.return_value
        db_instance.load_tags.assert_called_with(str(cache_file), callback=ANY)

    def test_load_tags_gz_fallback(self, tmp_path, mock_args, mock_db_class, mock_config_class, mock_tag_cache_class):
        """Test fallback to .gz cache file."""
        cache_file = tmp_path / "cache.pkl" # doesn't exist
        cache_file_gz = tmp_path / "cache.pkl.gz"
        cache_file_gz.touch()
        mock_args.load_tags = str(cache_file)
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db_instance = mock_db_class.return_value
        db_instance.load_tags.assert_called_with(str(cache_file_gz), callback=ANY)

    def test_clear_stale_cache(self, tmp_path, mock_args, mock_db_class, mock_config_class, mock_tag_cache_class):
        """Test stale cache is cleared when not loading tags."""
        mock_args.load_tags = None
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        mock_tag_cache_class.clear.assert_called_once()

    def test_save_tags(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test saving tags to cache."""
        save_path = tmp_path / "save.pkl"
        mock_args.save_tags = str(save_path)
        
        db_instance = mock_db_class.return_value
        # Mock save_tags return value
        db_instance.save_tags.return_value = (str(save_path), 100)
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.SUCCESS
        
        db_instance.save_tags.assert_called()


class TestGenerateExecution:
    """Tests for the main execution flow (scan, generate, write)."""

    def test_scan_failure(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test handling of scan exception."""
        db_instance = mock_db_class.return_value
        db_instance.add_dir.side_effect = Exception("Scan error")
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.DATA_ERROR

    def test_no_files_found(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test when no files are found."""
        db_instance = mock_db_class.return_value
        db_instance.paths = [] # No files
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.DATA_ERROR

    def test_generation_failure(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test handling of generation exception."""
        db_instance = mock_db_class.return_value
        db_instance.generate_database.side_effect = Exception("Gen error")
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.GENERATION_FAILED

    def test_output_directory_creation_fail(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test failure to create output directory."""
        # Use a read-only directory or mock Path.mkdir
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Denied")):
            with pytest.raises(SystemExit) as exc:
                cmd_generate(mock_args)
            assert exc.value.code == ExitCode.INVALID_INPUT

    def test_write_failure(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test handling of database write failure."""
        db_instance = mock_db_class.return_value
        db_instance.write.side_effect = Exception("Write error")
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.WRITE_FAILED

    def test_high_failure_rate(self, tmp_path, mock_args, mock_db_class, mock_config_class):
        """Test exit code when >10% files fail."""
        db_instance = mock_db_class.return_value
        db_instance.paths = ["f"] * 100
        db_instance.failed = ["f"] * 15 # 15% failure
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        assert exc.value.code == ExitCode.DATA_ERROR


class TestGenerateOutput:
    """Tests for command output (JSON/Console)."""

    def test_json_success_output(self, tmp_path, mock_args, mock_db_class, mock_config_class, capsys):
        """Test successful JSON output."""
        mock_args.json = True
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
        
        assert exc.value.code == ExitCode.SUCCESS
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        
        assert data["status"] == "success"
        assert "tracks" in data
        assert "duration_ms" in data
        assert "files_scanned" in data
        
    def test_json_high_failure_output(self, tmp_path, mock_args, mock_db_class, mock_config_class, capsys):
        """Test JSON output with high failure rate."""
        mock_args.json = True
        db_instance = mock_db_class.return_value
        db_instance.paths = ["f"] * 100
        db_instance.failed = ["f"] * 15
        
        with pytest.raises(SystemExit) as exc:
            cmd_generate(mock_args)
            
        assert exc.value.code == ExitCode.DATA_ERROR
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        
        assert data["status"] == "completed_with_errors"
        assert data["files_failed"] == 15

