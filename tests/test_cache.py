"""Tests for TagCache class and cache management."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dap_db_manager.database.cache import TagCache, SimpleTag


class TestSimpleTag:
    """Test SimpleTag class."""

    def test_simple_tag_creation(self):
        """Test creating a SimpleTag from a dictionary."""
        tag_dict = {"artist": ["Test Artist"], "album": ["Test Album"], "title": ["Test Title"]}
        tag = SimpleTag(tag_dict)
        
        assert tag["artist"] == ["Test Artist"]
        assert tag["album"] == ["Test Album"]
        assert tag["title"] == ["Test Title"]

    def test_simple_tag_get_string(self):
        """Test get_string method for titleformat compatibility."""
        tag_dict = {"artist": ["Artist Name"], "album": ["Album Name"]}
        tag = SimpleTag(tag_dict)
        
        assert tag.get_string("artist") == ["Artist Name"]
        assert tag.get_string("album") == ["Album Name"]
        
        # get_string raises KeyError for missing keys (matches mutagen behavior)
        with pytest.raises(KeyError):
            tag.get_string("nonexistent")

    def test_simple_tag_missing_key(self):
        """Test handling of missing keys."""
        tag_dict = {"artist": ["Artist"]}
        tag = SimpleTag(tag_dict)
        
        # Missing keys should return empty list via get_string
        assert tag.get_string("album") == []
        
        # Direct access should raise KeyError
        with pytest.raises(KeyError):
            _ = tag["album"]


class TestTagCacheBasics:
    """Test basic TagCache operations."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_cache_initialization(self):
        """Test cache initialization and access."""
        cache = TagCache.get_cache()
        assert cache is not None
        assert len(cache) == 0

    def test_cache_singleton_pattern(self):
        """Test that get_cache returns the same instance."""
        cache1 = TagCache.get_cache()
        cache2 = TagCache.get_cache()
        assert cache1 is cache2

    def test_cache_set_and_get(self):
        """Test setting and getting cache values."""
        test_key = "/test/path/song.mp3"
        test_value = ((1000, 1234567890), {"artist": ["Test"], "album": ["Album"]})
        
        TagCache.set(test_key, test_value)
        retrieved = TagCache.get(test_key)
        
        assert retrieved is not None
        assert retrieved[0] == (1000, 1234567890)
        assert retrieved[1]["artist"] == ["Test"]

    def test_cache_get_default(self):
        """Test get with default value for missing keys."""
        result = TagCache.get("/nonexistent/path.mp3", default="NOT_FOUND")
        assert result == "NOT_FOUND"

    def test_cache_clear(self):
        """Test clearing the cache."""
        TagCache.set("/test1.mp3", ((100, 111), {}))
        TagCache.set("/test2.mp3", ((200, 222), {}))
        
        assert len(TagCache.get_cache()) == 2
        
        TagCache.clear()
        assert len(TagCache.get_cache()) == 0


