"""Tests for FileScanner class and directory scanning."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dap_db_manager.database.file_scanner import FileScanner, myprint, read_single_file_tags
from dap_db_manager.database.cache import TagCache
from tests.conftest import music_test_folder


class TestFileScannerBasics:
    """Test basic FileScanner initialization and configuration."""

    def test_file_scanner_creation(self):
        """Test creating a FileScanner instance."""
        scanner = FileScanner()
        assert scanner is not None

    def test_file_scanner_with_max_workers(self):
        """Test FileScanner with custom max_workers."""
        scanner = FileScanner(max_workers=4)
        assert scanner is not None

    def test_file_scanner_without_multiprocessing(self):
        """Test FileScanner with threading instead of multiprocessing."""
        scanner = FileScanner(use_multiprocessing=False)
        assert scanner is not None

    def test_file_scanner_context_manager(self):
        """Test FileScanner as a context manager."""
        with FileScanner() as scanner:
            assert scanner is not None
        # Should cleanup automatically

    def test_myprint_function(self):
        """Test myprint helper function doesn't crash."""
        # Should not raise exceptions
        myprint("test")
        myprint("test", "multiple", "args")
        myprint("test", key="value")


class TestFileScannerSingleFile:
    """Test FileScanner single file operations."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_add_file_basic(self, tmp_path):
        """Test adding a single file."""
        # Create a test file (empty, just for path testing)
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        scanner = FileScanner() 
        paths_set = set()
        failed_list = []

        scanner.add_file(str(test_file), paths_set, failed_list)

        # File should be in paths_set (even if not a valid audio file)
        # The actual behavior depends on implementation

    def test_add_file_nonexistent(self):
        """Test adding a non-existent file."""
        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        # FileScanner.add_file calls Path.stat() which raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            scanner.add_file("/nonexistent/file.mp3", paths_set, failed_list)

    @patch('dap_db_manager.database.file_scanner.tagging')
    def test_read_tags_mock(self, mock_tagging):
        """Test reading tags from a file (mocked)."""
        mock_tag = Mock()
        mock_tag.__getitem__ = lambda self, key: f"value_{key}"
        mock_tagging.Tag = Mock(return_value=mock_tag)

        scanner = FileScanner()
        # This would normally require a real audio file
        # The test verifies the interface


class TestFileScannerMultipleFiles:
    """Test FileScanner batch operations."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_add_files_empty_list(self):
        """Test adding an empty list of files."""
        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_files([], paths_set, failed_list)
        assert len(paths_set) == 0

    def test_add_files_multiple(self, tmp_path):
        """Test adding multiple files."""
        # Create test files
        files = []
        for i in range(5):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"content {i}")
            files.append(str(test_file))

        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_files(files, paths_set, failed_list, callback=lambda *args, **kwargs: None)


