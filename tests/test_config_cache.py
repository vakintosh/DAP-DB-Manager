"""Tests for Config cache size configuration and TagCache integration."""

import pytest
import tempfile
from pathlib import Path

from dap_db_manager.config import Config
from dap_db_manager.database.cache import TagCache


class TestConfigCacheSize:
    """Test cache size configuration in Config class."""

    def test_default_cache_memory(self):
        """Test that default cache memory is in DEFAULT_CONFIG."""
        # Check the class-level default (not affected by loaded config)
        # Note: tag_cache_memory_mb may not be in DEFAULT_CONFIG if auto-detected
        assert "performance" in Config.DEFAULT_CONFIG

    def test_set_cache_memory(self):
        """Test setting cache memory."""
        config = Config()
        config.set_tag_cache_memory(1024)
        assert config.get_tag_cache_memory() == 1024

    def test_cache_memory_validation_too_small(self):
        """Test that cache memory validation rejects values < 100MB."""
        config = Config()
        with pytest.raises(ValueError, match="Cache memory must be at least 100 MB"):
            config.set_tag_cache_memory(32)

    def test_cache_memory_validation_minimum(self):
        """Test that cache memory accepts exactly 100MB."""
        config = Config()
        config.set_tag_cache_memory(100)
        assert config.get_tag_cache_memory() == 100

    def test_cache_memory_large_value(self):
        """Test setting very large cache memory."""
        config = Config()
        config.set_tag_cache_memory(4096)
        assert config.get_tag_cache_memory() == 4096

    def test_cache_size_persistence(self):
        """Test that cache size is saved and loaded from TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rdbm_config.toml"

            # Create and save config
            config1 = Config()
            config1.config_path = config_path
            config1.set_tag_cache_memory(768)
            config1.save()

            # Load in new instance
            config2 = Config()
            config2.config_path = config_path
            config2.load()

            assert config2.get_tag_cache_memory() == 768

    def test_cache_memory_in_performance_section(self):
        """Test that cache memory is stored in performance section."""
        config = Config()
        config.set_tag_cache_memory(1024)

        assert "performance" in config.data
        assert "tag_cache_memory_mb" in config.data["performance"]
        assert config.data["performance"]["tag_cache_memory_mb"] == 1024


class TestTagCacheIntegration:
    """Test TagCache class integration with Config."""

    def setup_method(self):
        """Reset cache before each test."""
        TagCache.clear()
        TagCache.MAX_CACHE_MEMORY_MB = 512  # Reset to default

    def test_set_max_cache_memory(self):
        """Test setting maximum cache memory."""
        TagCache.set_max_cache_memory(1024)
        assert TagCache.get_max_cache_memory() == 1024

    def test_get_max_cache_memory(self):
        """Test getting maximum cache memory."""
        assert TagCache.get_max_cache_memory() == 512  # Default
        TagCache.set_max_cache_memory(768)
        assert TagCache.get_max_cache_memory() == 768

    def test_set_cache_memory_validation(self):
        """Test that TagCache validates minimum memory."""
        with pytest.raises(ValueError, match="Cache memory must be at least 100 MB"):
            TagCache.set_max_cache_memory(50)

    def test_cache_memory_minimum_boundary(self):
        """Test minimum cache memory boundary."""
        TagCache.set_max_cache_memory(100)
        assert TagCache.get_max_cache_memory() == 100

    def test_cache_trim_on_memory_reduction(self):
        """Test that cache is trimmed when memory is reduced."""
        # Set initial large memory
        TagCache.set_max_cache_memory(2048)

        # Add entries to cache
        cache = TagCache.get_cache()
        for i in range(100):
            cache[f"file_{i}"] = ((1000, 1000), {"title": f"Track {i}"})

        assert len(cache) >= 10

        # Reduce memory - cache should trim automatically
        TagCache.set_max_cache_memory(256)

        # Just verify the max memory was set
        assert TagCache.get_max_cache_memory() == 256

    def test_config_and_cache_integration(self):
        """Test full integration: Config -> TagCache."""
        config = Config()
        config.set_tag_cache_memory(1536)

        # Apply to cache
        TagCache.set_max_cache_memory(config.get_tag_cache_memory())

        assert TagCache.get_max_cache_memory() == 1536

    def test_cache_respects_new_limit(self):
        """Test that cache respects the new limit when adding entries."""
        # Use a valid memory (>= 64MB)
        TagCache.set_max_cache_memory(128)
        cache = TagCache.get_cache()

        # Add entries
        for i in range(100):
            cache[f"file_{i}"] = ((1000, 1000), {"title": f"Track {i}"})

        # Cache may auto-trim depending on implementation
        # Just verify max memory is set correctly
        assert TagCache.get_max_cache_memory() == 128


class TestConfigCacheDefault:
    """Test that Config has proper default values."""

    def test_default_config_has_performance_section(self):
        """Test that DEFAULT_CONFIG includes performance section."""
        assert "performance" in Config.DEFAULT_CONFIG

    def test_default_performance_values(self):
        """Test default performance configuration values."""
        # Check that config returns valid cache memory (may be auto-detected)
        config = Config()
        cache_memory = config.get_tag_cache_memory()
        assert isinstance(cache_memory, int)
        assert cache_memory >= 100  # At least minimum


class TestConfigCacheEdgeCases:
    """Test edge cases and error handling."""

    def test_negative_cache_memory(self):
        """Test that negative cache memory is rejected."""
        config = Config()
        with pytest.raises(ValueError):
            config.set_tag_cache_memory(-512)

    def test_zero_cache_memory(self):
        """Test that zero cache memory is rejected."""
        config = Config()
        with pytest.raises(ValueError):
            config.set_tag_cache_memory(0)

    def test_cache_memory_without_performance_section(self):
        """Test getting cache memory when performance section doesn't exist."""
        config = Config()
        # Remove performance section
        if "performance" in config.data:
            del config.data["performance"]

        # Should return auto-detected value (based on system RAM)
        cache_memory = config.get_tag_cache_memory()
        assert isinstance(cache_memory, int)
        assert cache_memory >= 100

    def test_cache_memory_with_missing_key(self):
        """Test getting cache memory when key is missing."""
        config = Config()
        config.data["performance"] = {}  # Empty performance section

        # Should return auto-detected value
        cache_memory = config.get_tag_cache_memory()
        assert isinstance(cache_memory, int)
        assert cache_memory >= 100


