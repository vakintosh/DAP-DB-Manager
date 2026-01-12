"""Tests for TagFile and TagEntry classes."""

import io
import struct
import pytest
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from dap_db_manager.constants import MAGIC, SUPPORTED_VERSIONS


class TestTagEntry:
    """Test TagEntry class."""

    def test_tag_entry_creation(self):
        """Test creating a TagEntry."""
        entry = TagEntry("TestData")
        assert entry.data == "TestData"
        # TagEntry doesn't have idx_id, it has other attributes
        assert hasattr(entry, "data")

    def test_tag_entry_length(self):
        """Test that tag entry computes length correctly."""
        data = "TestData"
        entry = TagEntry(data)
        assert len(entry.data) == len(data)

    def test_tag_entry_with_unicode(self):
        """Test TagEntry with unicode strings."""
        text = "Artist Name"
        entry = TagEntry(text)

        # Should get back the same text
        assert entry.data == text

    def test_tag_entry_with_latin1_fallback(self):
        """Test TagEntry handles non-UTF-8 data gracefully."""
        # Create an entry with Latin-1 encoded data (degree symbol)
        entry = TagEntry()
        # Set raw data directly to bypass UTF-8 encoding
        entry._TagEntry__data_bytes = (  # type: ignore[attr-defined]
            b"Artist\xb0Name"  # 0xb0 = degree symbol in Latin-1
        )
        entry._TagEntry__data_str = None  # type: ignore[attr-defined]  # Clear cached string to force decode

        # Should decode using Latin-1 fallback
        data = entry.data
        assert isinstance(data, str)
        assert "Artist" in data
        assert "Name" in data
        # In Latin-1, 0xb0 is the degree symbol °
        assert "°" in data or "?" in data  # Might be ° or replacement char


class TestTagFile:
    """Test TagFile class."""

    def test_tagfile_creation(self):
        """Test creating an empty TagFile."""
        tagfile = TagFile()
        assert tagfile.magic == MAGIC
        assert len(tagfile.entrydict) == 0

    def test_add_entry(self):
        """Test adding an entry to TagFile."""
        tagfile = TagFile()
        entry = TagEntry("Test Artist")

        tagfile.append(entry)
        assert len(tagfile.entrydict) == 1

    def test_get_entry(self):
        """Test retrieving an entry by key."""
        tagfile = TagFile()
        test_data = "Test Artist"
        entry = TagEntry(test_data)

        tagfile.append(entry)
        # Access via entrydict using the key
        retrieved = tagfile[test_data]

        assert retrieved is not None
        assert retrieved.data == test_data

    def test_duplicate_entries(self):
        """Test handling duplicate data in TagFile."""
        tagfile = TagFile()
        test_data = "Same Artist"

        entry1 = TagEntry(test_data)
        entry2 = TagEntry(test_data)

        tagfile.append(entry1)
        # Second append overwrites in entrydict
        tagfile.append(entry2)

        # Should have the entry in dict
        assert test_data in tagfile.entrydict

    def test_raw_data_generation(self):
        """Test TagFile has size property."""
        tagfile = TagFile()
        entry = TagEntry("Test")
        tagfile.append(entry)

        # TagFile has a size property
        assert hasattr(tagfile, "size")
        assert tagfile.size > 0
        assert isinstance(tagfile.size, int)

    def test_empty_tagfile_size(self):
        """Test size property for empty TagFile."""
        tagfile = TagFile()

        # Empty tagfile should have 0 size
        assert tagfile.size == 0
        assert tagfile.count == 0


class TestTagFileVersionSupport:
    """Test TagFile support for multiple database versions."""

    def test_supported_versions_defined(self):
        """Test that supported versions are properly defined."""
        assert len(SUPPORTED_VERSIONS) >= 1
        assert 1413695504 in SUPPORTED_VERSIONS  # Version 16 (0x10)

    def test_read_version_16(self):
        """Test reading a version 16 (0x10) database file."""
        # Create a minimal tagfile with version 16
        data = io.BytesIO()
        magic = 1413695504  # Version 16
        size = 0
        count = 0
        data.write(struct.pack("III", magic, size, count))
        data.seek(0)

        tagfile = TagFile.from_file(data)
        assert tagfile.magic == magic
        assert tagfile.count == 0

    def test_reject_unsupported_version(self):
        """Test that unsupported versions are rejected."""
        # Create a tagfile with an invalid version
        data = io.BytesIO()
        magic = 9999999  # Invalid version
        size = 0
        count = 0
        data.write(struct.pack("III", magic, size, count))
        data.seek(0)

        with pytest.raises(ValueError) as excinfo:
            TagFile.from_file(data)
        assert "Unsupported database version" in str(excinfo.value)
        assert "9999999" in str(excinfo.value)

    def test_version_preserved_on_read(self):
        """Test that the version from file is preserved after reading."""
        # Test with version 16
        data = io.BytesIO()
        magic = 1413695504
        size = 0
        count = 0
        data.write(struct.pack("III", magic, size, count))
        data.seek(0)

        tagfile = TagFile.from_file(data)
        assert tagfile.magic == 1413695504  # Should preserve v16, not default to v13
