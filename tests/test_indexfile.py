"""Tests for IndexFile and IndexEntry classes."""

from dap_db_manager.indexfile import IndexFile, IndexEntry
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from dap_db_manager.constants import MAGIC


class TestIndexEntry:
    """Test IndexEntry class."""

    def test_index_entry_creation(self):
        """Test creating an IndexEntry."""
        entry = IndexEntry()

        # IndexEntry is dict-like, can set fields as dict keys
        assert hasattr(entry, "__getitem__")
        assert hasattr(entry, "__setitem__")

    def test_index_entry_set_values(self):
        """Test setting values on IndexEntry."""
        entry = IndexEntry()
        entry.artist = 100
        entry.year = 2009
        entry.length = 180000  # 3 minutes in ms

        assert entry.artist == 100
        assert entry.year == 2009
        assert entry.length == 180000

    def test_index_entry_dict_interface(self):
        """Test that IndexEntry works like a dict."""
        entry = IndexEntry()
        entry["artist"] = 50
        entry["title"] = 75

        assert entry["artist"] == 50
        assert entry["title"] == 75


class TestIndexFile:
    """Test IndexFile class."""

    def test_indexfile_creation(self):
        """Test creating an empty IndexFile."""
        indexfile = IndexFile()

        assert indexfile.magic == MAGIC
        assert indexfile.serial == 0
        assert len(indexfile.entries) == 0

    def test_add_entry(self):
        """Test adding an entry to IndexFile."""
        indexfile = IndexFile()
        entry = IndexEntry()
        entry["artist"] = 0
        entry["title"] = 1

        indexfile.append(entry)
        assert len(indexfile.entries) == 1

    def test_multiple_entries(self):
        """Test adding multiple entries."""
        indexfile = IndexFile()

        for i in range(5):
            entry = IndexEntry()
            entry["artist"] = i
            indexfile.append(entry)

        assert len(indexfile.entries) == 5

    def test_size_property(self):
        """Test IndexFile size calculation."""
        indexfile = IndexFile()
        entry = IndexEntry()
        entry["artist"] = 0
        entry["title"] = 1
        entry["year"] = 2009

        indexfile.append(entry)

        # Should have size and header_size properties
        assert hasattr(indexfile, "size")
        assert hasattr(indexfile, "header_size")
        assert indexfile.header_size == 24  # 6 * 4 bytes

    def test_tagfiles_integration(self):
        """Test IndexFile with TagFile integration."""
        # Create tag files
        artist_tagfile = TagFile()
        title_tagfile = TagFile()

        # Add some entries (use strings)
        artist_entry = TagEntry("Test Artist")
        title_entry = TagEntry("Test Song")

        artist_tagfile.append(artist_entry)
        title_tagfile.append(title_entry)

        # Create index entry
        indexfile = IndexFile()
        tagfiles = {"artist": artist_tagfile, "title": title_tagfile}
        indexfile.tagfiles = tagfiles

        entry = IndexEntry()
        entry["artist"] = 0
        entry["title"] = 0

        indexfile.append(entry)

        assert len(indexfile.entries) == 1
        assert indexfile.entries[0]["artist"] == 0
        assert indexfile.entries[0]["title"] == 0