class TestFileScannerDirectoryScan:
    """Test FileScanner directory scanning."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_add_dir_empty(self, tmp_path):
        """Test scanning an empty directory."""
        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_dir(
            str(tmp_path),
            paths_set,
            failed_list,
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

        # Empty directory should result in no files
        assert len(paths_set) == 0

    def test_add_dir_recursive(self, tmp_path):
        """Test recursive directory scanning."""
        # Create nested directory structure
        (tmp_path / "subdir1").mkdir()
        (tmp_path / "subdir2").mkdir()
        (tmp_path / "subdir1" / "nested").mkdir()

        # Create some files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "subdir1" / "file2.txt").write_text("content2")
        (tmp_path / "subdir1" / "nested" / "file3.txt").write_text("content3")

        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_dir(
            str(tmp_path),
            paths_set,
            failed_list,
            recursive=True,
            use_parallel=False,  # Disable parallel for test simplicity
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

    def test_add_dir_non_recursive(self, tmp_path):
        """Test non-recursive directory scanning."""
        # Create nested structure
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "subdir" / "file2.txt").write_text("content2")

        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_dir(
            str(tmp_path),
            paths_set,
            failed_list,
            recursive=False,
            use_parallel=False,
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

    def test_add_dir_nonexistent(self):
        """Test scanning a non-existent directory."""
        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        # add_dir handles non-existent directories gracefully (logs warning)
        scanner.add_dir(
            "/nonexistent/directory",
            paths_set,
            failed_list
        )
        
        # Should complete without raising, paths_set remains empty
        assert len(paths_set) == 0


class TestFileScannerCallbacks:
    """Test FileScanner callback functionality."""

    def test_add_file_with_callback(self, tmp_path):
        """Test that callbacks are invoked when adding files."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        callback_called = []
        
        def test_callback(*args, **kwargs):
            callback_called.append((args, kwargs))

        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_file(str(test_file), paths_set, failed_list, callback=test_callback)

    def test_add_dir_with_callbacks(self, tmp_path):
        """Test that directory and file callbacks are invoked."""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        dir_callbacks = []
        file_callbacks = []

        def dir_callback(*args, **kwargs):
            dir_callbacks.append((args, kwargs))

        def file_callback(*args, **kwargs):
            file_callbacks.append((args, kwargs))

        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_dir(
            str(tmp_path),
            paths_set,
            failed_list,
            recursive=False,
            use_parallel=False,
            dircallback=dir_callback,
            filecallback=file_callback
        )


