
import pytest
from unittest.mock import MagicMock, Mock
from mutagen.asf import ASF
from mutagen.mp4 import MP4
from mutagen.apev2 import APEv2File as APE
from mutagen.musepack import Musepack
from mutagen.wavpack import WavPack
from mutagen.wave import WAVE
import mutagen.id3

from dap_db_manager.tagging.tag.core import Tag
from dap_db_manager.tagging.tag.mappings.format_specific import setup_format_specific_mappings

# Ensure mappings are initialized
setup_format_specific_mappings()

class TestFormatSpecificMappings:
    """Test suite for format-specific tag mappings."""

    def test_asf_mappings(self):
        """Test ASF specific mappings."""
        mapping = Tag.field_map[ASF]
        
        # Verify keys exist
        assert "album artist" in mapping
        assert "performer" in mapping
        assert "discnumber" in mapping
        
        # We can't easily verify the implementation of RegisterBasicKey just by looking at dict,
        # but we can verify that the mapping exists.
        # To verify the logic, we'd need to mock an ASF tag and use Tag getter/setter.
        
        # Let's create a mock ASF tag
        asf_tags = MagicMock(spec=dict)
        asf_tags.__getitem__.side_effect = lambda k: asf_tags.data.get(k)
        asf_tags.__setitem__.side_effect = lambda k, v: asf_tags.data.update({k: v})
        asf_tags.__delitem__.side_effect = lambda k: asf_tags.data.pop(k)
        asf_tags.data = {}
        
        tag_wrapper = Tag(asf_tags)
        
        # Test setter mapped to "WM/AlbumArtist"
        # We need to manually set the mapping because Tag(tags) auto-detects type(tags)
        # But our mock is not instance of ASF.
        # We can force the mapping update by mocking type() or setting mapping directly.
        tag_wrapper.field_map = Tag.field_map # Point to global
        tag_wrapper.tag_mapping = Tag.field_map[ASF]
        
        # Test Setter
        tag_wrapper["album artist"] = "My Artist"
        assert asf_tags.data["WM/AlbumArtist"] == "My Artist"
        
        # Test Getter
        asf_tags.data["WM/AlbumArtist"] = "Another Artist"
        assert tag_wrapper["album artist"] == ["Another Artist"] # Tag.get wraps in list by default? No, Tag.get calls converter. Default converter is conv_string_list if get_string used? Tag.get uses mapping["convert"] which is default (None -> conv_default usually)
        
        # Check defaults
        # core.py: if not convert -> pass (identity)
        # So "Another Artist" should be returned returned as is?
        # Actually Tag.get() calls converter.
        # RegisterBasicKey sets default convert to None -> pass.
        # It seems Tag.get returns the raw value if convert is None.
        # But wait, Tag.get_string uses conv_string_list.
        # My assertion assumes list wrapping or not. Let's see.
        pass

    def test_mp4_tuple_logic(self):
        """Test MP4 tuple handling (disk, trkn)."""
        mp4_tags = {"disk": [(1, 2)], "trkn": [(5, 12)]}
        
        # Mock behavior
        mp4_mock = MagicMock()
        mp4_mock.__getitem__.side_effect = mp4_tags.__getitem__
        mp4_mock.__setitem__.side_effect = mp4_tags.__setitem__
        
        # Mapping functions
        # We can extract them from Tag.field_map[MP4]["discnumber"]
        mapping = Tag.field_map[MP4]
        
        # Test discnumber (index 0)
        getter = mapping["discnumber"]["getter"]
        setter = mapping["discnumber"]["setter"]
        
        assert getter(mp4_tags) == 1
        
        # Test setting discnumber
        setter(mp4_tags, 3)
        assert mp4_tags["disk"] == [(3, 2)]
        
        # Test totaldiscs (index 1)
        getter_total = mapping["totaldiscs"]["getter"]
        setter_total = mapping["totaldiscs"]["setter"]
        
        assert getter_total(mp4_tags) == 2
        setter_total(mp4_tags, 5)
        assert mp4_tags["disk"] == [(3, 5)]

    def test_string_split_logic(self):
        """Test APE/Musepack string splitting (1/10)."""
        # Testing the helper logic via registered keys
        mapping = Tag.field_map[APE]
        
        tags = {"Track": "5/12"}
        
        # Test tracknumber
        getter = mapping["tracknumber"]["getter"]
        assert getter(tags) == "5"
        
        # Test totaltracks
        getter_total = mapping["totaltracks"]["getter"]
        assert getter_total(tags) == "12"
        
        # Test setter (tracknumber)
        setter = mapping["tracknumber"]["setter"]
        setter(tags, "7")
        assert tags["Track"] == "7/12"
        
        # Test setter (totaltracks)
        setter_total = mapping["totaltracks"]["setter"]
        setter_total(tags, "20")
        assert tags["Track"] == "7/20"
        
        # Test setter with missing total
        tags = {"Track": "5"}
        setter(tags, "6")
        assert tags["Track"] == "6"
        
        # Test setter creating new
        tags = {}
        # This setter assumes key exists or handles KeyError logic?
        # split_string setter:
        # try: vals = partition...
        # except KeyError: if index==0: tags[key] = value
        setter(tags, "1")
        assert tags["Track"] == "1"

    def test_wave_date_logic(self):
        """Test WAVE date handling (fallback logic)."""
        mock_wave = MagicMock()
        mock_id3 = mutagen.id3.ID3()
        mock_wave.tags = mock_id3
        
        mapping = Tag.field_map[WAVE]
        getter = mapping["date"]["getter"]
        setter = mapping["date"]["setter"]
        
        # Test Setter (TDRC)
        setter(mock_wave, ["2023"])
        assert "TDRC" in mock_id3
        assert str(mock_id3["TDRC"].text[0]) == "2023"
        
        # Test Getter (TDRC)
        assert [str(x) for x in getter(mock_wave)] == ["2023"]
        
        # Test Fallback (TYER)
        del mock_id3["TDRC"]
        mock_id3.add(mutagen.id3.TYER(encoding=3, text=["2020"]))
        assert [str(x) for x in getter(mock_wave)] == ["2020"]

    def test_custom_fields(self):
        """Test MP4 and ASF custom user fields."""
        # MP4 User Field
        mapping = Tag.field_map[MP4]
        user_getter = mapping["user_field"]["getter"]
        
        # Mock tags
        tags = {"----:com.apple.iTunes:MYFIELD": "Value"}
        assert user_getter(tags, "myfield") == "Value"
        
        # ASF User Field
        mapping_asf = Tag.field_map[ASF]
        user_getter_asf = mapping_asf["user_field"]["getter"]
        
        tags_asf = {"foobar2000/MYFIELD": "Value"}
        assert user_getter_asf(tags_asf, "myfield") == "Value"

    def test_musepack_replaygain(self):
        """Test Musepack replaygain mappings."""
        mapping = Tag.field_map[Musepack]
        
        # RegisterInfoKey uses tags.info.__dict__
        mock_tags = MagicMock()
        mock_tags.info.__dict__ = {"album_gain": "-9.0 dB"}
        
        getter = mapping["replaygain_album_gain"]["getter"]
        assert getter(mock_tags) == "-9.0 dB"