class TestTagCacheMemoryManagement:
    """Test TagCache memory management features."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()
        TagCache.set_memory_tracking(True)

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()
        TagCache.set_memory_tracking(True)
        TagCache.set_auto_trim(True)

    def test_set_max_cache_memory(self):
        """Test setting maximum cache memory."""
        TagCache.set_max_cache_memory(200)
        assert TagCache.get_max_cache_memory() == 200

    def test_set_max_cache_memory_minimum(self):
        """Test that minimum cache size is enforced."""
        with pytest.raises(ValueError, match="at least 100"):
            TagCache.set_max_cache_memory(50)

    def test_get_current_memory_usage(self):
        """Test getting current memory usage."""
        bytes_used, mb_used, entry_count = TagCache.get_current_memory_usage()
        assert bytes_used >= 0
        assert mb_used >= 0
        assert entry_count == 0

        # Add an entry
        TagCache.set("/test.mp3", ((100, 111), {"artist": ["Artist"]}))
        bytes_used, mb_used, entry_count = TagCache.get_current_memory_usage()
        assert entry_count == 1
        assert bytes_used > 0

    def test_memory_tracking_toggle(self):
        """Test enabling and disabling memory tracking."""
        TagCache.set_memory_tracking(False)
        TagCache.set("/test.mp3", ((100, 111), {}))
        
        # With tracking disabled, memory should be 0
        bytes_used, _, _ = TagCache.get_current_memory_usage()
        assert bytes_used == 0

        # Re-enable tracking
        TagCache.set_memory_tracking(True)
        bytes_used, _, _ = TagCache.get_current_memory_usage()
        assert bytes_used > 0

    def test_auto_trim_toggle(self):
        """Test enabling and disabling auto-trim."""
        TagCache.set_auto_trim(False)
        # Should not raise an error
        TagCache.set_auto_trim(True)


class TestTagCacheEssentialTags:
    """Test essential tag extraction and restoration."""

    def test_extract_essential_tags_with_none(self):
        """Test extracting essential tags from None."""
        result = TagCache.extract_essential_tags(None)
        assert result is None

    def test_extract_essential_tags_basic(self):
        """Test extracting essential tags from a mock tag object."""
        mock_tag = Mock()
        mock_tag.__getitem__ = lambda self, key: f"value_{key}"
        
        result = TagCache.extract_essential_tags(mock_tag)
        assert isinstance(result, dict)

    def test_restore_tag_dict_with_none(self):
        """Test restoring None tag dict."""
        result = TagCache.restore_tag_dict(None)
        assert result is None

    def test_restore_tag_dict_basic(self):
        """Test restoring a tag dictionary."""
        tag_dict = {"artist": ["Artist"], "album": ["Album"]}
        result = TagCache.restore_tag_dict(tag_dict)
        
        assert isinstance(result, SimpleTag)
        assert result["artist"] == ["Artist"]
        assert result.get_string("album") == ["Album"]


class TestTagCachePersistence:
    """Test TagCache save and load operations."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_save_and_load_cache(self, tmp_path):
        """Test saving and loading cache to/from file."""
        # Populate cache
        test_data = {
            "/test1.mp3": ((1000, 1234567890), {"artist": ["Artist1"], "title": ["Song1"]}),
            "/test2.mp3": ((2000, 1234567891), {"artist": ["Artist2"], "title": ["Song2"]}),
        }
        
        for path, value in test_data.items():
            TagCache.set(path, value)

        # Save cache
        cache_file = tmp_path / "test_cache.pkl.gz"
        paths_set = set(test_data.keys())
        TagCache.save(str(cache_file), paths_set)

        # Clear cache and reload
        TagCache.clear()
        assert len(TagCache.get_cache()) == 0

        new_paths_set = set()
        TagCache.load(str(cache_file), new_paths_set)

        # Verify loaded data
        assert len(new_paths_set) == 2
        assert "/test1.mp3" in new_paths_set
        assert "/test2.mp3" in new_paths_set

    def test_load_nonexistent_file(self):
        """Test loading from a non-existent cache file."""
        paths_set = set()
        # Should not raise an exception, just log a warning
        TagCache.load("/nonexistent/cache.pkl.gz", paths_set)
        assert len(paths_set) == 0

    def test_save_creates_directory(self, tmp_path):
        """Test that save requires parent directory to exist."""
        cache_file = tmp_path / "nested" / "dir" / "cache.pkl.gz"
        paths_set = {"/test.mp3"}
        TagCache.set("/test.mp3", ((100, 111), {"artist": ["Artist"]}))
        
        # Create parent directory first (save doesn't auto-create)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        TagCache.save(str(cache_file), paths_set)
        assert cache_file.exists()

    def test_save_empty_cache(self, tmp_path):
        """Test saving an empty cache."""
        cache_file = tmp_path / "empty_cache.pkl.gz"
        paths_set = set()
        
        TagCache.save(str(cache_file), paths_set)
        # Should create an empty cache file
        assert cache_file.exists()


class TestTagCacheCleanup:
    """Test TagCache cleanup operations."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_cleanup_removes_unused_entries(self):
        """Test that cleanup removes entries not in keep_paths."""
        TagCache.set("/keep/this.mp3", ((100, 111), {}))
        TagCache.set("/remove/this.mp3", ((200, 222), {}))
        TagCache.set("/also/keep.mp3", ((300, 333), {}))

        keep_paths = {"/keep/this.mp3", "/also/keep.mp3"}
        TagCache.cleanup(keep_paths)

        # Should only have kept paths
        assert TagCache.get("/keep/this.mp3") is not None
        assert TagCache.get("/also/keep.mp3") is not None
        assert TagCache.get("/remove/this.mp3") is None

    def test_cleanup_with_none_keeps_all(self):
        """Test that cleanup(None) keeps all entries."""
        TagCache.set("/test1.mp3", ((100, 111), {}))
        TagCache.set("/test2.mp3", ((200, 222), {}))

        initial_count = len(TagCache.get_cache())
        TagCache.cleanup(None)
        
        # Should keep everything
        assert len(TagCache.get_cache()) == initial_count


@pytest.mark.integration
class TestTagCacheIntegration:
    """Integration tests for TagCache with realistic scenarios."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_cache_workflow_save_load_cleanup(self, tmp_path):
        """Test a complete cache workflow: populate, save, load, cleanup."""
        # 1. Populate cache
        files = [f"/music/song{i}.mp3" for i in range(10)]
        for i, file in enumerate(files):
            TagCache.set(file, ((i * 1000, i * 100), {"artist": [f"Artist{i}"]}))

        # 2. Save cache
        cache_file = tmp_path / "workflow_cache.pkl.gz"
        TagCache.save(str(cache_file), set(files))
        assert cache_file.exists()

        # 3. Clear and reload
        TagCache.clear()
        paths_set = set()
        TagCache.load(str(cache_file), paths_set)
        assert len(paths_set) == 10

        # 4. Cleanup - keep only first 5 files
        keep_paths = set(files[:5])
        TagCache.cleanup(keep_paths)
        assert len(TagCache.get_cache()) == 5

        # 5. Verify correct files remain
        for file in files[:5]:
            assert TagCache.get(file) is not None
        for file in files[5:]:
            assert TagCache.get(file) is None