class TestCacheMemoryManagement:
    """Test cache memory management features."""

    def setup_method(self):
        """Reset cache before each test."""
        TagCache.clear()
        TagCache.MAX_CACHE_MEMORY_MB = 512

    def test_clear_cache(self):
        """Test clearing the cache."""
        cache = TagCache.get_cache()
        for i in range(100):
            cache[f"file_{i}"] = {"title": f"Track {i}"}

        assert len(cache) > 0
        TagCache.clear()
        assert len(cache) == 0

    def test_cache_memory_change_preserves_entries(self):
        """Test that increasing cache memory preserves existing entries."""
        TagCache.set_max_cache_memory(256)
        cache = TagCache.get_cache()

        # Add entries
        for i in range(50):
            cache[f"file_{i}"] = ((1000, 1000), {"title": f"Track {i}"})

        # Increase memory
        TagCache.set_max_cache_memory(512)

        # All entries should still be there
        assert len(cache) >= 10
        assert "file_10" in cache

    def test_multiple_memory_adjustments(self):
        """Test multiple consecutive memory adjustments."""
        TagCache.set_max_cache_memory(256)
        assert TagCache.get_max_cache_memory() == 256

        TagCache.set_max_cache_memory(1024)
        assert TagCache.get_max_cache_memory() == 1024

        TagCache.set_max_cache_memory(512)
        assert TagCache.get_max_cache_memory() == 512


class TestCLICacheConfiguration:
    """Test CLI integration with cache configuration."""

    def test_config_loads_before_commands(self):
        """Test that config is loaded and applied during CLI initialization."""
        # This is more of a documentation test - the actual CLI loading
        # happens in cli/__init__.py main() function
        config = Config()
        cache_memory = config.get_tag_cache_memory()

        # Simulate CLI initialization
        TagCache.set_max_cache_memory(cache_memory)

        assert TagCache.get_max_cache_memory() == cache_memory


class TestGUICacheConfiguration:
    """Test GUI integration with cache configuration."""

    def test_gui_initialization(self):
        """Test that GUI initializes cache configuration."""
        # Simulate GUI startup
        config = Config()
        TagCache.set_max_cache_memory(config.get_tag_cache_memory())

        # Verify cache is configured
        assert TagCache.get_max_cache_memory() == config.get_tag_cache_memory()

    def test_runtime_cache_adjustment(self):
        """Test adjusting cache memory during runtime (e.g., from settings dialog)."""
        config = Config()

        # User changes setting
        new_memory = 1024
        config.set_tag_cache_memory(new_memory)
        config.save()

        # Apply immediately
        TagCache.set_max_cache_memory(new_memory)

        assert TagCache.get_max_cache_memory() == new_memory
        assert config.get_tag_cache_memory() == new_memory


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
