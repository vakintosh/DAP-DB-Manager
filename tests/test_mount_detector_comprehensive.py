
import pytest
import sys
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from dap_db_manager.database.mount_detector import MountDetector, MountInfo, MOUNT_PATTERN

class TestMountDetector:

    # --- Helper Tests ---
    
    def test_mount_pattern_regex(self):
        # Test the regex directly
        assert MOUNT_PATTERN.match("/<HDD0>/file.mp3")
        assert MOUNT_PATTERN.match("/<MMC1>/folder/file")
        assert not MOUNT_PATTERN.match("/Music/file.mp3")
        assert not MOUNT_PATTERN.match("/<Invalid>/file") # Needs digits?
        # A-Z + digits
        assert MOUNT_PATTERN.match("/<A1>/")
        
    def test_extract_mount_prefix(self):
        path = "/<HDD0>/Music/Song.mp3"
        notation, clean = MountDetector.extract_mount_prefix(path)
        assert notation == "/<HDD0>"
        assert clean == "/Music/Song.mp3"
        
        path = "/Music/Song.mp3"
        notation, clean = MountDetector.extract_mount_prefix(path)
        assert notation is None
        assert clean == "/Music/Song.mp3"

    # --- Storage Detection Tests (Platform Specific) ---

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_detect_from_device_storage_macos(self, mock_run, mock_platform):
        # Mock diskutil info
        mock_info_res = MagicMock()
        mock_info_res.returncode = 0
        mock_info_res.stdout = """
        Device Identifier:        disk2s1
        Device Node:              /dev/disk2s1
        """
        
        # Mock diskutil list
        # disk2 has partitions 1 (EFI), 2 (Rockbox FAT32), 3 (Data ExFAT)
        mock_list_res = MagicMock()
        mock_list_res.returncode = 0
        
        # Check logic: "disk" in line AND ("FAT" or "DOS")
        mock_list_res.stdout = """
           1:                DOS_FAT_32 ROCKBOX                 119.0 GB   disk2s1
           2:                DOS_FAT_32 SD_CARD                 64.0 GB    disk2s2
        """
        
        mock_run.side_effect = [mock_info_res, mock_list_res]
        
        with patch("pathlib.Path.exists", return_value=True):
            # Test HDD default
            mounts = MountDetector.detect_from_device_storage("/Volumes/ROCKBOX")
            assert mounts == ["/<HDD0>", "/<HDD1>"]
            
            # Test MMC (Sansa target)
            # Need to mock rockbox-info.txt specifically if logic attempts to read it
            # The code checks info_file.exists()
            # If we mock Path.exists=True generally, rockbox-info.txt exists.
            
            # We need separate context for MMC to override read_text
            with patch("pathlib.Path.read_text", return_value="Target: sansa"):
                 mock_run.side_effect = [mock_info_res, mock_list_res] # Reset side effect
                 mounts = MountDetector.detect_from_device_storage("/Volumes/SANSA")
                 assert mounts == ["/<MMC0>", "/<MMC1>"]

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_detect_from_device_storage_linux(self, mock_run, mock_platform):
        # Mock findmnt
        mock_find_res = MagicMock()
        mock_find_res.returncode = 0
        mock_find_res.stdout = "/dev/sdb1"
        
        # Mock lsblk
        mock_lsblk_res = MagicMock()
        mock_lsblk_res.returncode = 0
        mock_lsblk_res.stdout = """
        sdb1 vfat
        sdb2 exfat
        """
        
        mock_run.side_effect = [mock_find_res, mock_lsblk_res]
        
        with patch("pathlib.Path.exists", return_value=True):
            mounts = MountDetector.detect_from_device_storage("/media/ROCKBOX")
            assert mounts == ["/<HDD0>", "/<HDD1>"]

    @patch("platform.system", return_value="Windows")
    @patch("os.path.splitdrive", return_value=("E:", "\\"))
    def test_detect_from_device_storage_windows(self, mock_split, mock_platform):
        with patch("pathlib.Path.exists", return_value=True):
            mounts = MountDetector.detect_from_device_storage("E:\\")
            assert mounts == ["/<HDD0>"]

    @patch("platform.system", return_value="Unknown")
    def test_detect_from_device_storage_unknown(self, mock_platform):
        with patch("pathlib.Path.exists", return_value=True):
            mounts = MountDetector.detect_from_device_storage("/path")
            assert mounts == ["/<HDD0>"] # Fallback

    def test_detect_from_device_storage_missing_path(self):
         with patch("pathlib.Path.exists", return_value=False):
             mounts = MountDetector.detect_from_device_storage("/missing")
             assert mounts == []

    # --- Rockbox Info Tests ---

    def test_detect_from_rockbox_info(self):
        with patch.object(MountDetector, "detect_from_device_storage", return_value=["/<MMC0>"]) as mock_detect:
            res = MountDetector.detect_from_rockbox_info("/Volumes/DAP/.rockbox")
            assert res == "/<MMC0>"
            mock_detect.assert_called_with("/Volumes/DAP")
            
            mock_detect.reset_mock()
            res = MountDetector.detect_from_rockbox_info("/Volumes/DAP")
            mock_detect.assert_called_with("/Volumes/DAP")

    def test_suggest_mount_notation(self):
        # Case 1: Detects successfully
        with patch.object(MountDetector, "detect_from_device_storage", return_value=["/<MMC0>"]):
            res = MountDetector.suggest_mount_notation("/Volumes/DAP")
            assert res == "/<MMC0>"
            
        # Case 2: Detection returns empty (e.g. error) -> Fallback
        with patch.object(MountDetector, "detect_from_device_storage", return_value=[]):
            res = MountDetector.suggest_mount_notation("/Volumes/DAP")
            assert res == "/<HDD0>" # Default fallback from suggest_mount_notation logic?
            # Code says: if mounts: return mounts[0]. Else return "/<HDD0>"
            
        # Case 3: No path provided
        res = MountDetector.suggest_mount_notation(None)
        assert res == "/<HDD0>"

    # --- DB Detection Tests ---

    @patch("dap_db_manager.tagging.tag.tagfile.TagFile.read")
    def test_detect_mounts_success(self, mock_read):
        path_file = MagicMock()
        entry1 = MagicMock()
        entry1.data = "/<HDD0>/Music/1.mp3"
        entry2 = MagicMock()
        entry2.data = "/<HDD0>/Music/2.mp3"
        entry3 = MagicMock()
        entry3.data = "/<HDD1>/Music/3.mp3"
        
        path_file.entries = [entry1, entry2, entry3]
        mock_read.return_value = path_file
        
        with patch("pathlib.Path.exists", return_value=True):
            mounts = MountDetector.detect_mounts("/path/.rockbox")
            
            assert len(mounts) == 2
            assert "/<HDD0>" in mounts
            assert mounts["/<HDD0>"].count == 2
            assert "/<HDD1>" in mounts
            assert mounts["/<HDD1>"].count == 1

    @patch("dap_db_manager.tagging.tag.tagfile.TagFile.read")
    def test_detect_mounts_no_notations(self, mock_read):
        path_file = MagicMock()
        entry1 = MagicMock()
        entry1.data = "/Music/1.mp3" 
        path_file.entries = [entry1]
        mock_read.return_value = path_file
        
        with patch("pathlib.Path.exists", return_value=True):
            mounts = MountDetector.detect_mounts("/path/.rockbox")
            assert len(mounts) == 0

    def test_detect_mounts_file_not_found(self):
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                MountDetector.detect_mounts("/path")

    # --- Helper Integrations ---

    def test_get_primary_mount(self):
        with patch.object(MountDetector, "detect_mounts") as mock_detect:
            # Case 1: Multiple mounts
            hdd0 = MountInfo("/<HDD0>", 100, [])
            hdd1 = MountInfo("/<HDD1>", 50, [])
            mock_detect.return_value = {"/<HDD0>": hdd0, "/<HDD1>": hdd1}
            
            assert MountDetector.get_primary_mount("/path") == "/<HDD0>"
            
            # Case 2: None
            mock_detect.return_value = {}
            assert MountDetector.get_primary_mount("/path") is None
            
            # Case 3: Exception
            mock_detect.side_effect = Exception
            assert MountDetector.get_primary_mount("/path") is None

    def test_print_mount_summary(self):
        with patch.object(MountDetector, "detect_mounts") as mock_detect, \
             patch("builtins.print") as mock_print:
            
            # Case 1: Success
            hdd0 = MountInfo("/<HDD0>", 100, ["/sample"])
            mock_detect.return_value = {"/<HDD0>": hdd0}
            MountDetector.print_mount_summary("/path")
            assert mock_print.call_count > 0
            
            # Case 2: No mounts
            mock_print.reset_mock()
            mock_detect.return_value = {}
            MountDetector.print_mount_summary("/path")
            mock_print.assert_any_call("No Rockbox mount notation detected in database.")

            # Case 3: Exception
            mock_print.reset_mock()
            mock_detect.side_effect = Exception("Boom")
            MountDetector.print_mount_summary("/path")
            mock_print.assert_called_with("Error detecting mounts: Boom")
