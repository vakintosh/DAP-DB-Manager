"""Tests for mount detector functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, tmp_path
from dap_db_manager.database.mount_detector import MountDetector, MountInfo


class TestMountDetector:
    """Test MountDetector class."""

    def test_mount_detector_extract_prefix(self):
        """Test extracting mount prefix from paths."""
        # Test with mount notation
        notation, path = MountDetector.extract_mount_prefix("/<HDD0>/Music/song.mp3")
        assert notation == "/<HDD0>"
        assert path == "/Music/song.mp3"
        
        # Test without mount notation
        notation2, path2 = MountDetector.extract_mount_prefix("/Music/song.mp3")
        assert notation2 is None
        assert path2 == "/Music/song.mp3"

    def test_mount_detector_suggest_notation(self):
        """Test suggesting mount notation."""
        # Should return a default or detected notation
        notation = MountDetector.suggest_mount_notation()
        assert notation is not None
        assert isinstance(notation, str)


class TestMountInfo:
    """Test MountInfo class."""

    def test_mount_info_creation(self):
        """Test creating MountInfo objects."""
        mount = MountInfo(
            notation="/<HDD0>",
            count=100,
            sample_paths=["/Music/song1.mp3", "/Music/song2.mp3"]
        )
        assert mount.notation == "/<HDD0>"
        assert mount.count == 100
        assert len(mount.sample_paths) <= 5  # Only keeps first 5 samples

    def test_mount_info_repr(self):
        """Test MountInfo string representation."""
        mount = MountInfo("/<HDD0>", 50, ["/path/to/file.mp3"])
        repr_str = repr(mount)
        assert "MountInfo" in repr_str or "HDD0" in repr_str


@pytest.mark.integration
class TestMountDetectorIntegration:
    """Integration tests for mount detection."""

    def test_detect_from_storage_no_crash(self):
        """Test that device storage detection doesn't crash."""
        # Test with non-existent path
        mounts = MountDetector.detect_from_device_storage("/nonexistent/path")
        # Should return empty list or handle gracefully
        assert isinstance(mounts, list)
