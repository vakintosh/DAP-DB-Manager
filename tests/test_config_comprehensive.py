"""Comprehensive tests for Config class to achieve 85%+ coverage."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from dap_db_manager.config import Config, get_config_dir, get_config_path, get_optimal_cache_memory_mb


class TestConfigHelperFunctions:
    """Test module-level helper functions."""

    def test_get_config_dir_creates_directory(self):
        """Test that get_config_dir creates the .ddm directory."""
        config_dir = get_config_dir()
        assert config_dir.exists()
        assert config_dir.name == ".ddm"
        assert config_dir.is_dir()

    def test_get_config_path(self):
        """Test that get_config_path returns correct path."""
        config_path = get_config_path()
        assert config_path.name == ".rdbm_config.toml"
        assert config_path.parent.name == ".ddm"

    def test_get_optimal_cache_memory_mb_no_psutil(self):
        """Test optimal cache memory when psutil is not available."""
        with patch('dap_db_manager.config.psutil_module', None):
            memory = get_optimal_cache_memory_mb()
            assert memory == 512  # Fallback value

    def test_get_optimal_cache_memory_mb_low_ram(self):
        """Test optimal cache memory with < 4GB RAM."""
        mock_memory = MagicMock()
        mock_memory.total = 2 * 1024 * 1024 * 1024  # 2GB
        with patch('dap_db_manager.config.psutil_module') as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_memory
            memory = get_optimal_cache_memory_mb()
            assert memory == 256

    def test_get_optimal_cache_memory_mb_medium_ram(self):
        """Test optimal cache memory with 4-8GB RAM."""
        mock_memory = MagicMock()
        mock_memory.total = 6 * 1024 * 1024 * 1024  # 6GB
        with patch('dap_db_manager.config.psutil_module') as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_memory
            memory = get_optimal_cache_memory_mb()
            assert memory == 512

    def test_get_optimal_cache_memory_mb_high_ram(self):
        """Test optimal cache memory with 8-16GB RAM."""
        mock_memory = MagicMock()
        mock_memory.total = 12 * 1024 * 1024 * 1024  # 12GB
        with patch('dap_db_manager.config.psutil_module') as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_memory
            memory = get_optimal_cache_memory_mb()
            assert memory == 1024

    def test_get_optimal_cache_memory_mb_very_high_ram(self):
        """Test optimal cache memory with > 16GB RAM."""
        mock_memory = MagicMock()
        mock_memory.total = 32 * 1024 * 1024 * 1024  # 32GB
        with patch('dap_db_manager.config.psutil_module') as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_memory
            memory = get_optimal_cache_memory_mb()
            assert memory == 2048

    def test_get_optimal_cache_memory_mb_exception(self):
        """Test optimal cache memory when exception occurs."""
        with patch('dap_db_manager.config.psutil_module') as mock_psutil:
            mock_psutil.virtual_memory.side_effect = Exception("Mock error")
            memory = get_optimal_cache_memory_mb()
            assert memory == 512  # Fallback value


class TestConfigLoadSave:
    """Test Config loading and saving functionality."""

    def test_load_nonexistent_file(self):
        """Test loading when config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.toml"
            # Create fresh config without loading existing user config
            config = Config()
            config.data = config.DEFAULT_CONFIG.copy()
            config.config_path = config_path
            
            result = config.load()
            assert result is False
            # Should have default values
            assert config.data == Config.DEFAULT_CONFIG

    def test_load_corrupted_toml(self):
        """Test loading corrupted TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "corrupted.toml"
            config_path.write_text("this is not valid toml {{{}}")
            
            config = Config()
            config.config_path = config_path
            result = config.load()
            assert result is False

    def test_load_success(self):
        """Test successful config loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            
            # Create and save a config
            config1 = Config()
            config1.config_path = config_path
            config1.set_window_size(1024, 768)
            config1.save()
            
            # Load in new instance
            config2 = Config()
            config2.config_path = config_path
            result = config2.load()
            
            assert result is True
            assert config2.get_window_size() == (1024, 768)

    def test_save_when_not_dirty(self):
        """Test that save returns True without writing when not dirty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = Config()
            config.config_path = config_path
            config._dirty = False
            
            result = config.save()
            assert result is True
            assert not config_path.exists()  # File not created

    def test_save_without_tomli_w(self):
        """Test save when tomli_w is not available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = Config()
            config.config_path = config_path
            config._dirty = True
            
            with patch('dap_db_manager.config.tomli_w', None):
                result = config.save()
                assert result is False

    def test_save_io_error(self):
        """Test save when I/O error occurs."""
        config = Config()
        config.config_path = Path("/nonexistent_directory/config.toml")
        config._dirty = True
        
        result = config.save()
        assert result is False

    def test_save_force_when_not_dirty(self):
        """Test force save even when not dirty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = Config()
            config.config_path = config_path
            config._dirty = False
            
            result = config.save(force=True)
            assert result is True
            assert config_path.exists()


class TestConfigDirtyFlag:
    """Test dirty flag tracking."""

    def test_is_dirty_initially_false(self):
        """Test that config is not dirty initially after forced init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert not config.is_dirty()

    def test_is_dirty_after_set_window_size(self):
        """Test dirty flag is set after window size change."""
        config = Config()
        config.set_window_size(800, 600)
        assert config.is_dirty()

    def test_is_dirty_after_set_window_position(self):
        """Test dirty flag is set after window position change."""
        config = Config()
        config.set_window_position(100, 200)
        assert config.is_dirty()

    def test_is_dirty_after_set_format(self):
        """Test dirty flag is set after format change."""
        config = Config()
        config.set_format("artist", "%artist% - custom")
        assert config.is_dirty()

    def test_dirty_flag_cleared_after_save(self):
        """Test dirty flag is cleared after successful save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = Config()
            config.config_path = config_path
            config.set_window_size(1024, 768)
            
            assert config.is_dirty()
            config.save()
            assert not config.is_dirty()


class TestConfigWindowSettings:
    """Test window-related configuration methods."""

    def test_get_window_size_default(self):
        """Test getting default window size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert config.get_window_size() == (800, 600)

    def test_set_and_get_window_size(self):
        """Test setting and getting window size."""
        config = Config()
        config.set_window_size(1920, 1080)
        assert config.get_window_size() == (1920, 1080)

    def test_get_window_position_default(self):
        """Test getting default window position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert config.get_window_position() == (-1, -1)

    def test_set_and_get_window_position(self):
        """Test setting and getting window position."""
        config = Config()
        config.set_window_position(100, 200)
        assert config.get_window_position() == (100, 200)


class TestConfigPathSettings:
    """Test path-related configuration methods."""

    def test_get_last_music_dir_default(self):
        """Test getting default last music dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert config.get_last_music_dir() == ""

    def test_set_and_get_last_music_dir(self):
        """Test setting and getting last music dir."""
        config = Config()
        config.set_last_music_dir("/path/to/music")
        assert config.get_last_music_dir() == "/path/to/music"

    def test_get_last_output_dir_default(self):
        """Test getting default last output dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert config.get_last_output_dir() == ""

    def test_set_and_get_last_output_dir(self):
        """Test setting and getting last output dir."""
        config = Config()
        config.set_last_output_dir("/path/to/output")
        assert config.get_last_output_dir() == "/path/to/output"

    def test_get_last_tags_file_default(self):
        """Test getting default last tags file."""
        config = Config()
        assert config.get_last_tags_file() == ""

    def test_set_and_get_last_tags_file(self):
        """Test setting and getting last tags file."""
        config = Config()
        config.set_last_tags_file("/path/to/tags.pkl")
        assert config.get_last_tags_file() == "/path/to/tags.pkl"


class TestConfigFormatSettings:
    """Test format string configuration methods."""

    def test_get_format_existing(self):
        """Test getting existing format."""
        config = Config()
        assert config.get_format("artist") == "%artist%"

    def test_get_format_nonexistent(self):
        """Test getting non-existent format returns default."""
        config = Config()
        result = config.get_format("customfield")
        assert "%customfield%" in result

    def test_set_and_get_format(self):
        """Test setting and getting format."""
        config = Config()
        config.set_format("artist", "%artist% - %album%")
        assert config.get_format("artist") == "%artist% - %album%"

    def test_get_sort_format_default(self):
        """Test getting default sort format."""
        config = Config()
        assert config.get_sort_format("artist") == ""

    def test_set_and_get_sort_format(self):
        """Test setting and getting sort format."""
        config = Config()
        config.set_sort_format("artist", "%artist% sort")
        assert config.get_sort_format("artist") == "%artist% sort"

    def test_get_all_formats(self):
        """Test getting all formats."""
        config = Config()
        formats = config.get_all_formats()
        assert isinstance(formats, dict)
        assert "artist" in formats
        assert "album" in formats

    def test_get_all_sort_formats(self):
        """Test getting all sort formats."""
        config = Config()
        sort_formats = config.get_all_sort_formats()
        assert isinstance(sort_formats, dict)
        assert "artist" in sort_formats


class TestConfigDatabaseSettings:
    """Test database-related configuration methods."""

    def test_get_database_version_default(self):
        """Test getting default database version."""
        config = Config()
        assert config.get_database_version() == 16

    def test_set_database_version(self):
        """Test setting database version."""
        config = Config()
        config.set_database_version(16)
        assert config.get_database_version() == 16

    def test_set_database_version_creates_section(self):
        """Test that setting database version creates database section."""
        config = Config()
        if "database" in config.data:
            del config.data["database"]
        
        config.set_database_version(16)
        assert "database" in config.data
        assert config.data["database"]["version"] == 16

    def test_get_mount_notation_default(self):
        """Test getting default mount notation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert config.get_mount_notation() == ""

    def test_set_mount_notation(self):
        """Test setting mount notation."""
        config = Config()
        config.set_mount_notation("/<HDD0>")
        assert config.get_mount_notation() == "/<HDD0>"
        assert config.is_mount_notation_configured()

    def test_is_mount_notation_configured_default(self):
        """Test mount notation configured is False by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.config_path = Path(tmpdir) / "config.toml"
            config.data = config.DEFAULT_CONFIG.copy()
            config._dirty = False
        assert not config.is_mount_notation_configured()

    def test_set_mount_notation_creates_section(self):
        """Test that setting mount notation creates database section."""
        config = Config()
        if "database" in config.data:
            del config.data["database"]
        
        config.set_mount_notation("/<MMC0>")
        assert "database" in config.data
        assert config.data["database"]["mount_notation"] == "/<MMC0>"
        assert config.data["database"]["mount_notation_configured"] is True


class TestConfigMountNotationAutoDetect:
    """Test auto-detection of mount notation."""

    def test_auto_detect_mount_notation_success(self):
        """Test successful auto-detection."""
        config = Config()
        
        with patch('dap_db_manager.database.mount_detector.MountDetector') as mock_detector:
            mock_detector.detect_from_device_storage.return_value = ["/<HDD0>", "/<MMC0>"]
            
            result = config.auto_detect_mount_notation("/path/to/device")
            
            assert result == "/<HDD0>"
            assert config.get_mount_notation() == "/<HDD0>"
            assert config.is_mount_notation_configured()

    def test_auto_detect_mount_notation_with_callback(self):
        """Test auto-detection with callback."""
        config = Config()
        callback_messages = []
        
        def callback(msg):
            callback_messages.append(msg)
        
        with patch('dap_db_manager.database.mount_detector.MountDetector') as mock_detector:
            mock_detector.detect_from_device_storage.return_value = ["/<HDD0>"]
            
            result = config.auto_detect_mount_notation("/path/to/device", callback=callback)
            
            assert result == "/<HDD0>"
            assert len(callback_messages) >= 2  # Should have detection messages

    def test_auto_detect_mount_notation_multiple_mounts(self):
        """Test auto-detection with multiple mounts."""
        config = Config()
        callback_messages = []
        
        def callback(msg):
            callback_messages.append(msg)
        
        with patch('dap_db_manager.database.mount_detector.MountDetector') as mock_detector:
            mock_detector.detect_from_device_storage.return_value = ["/<HDD0>", "/<MMC0>", "/<USB0>"]
            
            result = config.auto_detect_mount_notation("/path/to/device", callback=callback)
            
            assert result == "/<HDD0>"
            # Should mention additional mounts
            assert any("Additional mounts" in msg for msg in callback_messages)

    def test_auto_detect_mount_notation_no_mounts_found(self):
        """Test auto-detection when no mounts found."""
        config = Config()
        callback_messages = []
        
        def callback(msg):
            callback_messages.append(msg)
        
        with patch('dap_db_manager.database.mount_detector.MountDetector') as mock_detector:
            mock_detector.detect_from_device_storage.return_value = []
            
            result = config.auto_detect_mount_notation("/path/to/device", callback=callback)
            
            assert result == "/<HDD0>"  # Default fallback
            assert config.get_mount_notation() == "/<HDD0>"
            # Should have warning message
            assert any("Could not detect" in msg for msg in callback_messages)

    def test_auto_detect_mount_notation_exception(self):
        """Test auto-detection when exception occurs."""
        config = Config()
        callback_messages = []
        
        def callback(msg):
            callback_messages.append(msg)
        
        with patch('dap_db_manager.database.mount_detector.MountDetector') as mock_detector:
            mock_detector.detect_from_device_storage.side_effect = Exception("Mock error")
            
            result = config.auto_detect_mount_notation("/path/to/device", callback=callback)
            
            assert result == "/<HDD0>"  # Default fallback
            # Should have error message
            assert any("failed" in msg for msg in callback_messages)


class TestConfigMergeAndFilter:
    """Test config merging and None value filtering."""

    def test_merge_config_simple(self):
        """Test simple config merging."""
        config = Config()
        base = {"key1": "value1"}
        override = {"key2": "value2"}
        
        config._merge_config(base, override)
        
        assert base == {"key1": "value1", "key2": "value2"}

    def test_merge_config_nested(self):
        """Test nested config merging."""
        config = Config()
        base = {"section": {"key1": "value1"}}
        override = {"section": {"key2": "value2"}}
        
        config._merge_config(base, override)
        
        assert base == {"section": {"key1": "value1", "key2": "value2"}}

    def test_merge_config_override(self):
        """Test config merging overrides values."""
        config = Config()
        base = {"key": "old_value"}
        override = {"key": "new_value"}
        
        config._merge_config(base, override)
        
        assert base == {"key": "new_value"}

    def test_filter_none_values_simple(self):
        """Test filtering None values."""
        config = Config()
        data = {"key1": "value1", "key2": None, "key3": "value3"}
        
        result = config._filter_none_values(data)
        
        assert result == {"key1": "value1", "key3": "value3"}

    def test_filter_none_values_nested(self):
        """Test filtering None values in nested dicts."""
        config = Config()
        data = {
            "section": {
                "key1": "value1",
                "key2": None,
                "nested": {
                    "key3": None,
                    "key4": "value4"
                }
            }
        }
        
        result = config._filter_none_values(data)
        
        assert result == {
            "section": {
                "key1": "value1",
                "nested": {
                    "key4": "value4"
                }
            }
        }

    def test_filter_none_values_empty_dict(self):
        """Test that empty dicts are removed after filtering."""
        config = Config()
        data = {
            "section": {
                "key1": None
            },
            "other": "value"
        }
        
        result = config._filter_none_values(data)
        
        # Empty section should be removed
        assert result == {"other": "value"}


class TestConfigPersistence:
    """Test config persistence across load/save cycles."""

    def test_persistence_all_settings(self):
        """Test that all settings persist across save/load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            
            # Set all types of settings
            config1 = Config()
            config1.config_path = config_path
            config1.set_window_size(1024, 768)
            config1.set_window_position(100, 200)
            config1.set_last_music_dir("/music")
            config1.set_format("artist", "custom")
            config1.set_database_version(16)
            config1.set_mount_notation("/<HDD0>")
            config1.save()
            
            # Load in new instance
            config2 = Config()
            config2.config_path = config_path
            config2.load()
            
            assert config2.get_window_size() == (1024, 768)
            assert config2.get_window_position() == (100, 200)
            assert config2.get_last_music_dir() == "/music"
            assert config2.get_format("artist") == "custom"
            assert config2.get_database_version() == 16
            assert config2.get_mount_notation() == "/<HDD0>"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
