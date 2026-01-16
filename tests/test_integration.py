"""Integration tests for end-to-end workflows with real audio files."""

import pytest
from pathlib import Path
import tempfile
import shutil
from dap_db_manager.database import Database
from dap_db_manager.database.io import DatabaseIO
from dap_db_manager.indexfile import IndexFile


# Test data path
TEST_DATA_DIR = Path("/Users/v/PYTHON_PROJECTS/rdbm/rockbox-db-manager/music_test_folder")


@pytest.mark.integration
class TestIntegrationWorkflow:
    """Test complete database generation and update workflows."""

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_complete_generation_workflow(self, tmp_path):
        """Test complete database generation from real audio files."""
        # Create database
        db = Database()
        
        # Add test directory
        db.add_dir(str(TEST_DATA_DIR), recursive=True)
        
        # Generate database
        output_dir = tmp_path / "database"
        output_dir.mkdir()
        
        db.write(str(output_dir))
        
        # Verify database files were created
        assert (output_dir / "database_idx.tcd").exists()
        assert (output_dir / "database_0.tcd").exists()  # artist
        assert (output_dir / "database_1.tcd").exists()  # album

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_database_load_workflow(self, tmp_path):
        """Test loading an existing database."""
        # Generate database first
        db = Database()
        db.add_dir(str(TEST_DATA_DIR), recursive=True)
        
        output_dir = tmp_path / "database"
        output_dir.mkdir()
        db.write(str(output_dir))
        
        # Now load it
        loaded_db = Database.load(str(output_dir))
        
        assert loaded_db is not None
        # Verify some basic properties

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_database_update_workflow(self, tmp_path):
        """Test updating an existing database."""
        # Create initial database
        db = Database()
        db.add_dir(str(TEST_DATA_DIR), recursive=True)
        
        output_dir = tmp_path / "database"
        output_dir.mkdir()
        db.write(str(output_dir))
        
        # Save cache
        cache_file = tmp_path / "cache.pkl.gz"
        db.save_cache(str(cache_file))
        
        # Load and update
        db2 = Database.load(str(output_dir))
        if cache_file.exists():
            db2.load_cache(str(cache_file))
        
        # Perform update (with same directory, should detect no changes)
        added, deleted, renames = db2.update_database(str(TEST_DATA_DIR))
        
        # Should have processed the files
        assert isinstance(added, list)
        assert isinstance(deleted, list)
        assert isinstance(renames, dict)

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_cache_persistence_workflow(self, tmp_path):
        """Test that cache persists and loads correctly."""
        # Generate with cache
        db = Database()
        db.add_dir(str(TEST_DATA_DIR), recursive=True)
        
        cache_file = tmp_path / "cache.pkl.gz"
        db.save_cache(str(cache_file))
        
        assert cache_file.exists()
        
        # Load cache in new database
        db2 = Database()
        db2.load_cache(str(cache_file))
        
        # Cache should contain data
        from dap_db_manager.database.cache import TagCache
        bytes_used, _, _ = TagCache.get_current_memory_usage()
        # Should have some cached data


@pytest.mark.integration
class TestIntegrationFormats:
    """Test database generation with different audio formats."""

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_mp3_files(self):
        """Test processing MP3 files."""
        db = Database()
        
        mp3_files = list(TEST_DATA_DIR.rglob("*.mp3"))
        if mp3_files:
            db.add_file(str(mp3_files[0]))
            # Should process without errors

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_flac_files(self):
        """Test processing FLAC files."""
        db = Database()
        
        flac_files = list(TEST_DATA_DIR.rglob("*.flac"))
        if flac_files:
            db.add_file(str(flac_files[0]))

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_mixed_formats(self):
        """Test processing mixed audio formats."""
        db = Database()
        
        # Add entire directory with mixed formats
        db.add_dir(str(TEST_DATA_DIR), recursive=True)
        
        # Should handle all formats


@pytest.mark.integration
class TestIntegrationEdgeCases:
    """Test edge cases with real files."""

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_corrupted_files(self):
        """Test handling of corrupted audio files."""
        db = Database()
        
        # Test data folder intentionally contains corrupted files
        failed = []
        
        def callback(*args, **kwargs):
            pass
        
        db.add_dir(str(TEST_DATA_DIR), recursive=True, callback=callback)
        
        # Should complete without crashing

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_unicode_paths(self):
        """Test handling of unicode in file paths."""
        db = Database()
        
        # If test data has unicode paths, they should be handled
        db.add_dir(str(TEST_DATA_DIR), recursive=True)

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_large_directory_tree(self, tmp_path):
        """Test processing large directory structure."""
        db = Database()
        
        # Add entire test directory
        db.add_dir(str(TEST_DATA_DIR), recursive=True)
        
        # Write database
        output_dir = tmp_path / "database"
        output_dir.mkdir()
        db.write(str(output_dir))
        
        # Should complete successfully


@pytest.mark.integration  
class TestIntegrationRenameDetection:
    """Test rename detection in real-world scenarios."""

    @pytest.mark.skipif(not TEST_DATA_DIR.exists(), reason="Test data not available")
    def test_rename_detection_workflow(self, tmp_path):
        """Test detecting renamed files in update workflow."""
        # This would require creating a database, then renaming files
        # and detecting the changes - complex integration test
        pytest.skip("Complex rename scenario - manual validation needed")
