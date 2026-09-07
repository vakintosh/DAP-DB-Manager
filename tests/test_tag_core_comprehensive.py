
import pytest
from unittest.mock import MagicMock, Mock, patch
from mutagen.mp3 import EasyMP3 as MP3
from mutagen.apev2 import APEv2File as APE
from mutagen.flac import FLAC, SeekPoint
from mutagen.id3 import ID3
from dap_db_manager.tagging.tag.core import Tag
import copy
import pickle

class TestTagCore:
    """Test suite for the core Tag class."""

    @pytest.fixture
    def mock_tags(self):
        """Create a basic mock tags object."""
        tags = MagicMock(spec=dict)
        tags.__getitem__.side_effect = lambda k: tags.data.get(k)
        tags.__setitem__.side_effect = lambda k, v: tags.data.update({k: v})
        tags.__delitem__.side_effect = lambda k: tags.data.pop(k)
        tags.data = {}
        return tags

    def test_init_and_properties3(self, mock_tags):
        """Test initialization and property access."""
        tag = Tag(mock_tags)
        assert tag.tags == mock_tags
        assert tag.force_string is False
        
        # Test force_string setter
        tag.force_string = True
        assert tag.force_string is True

    def test_register_key(self):
        """Test registering keys."""
        # Use a dummy type for registration to avoid polluting globals
        class DummyType: pass
        
        getter = Mock(return_value="val")
        setter = Mock()
        deleter = Mock()
        
        Tag.RegisterKey("mykey", DummyType, getter, setter, deleter)
        
        assert "mykey" in Tag.field_map[DummyType]
        assert Tag.field_map[DummyType]["mykey"]["getter"] == getter

    def test_get_item(self, mock_tags):
        """Test __getitem__ and get/get_string behavior."""
        tag = Tag(mock_tags)
        
        # Setup a mapping for mock_tags type
        # We need to manually inject mapping because mock_tags is MagicMock
        # but Tag.update_mapping uses type(self.tags).
        # We can patch Tag.field_map's 'default' for this test
        
        getter = Mock(return_value="Value")
        convert = Mock(return_value="ConvertedValue")
        
        # Patch the DEFAULT mapping for "testkey"
        # We need to preserve original field_map to not break other tests
        original_map = copy.deepcopy(Tag.field_map)
        try:
            Tag.RegisterKey("testkey", "default", getter=getter, convert=convert)
            
            # Force update mapping
            tag.update_mapping()
            
            # Test get()
            assert tag.get("testkey") == "ConvertedValue"
            
            # Test __getitem__ (defaults to get)
            assert tag["testkey"] == "ConvertedValue"
            
            # Test get_string() (forces string list conversion)
            # Default conv_string_list wraps single items in list
            assert tag.get_string("testkey") == ["ConvertedValue"]
            
            # Test force_string property
            tag.force_string = True
            assert tag["testkey"] == ["ConvertedValue"]
            
        finally:
            Tag.field_map = original_map

    def test_set_del_item(self, mock_tags):
        """Test __setitem__ and __delitem__."""
        tag = Tag(mock_tags)
        
        setter = Mock()
        deleter = Mock()
        
        original_map = copy.deepcopy(Tag.field_map)
        try:
            Tag.RegisterKey("testkey", "default", setter=setter, deleter=deleter)
            tag.update_mapping()
            
            tag["testkey"] = "NewValue"
            setter.assert_called_with(mock_tags, "NewValue")
            
            del tag["testkey"]
            deleter.assert_called_with(mock_tags)
            
        finally:
            Tag.field_map = original_map

    def test_user_field_fallback(self, mock_tags):
        """Test fallback to user fields for unknown keys."""
        tag = Tag(mock_tags)
        
        # Register user key handler
        user_setter = Mock()
        original_map = copy.deepcopy(Tag.field_map)
        try:
            # We can't easily register a user key on 'default' effectively without modifying RegisterUserKey implementation?
            # RegisterUserKey registers 'user_field'.
            
            # Manually inject user_field into mapping
            # Actually RegisterUserKey does exactly that
            def name_func(n): return f"User_{n}"
            Tag.RegisterUserKey(name_func, "default")
            tag.update_mapping()
                     
            # Set unknown key
            tag["unknown"] = "UserValue"
            # It should call the user_setter (which uses setitem on tags with transformed name)
            assert mock_tags.data.get("User_unknown") == "UserValue"
            
            # Get unknown key
            assert tag["unknown"] == ["UserValue"] # Default convert for user key is conv_string_list
            
            # Del unknown key
            del tag["unknown"]
            assert "User_unknown" not in mock_tags.data
            
        finally:
            Tag.field_map = original_map

    def test_pickling_mp3(self):
        """Test custom pickling logic for MP3 (EasyMP3)."""
        # MP3 objects have methods like load/save that can't be pickled.
        # Tag.__getstate__ handles this.
        
        mock_mp3 = MagicMock(spec=MP3)
        # Mock specific MP3 structure
        mock_mp3.tags = MagicMock()
        mock_mp3.tags.load = Mock()
        mock_mp3.tags.save = Mock()
        mock_mp3.tags.delete = Mock()
        # Need _EasyID3__id3 for restoration logic
        mock_mp3.tags._EasyID3__id3 = MagicMock()
        setattr(mock_mp3.tags._EasyID3__id3, "load", "RestoredLoad")
        setattr(mock_mp3.tags._EasyID3__id3, "save", "RestoredSave")
        setattr(mock_mp3.tags._EasyID3__id3, "delete", "RestoredDelete")
        
        tag = Tag(mock_mp3)
        
        # Pickle
        state = tag.__getstate__()
        restored_mp3, force_string = state
        
        # Verify methods removed in pickled state
        assert not hasattr(restored_mp3.tags, "load") or restored_mp3.tags.load is None
        
        # Unpickle (simulate __setstate__)
        new_tag = Tag(None)
        new_tag.__setstate__(state)
        
        # Verify restoration logic
        assert new_tag.tags.tags.load == "RestoredLoad"
        assert new_tag.tags.tags.save == "RestoredSave"

    def test_pickling_ape(self):
        """Test APE pickling workaround."""
        mock_ape = MagicMock(spec=APE)
        # Mocking info attribute and its __dict__
        mock_ape.info = MagicMock()
        mock_ape.info.__dict__ = {"foo": "bar"}
        
        tag = Tag(mock_ape)
        state = tag.__getstate__()
        
        # Unpickle
        new_tag = Tag(None)
        
        # Create a dummy class to act as APEv2File._Info
        class MockInfoClass:
            pass
            
        with patch("mutagen.apev2.APEv2File._Info", new=MockInfoClass):
             new_tag.__setstate__(state)
        
        # Check if info dict was restored
        assert new_tag.tags.info.__dict__["foo"] == "bar"

    def test_pickling_flac(self):
        """Test FLAC seektable pickling."""
        mock_flac = MagicMock(spec=FLAC)
        mock_flac.seektable = MagicMock()
        # SeekPoints behave liek tuples
        mock_flac.seektable.seekpoints = [SeekPoint(1, 2, 3)]
        
        tag = Tag(mock_flac)
        state = tag.__getstate__()
        
        # Pickled state should have converted seekpoints to tuples
        pickled_flac = state[0]
        assert isinstance(pickled_flac.seektable.seekpoints[0], tuple)
        
        # Unpickle
        new_tag = Tag(None)
        new_tag.__setstate__(state)
        
        # Should be restored to SeekPoint objects
        assert isinstance(new_tag.tags.seektable.seekpoints[0], SeekPoint)

    def test_update_mapping_unknown_type(self):
        """Test update_mapping handles unknown types explicitly."""
        class UnknownType: pass
        mock_tags = MagicMock(spec=UnknownType)
        tag = Tag(mock_tags)
        tag.update_mapping()
        # Should just contain default mappings
        assert "user_field" in tag.tag_mapping

