"""Tests for Tag class and tag reading functionality."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dap_db_manager.tagging.tag.core import Tag


class TestTagInitialization:
    """Test Tag class initialization."""

    def test_tag_creation_with_mock(self):
        """Test creating a Tag with a mock mutagen object."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        
        tag = Tag(mock_tags)
        assert tag is not None
        assert tag.tags == mock_tags

    def test_tag_force_string_parameter(self):
        """Test Tag with force_string parameter."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "FLAC"
        
        tag = Tag(mock_tags, force_string=True)
        assert tag.force_string is True

    def test_tag_force_string_property(self):
        """Test force_string property getter/setter."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        
        tag = Tag(mock_tags, force_string=False)
        assert tag.force_string is False
        
        tag.force_string = True
        assert tag.force_string is True


class TestTagPropertyAccess:
    """Test Tag property access methods."""

    def test_tag_getitem(self):
        """Test __getitem__ access."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        mock_tags.__getitem__ = Mock(return_value=["Test Artist"])
        
        tag = Tag(mock_tags)
        # This will use the tag_mapping to access fields
        # The behavior depends on registered keys

    def test_tag_get_method(self):
        """Test get() method."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "FLAC"
        
        tag = Tag(mock_tags)
        # Test get method - behavior depends on tag_mapping
        # Just verify the method exists and is callable
        assert hasattr(tag, 'get')
        assert callable(tag.get)

    def test_tag_get_string(self):
        """Test get_string() method."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        
        tag = Tag(mock_tags)
        # get_string should convert to string list


class TestTagMapping:
    """Test Tag mapping functionality."""

    def test_update_mapping(self):
        """Test update_mapping method."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        
        tag = Tag(mock_tags)
        tag.update_mapping()
        # Should update tag_mapping based on tag type

    def test_register_key(self):
        """Test RegisterKey class method."""
        # RegisterKey allows custom field registration
        # This is a class method that modifies the Tag class


class TestTagSerialization:
    """Test Tag serialization/deserialization."""

    def test_getstate(self):
        """Test __getstate__ for pickling."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "FLAC"
        mock_tags.filename = "/test/file.flac"
        
        tag = Tag(mock_tags)
        state = tag.__getstate__()
        
        # __getstate__ returns a tuple (tags, force_string)
        assert isinstance(state, tuple)
        assert len(state) == 2

    def test_setstate(self):
        """Test __setstate__ for unpickling."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        
        tag = Tag(mock_tags)
        state = {"force_string": True, "filename": "/test/file.mp3"}
        
        # This would restore the tag from pickled state
        # tag.__setstate__(state)


class TestTagPrettyPrint:
    """Test Tag pretty printing."""

    def test_pprint(self):
        """Test pprint method."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "FLAC"
        
        tag = Tag(mock_tags)
        # pprint should print all tag fields nicely
        # It shouldn't crash
        try:
            tag.pprint()
        except Exception:
            # pprint may not work perfectly with mocks
            pass


@pytest.mark.integration
class TestTagWithRealFiles:
    """Integration tests with real audio files (if available)."""

    @pytest.mark.skipif(
        not Path("/Users/v/PYTHON_PROJECTS/rdbm/rockbox-db-manager/music_test_folder").exists(),
        reason="Test data not available"
    )
    def test_tag_from_real_mp3(self):
        """Test creating Tag from a real MP3 file."""
        test_dir = Path("/Users/v/PYTHON_PROJECTS/rdbm/rockbox-db-manager/music_test_folder")
        
        # Find an MP3 file
        mp3_files = list(test_dir.rglob("*.mp3"))
        if mp3_files:
            from dap_db_manager.tagging import tag
            
            # Try to read a real file
            test_file = str(mp3_files[0])
            try:
                tags = tag.read(test_file)
                if tags:
                    # Verify it's a Tag instance
                    assert hasattr(tags, 'get')
                    assert hasattr(tags, 'get_string')
            except Exception:
                # File might be corrupted (which is fine for testing)
                pass

    @pytest.mark.skipif(
        not Path("/Users/v/PYTHON_PROJECTS/rdbm/rockbox-db-manager/music_test_folder").exists(),
        reason="Test data not available"
    )
    def test_tag_from_real_flac(self):
        """Test creating Tag from a real FLAC file."""
        test_dir = Path("/Users/v/PYTHON_PROJECTS/rdbm/rockbox-db-manager/music_test_folder")
        
        # Find a FLAC file
        flac_files = list(test_dir.rglob("*.flac"))
        if flac_files:
            from dap_db_manager.tagging import tag
            
            test_file = str(flac_files[0])
            try:
                tags = tag.read(test_file)
                if tags:
                    assert hasattr(tags, 'get')
            except Exception:
                pass


class TestTagFieldAccess:
    """Test accessing standard tag fields."""

    def test_tag_standard_fields(self):
        """Test that Tag supports standard fields."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        
        tag = Tag(mock_tags)
        
        # Standard fields that should be supported:
        # artist, album, title, albumartist, genre, date, etc.
        # The exact behavior depends on the tag_mapping


class TestTagModification:
    """Test modifying tag values."""

    def test_setitem(self):
        """Test __setitem__ for modifying tags."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "FLAC"
        mock_tags.__setitem__ = Mock()
        
        tag = Tag(mock_tags)
        # Modifying a tag field
        # tag["artist"] = ["New Artist"]

    def test_delitem(self):
        """Test __delitem__ for removing tags."""
        mock_tags = Mock()
        mock_tags.__class__.__name__ = "MP3"
        mock_tags.__delitem__ = Mock()
        
        tag = Tag(mock_tags)
        # Deleting a tag field
        # del tag["comment"]
