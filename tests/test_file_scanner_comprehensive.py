
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY
from concurrent.futures import ProcessPoolExecutor, Future

# Import the module under test
from dap_db_manager.database.file_scanner import (
    FileScanner,
    read_single_file_tags,
    warn_no_tags,
    myprint
)
from dap_db_manager.database.cache import TagCache

class TestFileScannerComprehensive:

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # Reset cache before/after tests
        TagCache._cache.clear()
        TagCache._dirty = False
        yield
        TagCache._cache.clear()

    # --- Standalone Function Tests ---

    @patch("pathlib.Path.stat")
    def test_read_single_file_tags_success(self, mock_stat):
        # Setup
        path = "/music/song.mp3"
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_size = 1024
        mock_stat_obj.st_mtime = 1600000000
        mock_stat.return_value = mock_stat_obj
        
        mock_tags = {"title": "Test Title"}
        mock_tagging = MagicMock()
        mock_tagging.read.return_value = mock_tags

        mock_dap_db_manager = MagicMock()
        mock_dap_db_manager.tagging = mock_tagging

        # Patch sys.modules to handle the local import 'from dap_db_manager import tagging'
        with patch.dict("sys.modules", {"dap_db_manager": mock_dap_db_manager, "dap_db_manager.tagging": mock_tagging}):
            # Execute
            result = read_single_file_tags(path)

        # Verify
        assert result == (path, 1024, 1600000000, mock_tags)
        mock_tagging.read.assert_called_once_with(path)

    @patch("pathlib.Path.stat")
    def test_read_single_file_tags_cached_hit(self, mock_stat):
        # Setup cache hit
        path = "/music/song.mp3"
        lower_path = path.lower()
        size = 1024
        mtime = 1600000000
        cached_tags = {"title": "Cached Title"}
        
        # Pre-populate cache
        TagCache._cache[lower_path] = ((size, mtime), cached_tags)

        # Mock stat to match cache
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_size = size
        mock_stat_obj.st_mtime = mtime
        mock_stat.return_value = mock_stat_obj

        mock_tagging = MagicMock()
        mock_dap_db_manager = MagicMock()
        mock_dap_db_manager.tagging = mock_tagging

        with patch.dict("sys.modules", {"dap_db_manager": mock_dap_db_manager, "dap_db_manager.tagging": mock_tagging}):
             # Execute
            result = read_single_file_tags(path)

        # Verify - should retrieve from cache and NOT call tagging.read
        assert result == (path, size, mtime, cached_tags)
        mock_tagging.read.assert_not_called()

    @patch("pathlib.Path.stat")
    def test_read_single_file_tags_cached_miss_changed(self, mock_stat):
        # Setup cache miss (file changed)
        path = "/music/song.mp3"
        lower_path = path.lower()
        
        # Cache has OLD data
        TagCache._cache[lower_path] = ((1024, 1500000000), {})

        # File on disk is NEWER
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_size = 1024
        mock_stat_obj.st_mtime = 1600000000 # changed
        mock_stat.return_value = mock_stat_obj
        
        mock_tags = {"title": "New Title"}
        mock_tagging = MagicMock()
        mock_tagging.read.return_value = mock_tags

        mock_dap_db_manager = MagicMock()
        mock_dap_db_manager.tagging = mock_tagging

        with patch.dict("sys.modules", {"dap_db_manager": mock_dap_db_manager, "dap_db_manager.tagging": mock_tagging}):
            # Execute
            result = read_single_file_tags(path)

        # Verify - should call tagging.read
        assert result == (path, 1024, 1600000000, mock_tags)
        mock_tagging.read.assert_called_once_with(path)

    @patch("pathlib.Path.stat")
    def test_read_single_file_tags_import_error(self, mock_stat):
        # Simulate ImportError during 'from dap_db_manager import tagging'
        # We achieve this by patching sys.modules but ensuring access raises ImportError, or simply not having it?
        # Actually simplest is to ensure looking up 'dap_db_manager' raises ImportError
        
        # We can't easily mock ImportError via patch.dict on sys.modules because it just does lookup.
        # But we can patch builtins.__import__ IF we dared.
        # Alternatively, we can use side_effect on a property access if simple import was doing that... but it's a statement.
        
        # Best bet: Use context manager that un-sets the module?
        # If 'dap_db_manager' is missing from sys.modules, normal import machinery runs.
        # If we can't find it, ImportError.
        
        path = "/music/song.mp3" 
        
        with patch.dict("sys.modules"):
            # Remove relevant modules temporarily
            sys.modules.pop("dap_db_manager", None)
            sys.modules.pop("dap_db_manager.tagging", None)
            
            # The test runner environment puts src in path, so it might still invoke real import.
            # To force failure, we can patch builtins.__import__
            with patch("builtins.__import__", side_effect=ImportError("Mocked Import Error")):
                result = read_single_file_tags(path)
                assert result == (path, None, None, None)

    @patch("pathlib.Path.stat")
    def test_read_single_file_tags_usage_error(self, mock_stat):
        # Error during usage of tagging module (e.g. read fails)
        path = "/music/song.mp3"
        mock_stat.return_value.st_size = 100
        mock_stat.return_value.st_mtime = 200
        
        mock_tagging = MagicMock()
        mock_tagging.read.side_effect = Exception("Read Failed")
        
        mock_dap_db_manager = MagicMock()
        mock_dap_db_manager.tagging = mock_tagging
        
        with patch.dict("sys.modules", {"dap_db_manager": mock_dap_db_manager, "dap_db_manager.tagging": mock_tagging}):
            result = read_single_file_tags(path)
            assert result == (path, None, None, None)

    @patch("pathlib.Path.stat")
    def test_read_single_file_tags_stat_error(self, mock_stat):
        # Setup error
        path = "/music/bad.mp3"
        mock_stat.side_effect = OSError("File not found")
        
        # Execute
        result = read_single_file_tags(path)
        
        # Verify tuple structure for failure
        assert result == (path, None, None, None)

    # --- FileScanner Class Tests ---

    def test_init_workers(self):
        with patch("os.cpu_count", return_value=4):
            scanner = FileScanner(use_multiprocessing=True)
            assert scanner.max_workers == 4
            scanner.shutdown()

            scanner = FileScanner(use_multiprocessing=False)
            assert scanner.max_workers == 8 # min(32, 4 + 4)
            scanner.shutdown()
            
            # Explicit workers
            scanner = FileScanner(max_workers=2)
            assert scanner.max_workers == 2
            scanner.shutdown()

    def test_read_tags_internal_error(self):
        # cover _read_tags exception handling
        scanner = FileScanner()
        with patch("dap_db_manager.database.file_scanner.tagging") as mock_tagging:
            mock_tagging.read.side_effect = Exception("Boom")
            result = scanner._read_tags("/path/to/file.mp3")
            assert result is None
        scanner.shutdown()

    @patch("dap_db_manager.database.file_scanner.read_single_file_tags")
    def test_read_tags_batch(self, mock_read_single):
        # Test parallel execution flow mocking ProcessPoolExecutor behavior
        scanner = FileScanner(max_workers=2, use_multiprocessing=True)
        
        mock_executor = MagicMock()
        scanner._executor = mock_executor
        
        file_paths = ["/a.mp3", "/b.mp3"]
        
        # Setup futures
        f1 = Future()
        f1.set_result(("/a.mp3", 100, 1000, {}))
        f2 = Future()
        f2.set_result(("/b.mp3", 100, 1000, {}))
        
        mock_executor.submit.side_effect = [f1, f2]
        
        results = scanner.read_tags_batch(file_paths)
        
        assert len(results) == 2
        assert ("/a.mp3", 100, 1000, {}) in results
        assert ("/b.mp3", 100, 1000, {}) in results
        
        assert mock_executor.submit.call_count == 2
        
        scanner.shutdown()

    def test_add_files_sequential(self):
        # Test add_files which calls _add_file_internal sequentially
        scanner = FileScanner(max_workers=1)
        
        paths_set = set()
        failed_list = []
        files = ["/music/song1.mp3", "/music/song2.mp3"]
        
        with patch.object(scanner, "_add_file_internal") as mock_add_internal:
            scanner.add_files(files, paths_set, failed_list)
            
            assert mock_add_internal.call_count == 2
            mock_add_internal.assert_has_calls([
                call("/music/song1.mp3", paths_set, failed_list),
                call("/music/song2.mp3", paths_set, failed_list)
            ])
            
        scanner.shutdown()

    @patch("os.scandir")
    def test_add_dir_parallel_logic(self, mock_scandir):
        # This tests the parallel processing branch in add_dir
        scanner = FileScanner(use_multiprocessing=True) # use_parallel default is True logic in add_dir
        
        # Setup a mock directory structure with enough files to trigger parallel batching (default batch=100)
        # We need > 100 files
        file_entries = []
        for i in range(150):
            entry = MagicMock()
            entry.is_file.return_value = True
            entry.is_dir.return_value = False
            entry.path = f"/music/song{i}.mp3"
            entry.name = f"song{i}.mp3"
            file_entries.append(entry)
            
        # Mock context manager for scandir
        mock_scandir_ctx = MagicMock()
        mock_scandir_ctx.__enter__.return_value = file_entries
        mock_scandir_ctx.__exit__.return_value = None
        mock_scandir.return_value = mock_scandir_ctx
        
        paths_set = set()
        failed_list = []
        
        # Mock read_tags_batch to return dummy results instantly
        def side_effect_read_batch(batch):
            return [(p, 100, 1000, {}) for p in batch]
            
        with patch.object(scanner, "read_tags_batch", side_effect=side_effect_read_batch) as mock_read_batch:
            # Also mock _add_file_internal to verified it gets called with results
            with patch.object(scanner, "_add_file_internal") as mock_add_internal:
                
                scanner.add_dir("/music", paths_set, failed_list, use_parallel=True)
                
                # Should have been called in batches
                # 150 files -> batch 100, batch 50 -> 2 calls to read_tags_batch
                assert mock_read_batch.call_count == 2
                
                # _add_file_internal should be called for each file (150 times)
                assert mock_add_internal.call_count == 150
                
        scanner.shutdown()

    @patch("os.scandir")
    def test_add_dir_recursive(self, mock_scandir):
        scanner = FileScanner()
        
        # Define directory structure
        # /root
        #   /root/subdir
        #     file2.mp3
        #   file1.mp3
        
        entry_file1 = MagicMock()
        entry_file1.is_file.return_value = True
        entry_file1.is_dir.return_value = False
        entry_file1.path = "/root/file1.mp3"
        entry_file1.name = "file1.mp3"
        
        entry_subdir = MagicMock()
        entry_subdir.is_file.return_value = False
        entry_subdir.is_dir.return_value = True
        entry_subdir.path = "/root/subdir"
        entry_subdir.name = "subdir"
        
        entry_file2 = MagicMock()
        entry_file2.is_file.return_value = True
        entry_file2.is_dir.return_value = False
        entry_file2.path = "/root/subdir/file2.mp3"
        entry_file2.name = "file2.mp3"
        
        # Mock scandir to return different contents based on path arg
        # os.scandir(path) is called.
        
        def mock_scandir_side_effect(path):
            ctx = MagicMock()
            if path == "/root":
                ctx.__enter__.return_value = [entry_file1, entry_subdir]
            elif path == "/root/subdir":
                ctx.__enter__.return_value = [entry_file2]
            else:
                ctx.__enter__.return_value = []
            return ctx
            
        mock_scandir.side_effect = mock_scandir_side_effect
        
        paths_set = set()
        failed_list = []
        dircallback = MagicMock()
        
        # Use sequential (use_parallel=False) for simpler flow verification
        with patch.object(scanner, "_add_file_internal") as mock_add_internal:
            scanner.add_dir("/root", paths_set, failed_list, recursive=True, use_parallel=False, dircallback=dircallback)
            
            # Verify calls
            mock_add_internal.assert_any_call("/root/file1.mp3", paths_set, failed_list)
            mock_add_internal.assert_any_call("/root/subdir/file2.mp3", paths_set, failed_list)
        
        dircallback.assert_any_call("/root/subdir")
        scanner.shutdown()

    def test_missing_tags_handling(self):
        # Verify _add_file_internal handles read failures (None tags)
        scanner = FileScanner()
        paths_set = set()
        failed_list = []
        
        path = "/music/corrupt.mp3"
        
        # Mock stat
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 123
            mock_stat.return_value.st_mtime = 456
            
            # Mock Cache get (miss)
            with patch("dap_db_manager.database.cache.TagCache.get", side_effect=KeyError):
                # Mock read failure
                with patch("dap_db_manager.database.file_scanner.tagging.read", side_effect=Exception("Read Err")):
                    
                    scanner._add_file_internal(path, paths_set, failed_list)
                    
                    assert path in failed_list
                    assert len(paths_set) == 0
                    
        scanner.shutdown()

    def test_warn_no_tags(self):
        with patch("logging.warning") as mock_warn:
            warn_no_tags()
            mock_warn.assert_called_once()
            
    def test_myprint(self):
        with patch("sys.stdout.write") as mock_write:
            myprint("hello", "world", sep="-")
            mock_write.assert_called_with("hello-world\n")

    def test_context_manager(self):
        with FileScanner() as scanner:
            assert not scanner._shutdown
        assert scanner._shutdown

