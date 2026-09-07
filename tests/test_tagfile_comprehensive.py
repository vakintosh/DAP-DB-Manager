
import pytest
import struct
import io
import os
from pathlib import Path
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from dap_db_manager.constants import MAGIC, ENCODING

class TestTagEntry:
    """Test suite for TagEntry."""

    def test_init_defaults(self):
        """Test default initialization."""
        entry = TagEntry()
        assert entry.data == "<Untagged>"
        assert entry.index == 0xFFFFFFFF
        assert entry.is_path is False
        assert entry.sort == "<Untagged>" # Defaults to data (preserved case) if sort not set

    def test_data_encoding(self):
        """Test data encoding/decoding lazy properties."""
        entry = TagEntry("Tést")
        # Check string access
        assert entry.data == "Tést"
        # Check bytes access (lazy)
        assert entry.raw_data.startswith(b"T\xc3\xa9st\x00")
        
        # Test setting bytes directly (e.g. from file)
        entry.raw_data = b"NewValue\x00Padding"
        assert entry.data == "NewValue"

    def test_sort_key(self):
        """Test sort key behavior."""
        # __init__ sets sort directly without lowercasing
        entry = TagEntry("The Band", sort="Band, The")
        assert entry.sort == "Band, The"
        
        # Property setter DOES lowercase
        entry.sort = "Band, The"
        assert entry.sort == "band, the"
        
        entry = TagEntry("Data")
        assert entry.sort == "Data" # Defaults to data (preserved case)
        
    def test_length_calculation(self):
        """Test padding and length calculation."""
        # Standard entry: padded to 8 bytes
        # "A" + null = 2 bytes -> padded to 8
        entry = TagEntry("A")
        assert entry.length == 8
        assert entry.size == 8 + 8 # length + 2 ints (4 bytes each)
        
        # "1234567" + null = 8 bytes -> padded to 8
        entry = TagEntry("1234567")
        assert entry.length == 8
        
        # "12345678" + null = 9 bytes -> padded to 16
        entry = TagEntry("12345678")
        assert entry.length == 16
        
        # Path entry: no padding
        entry = TagEntry("A", is_path=True)
        assert entry.length == 2 # "A" + null
        assert entry.size == 2 + 8

    def test_serialization(self):
        """Test to_file and from_file."""
        entry = TagEntry("Tést")
        entry.index = 10
        
        buf = io.BytesIO()
        entry.to_file(buf)
        buf.seek(0)
        
        # Read back
        restored = TagEntry.from_file(buf)
        assert restored.data == "Tést"
        assert restored.index == 10
        assert restored.offset == 0

class TestTagFile:
    """Test suite for TagFile container."""

    def test_append_and_lookup(self):
        """Test appending entries and lookups."""
        tf = TagFile()
        e1 = TagEntry("Apple", sort="apple")
        e2 = TagEntry("Banana", sort="banana")
        
        tf.append(e1)
        tf.append(e2)
        
        assert len(tf.entries) == 2
        assert "Apple" in tf
        assert tf["Apple"] == e1
        assert tf.find_by_sort("banana") == e2

    def test_sorted_insert(self):
        """Test append_sorted functionality."""
        tf = TagFile()
        e1 = TagEntry("B")
        e2 = TagEntry("A")
        e3 = TagEntry("C")
        
        tf.append_sorted(e1)
        tf.append_sorted(e2)
        tf.append_sorted(e3)
        
        assert tf.entries == [e2, e1, e3]
        assert tf._is_sorted

    def test_sorting(self):
        """Test explicitly sorting unsorted entries."""
        tf = TagFile()
        tf.append(TagEntry("B"))
        tf.append(TagEntry("A"))
        
        assert tf.entries[0].data == "B"
        tf.sort()
        assert tf.entries[0].data == "A"
        assert tf.entries[1].data == "B"

    def test_file_io(self, tmp_path):
        """Test writing and reading TagFile."""
        fpath = tmp_path / "tags.db"
        
        tf = TagFile()
        tf.append(TagEntry("Entry1"))
        e2 = TagEntry("Entry2")
        e2.index = 5
        tf.append(e2)
        
        # Write
        tf.write(fpath)
        
        # Read using class method
        loaded = TagFile.read(fpath)
        assert loaded.count == 2
        assert "Entry1" in loaded
        assert loaded["Entry2"].index == 5
        assert loaded.magic == MAGIC

    def test_invalid_file(self, tmp_path):
        """Test reading corrupted files."""
        fpath = tmp_path / "corrupt.db"
        
        # Short header
        fpath.write_bytes(b"SHORT")
        with pytest.raises((ValueError, EOFError), match="Incomplete file header"):
            TagFile.read(fpath)
            
        # Wrong magic
        fpath.write_bytes(struct.pack("III", 0xDEADBEEF, 0, 0))
        with pytest.raises(ValueError, match="Unsupported database version"):
            TagFile.read(fpath)

    def test_read_permission_error(self, tmp_path):
        """Test permission error handling."""
        fpath = tmp_path / "locked.db"
        fpath.write_bytes(b"data")
        
        # Trigger permission error by mocking open or chmod
        # chmod is easier but might not work in all envs (e.g. root)
        # We'll use mock open
        with pytest.raises(PermissionError):
             # Mock open to raise PermissionError
             from unittest.mock import patch
             with patch("builtins.open", side_effect=PermissionError("Boom")):
                 TagFile.read(fpath)

    def test_write_buffering(self, tmp_path):
        """Test write buffering options."""
        fpath = tmp_path / "buffered.db"
        tf = TagFile()
        
        # Default buffer
        tf.write(fpath)
        assert fpath.exists()
        
        # Disabled buffer
        fpath2 = tmp_path / "unbuffered.db" 
        tf.write(fpath2, buffer_size=None)
        assert fpath2.exists()