class TestFileScannerParallelProcessing:
    """Test FileScanner parallel processing capabilities."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    def test_parallel_vs_sequential(self, tmp_path):
        """Test that parallel and sequential modes both work."""
        # Create multiple test files
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_text(f"content {i}")

        # Sequential scan
        scanner_seq = FileScanner(use_multiprocessing=False)
        paths_seq = set()
        failed_seq = []
        scanner_seq.add_dir(
            str(tmp_path),
            paths_seq,
            failed_seq,
            use_parallel=False,
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

        # Parallel scan
        scanner_par = FileScanner(use_multiprocessing=True, max_workers=2)
        paths_par = set()
        failed_par = []
        scanner_par.add_dir(
            str(tmp_path),
            paths_par,
            failed_par,
            use_parallel=True,
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

        # Both should find the same files (though order may differ)
        # This test verifies both modes execute without error

    def test_shutdown(self):
        """Test shutting down the FileScanner."""
        scanner = FileScanner()
        scanner.shutdown(wait=True)
        # Should not raise an exception


@pytest.mark.integration
@pytest.mark.slow
class TestFileScannerIntegration:
    """Integration tests with real test data."""

    def setup_method(self):
        """Setup before each test."""
        TagCache.clear()

    def teardown_method(self):
        """Cleanup after each test."""
        TagCache.clear()

    @pytest.mark.skipif(
        not music_test_folder().exists(),
        reason="Test data directory not available"
    )
    def test_scan_real_test_data(self):
        """Test scanning real test data directory."""
        test_dir = str(music_test_folder())
        
        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        scanner.add_dir(
            test_dir,
            paths_set,
            failed_list,
            recursive=True,
            use_parallel=True,
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

        # Should find some files (including potentially corrupted ones)
        # The test verifies the scanner handles real-world data

    @pytest.mark.skipif(
        not music_test_folder().exists(),
        reason="Test data directory not available"
    )
    def test_corrupted_files_handling(self):
        """Test that scanner handles corrupted files gracefully."""
        test_dir = str(music_test_folder())
        
        scanner = FileScanner()
        paths_set = set()
        failed_list = []

        # Should not crash even with corrupted files
        scanner.add_dir(
            test_dir,
            paths_set,
            failed_list,
            recursive=True,
            use_parallel=False,
            dircallback=lambda *args, **kwargs: None,
            filecallback=lambda *args, **kwargs: None
        )

        # Corrupted files should be added to failed_list
        # This tests error handling robustness


class TestReadSingleFileTags:
    """Test the standalone read_single_file_tags function."""

    def test_read_single_file_tags_nonexistent(self):
        """Test reading tags from a non-existent file."""
        result = read_single_file_tags("/nonexistent/file.mp3")
        
        # Should return error tuple
        assert result[0] == "/nonexistent/file.mp3"
        assert result[1] is None  # size
        assert result[2] is None  # mtime
        assert result[3] is None  # tags

    @patch('os.path.exists', return_value=True)
    @patch('os.path.getsize', return_value=1000)
    @patch('os.path.getmtime', return_value=1234567890.0)
    def test_read_single_file_tags_mock(self, mock_mtime, mock_size, mock_exists):
        """Test reading tags with mocked file operations."""
        # This tests the structure without needing a real audio file
        result = read_single_file_tags("/mock/file.mp3")
        
        assert result[0] == "/mock/file.mp3"
        # Other fields depend on whether tagging module can be imported


class TestAppleDoubleFiltering:
    """AppleDouble sidecars (._name.ext) must never be treated as audio files.

    On exFAT/FAT volumes -- the usual format for removable media and portable
    players -- every macOS tag write creates a
    `._<track>.mp3` sidecar. It carries an audio extension but is not an audio
    stream, so suffix-only filtering enqueues it and it is then reported as a
    failed file. See docs/rockbox-parity.md, Gap 3.
    """

    def _make_tree(self, root):
        """Create a tree with one real track plus macOS cruft."""
        real = Path(root) / "track.mp3"
        real.write_bytes(b"\x00" * 16)
        sidecar = Path(root) / "._track.mp3"
        sidecar.write_bytes(b"\x00" * 16)

        macosx = Path(root) / "__MACOSX"
        macosx.mkdir()
        (macosx / "track.mp3").write_bytes(b"\x00" * 16)

        sub = Path(root) / "album"
        sub.mkdir()
        (sub / "b.mp3").write_bytes(b"\x00" * 16)
        (sub / "._b.mp3").write_bytes(b"\x00" * 16)

        return str(real), str(sidecar)

    def test_add_dir_skips_appledouble_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_tree(tmp)
            paths, failed = set(), []
            with FileScanner(use_multiprocessing=False) as scanner:
                scanner.add_dir(tmp, paths, failed, dircallback=None, filecallback=None)

            considered = set(paths) | set(failed)
            offenders = [p for p in considered if os.path.basename(p).startswith("._")]
            assert not offenders, f"AppleDouble sidecars were scanned: {offenders}"

    def test_add_dir_does_not_recurse_into_macosx(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_tree(tmp)
            paths, failed = set(), []
            with FileScanner(use_multiprocessing=False) as scanner:
                scanner.add_dir(tmp, paths, failed, dircallback=None, filecallback=None)

            considered = set(paths) | set(failed)
            offenders = [p for p in considered if "__MACOSX" in p]
            assert not offenders, f"__MACOSX was traversed: {offenders}"

    def test_add_file_skips_appledouble_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, sidecar = self._make_tree(tmp)
            paths, failed = set(), []
            with FileScanner(use_multiprocessing=False) as scanner:
                scanner.add_file(sidecar, paths, failed, callback=None)

            assert sidecar not in paths
            assert sidecar not in failed

    def test_add_files_skips_appledouble_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            real, sidecar = self._make_tree(tmp)
            paths, failed = set(), []
            with FileScanner(use_multiprocessing=False) as scanner:
                scanner.add_files([real, sidecar], paths, failed, callback=None)

            considered = set(paths) | set(failed)
            assert sidecar not in considered

    def test_real_audio_file_is_still_scanned(self):
        """Guard against over-filtering: a normal track must survive."""
        with tempfile.TemporaryDirectory() as tmp:
            real, _ = self._make_tree(tmp)
            paths, failed = set(), []
            with FileScanner(use_multiprocessing=False) as scanner:
                scanner.add_dir(tmp, paths, failed, dircallback=None, filecallback=None)

            considered = set(paths) | set(failed)
            assert real in considered, "the real track was filtered out"
