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


class TestRockboxSlotLayout:
    """The on-disk index entry must follow Rockbox's tag_type enum.

    apps/tagcache.h: artist=0 album genre title filename composer comment
    albumartist grouping=8 year=9 discnumber=10 tracknumber=11
    virt_canonicalartist=12 bitrate=13 length playcount rating playtime
    lastplayed commitid mtime lastelapsed lastoffset=22, then index_entry.flag.
    """

    ROCKBOX_SLOTS = [
        "artist",
        "album",
        "genre",
        "title",
        "path",
        "composer",
        "comment",
        "album artist",
        "grouping",
        "date",
        "discnumber",
        "tracknumber",
        "canonicalartist",
        "bitrate",
        "length",
        "playcount",
        "rating",
        "playtime",
        "lastplayed",
        "commitid",
        "mtime",
        "lastelapsed",
        "lastoffset",
        "flag",
    ]

    def _entry(self):
        import io
        import struct
        from dap_db_manager.constants import FILE_TAGS

        entry = IndexEntry()
        offsets = {}
        for i, field in enumerate(FILE_TAGS):
            te = TagEntry(field)
            te.offset = 1000 + i
            offsets[field] = te.offset
            entry[field] = te
        entry["date"] = 2026
        entry["discnumber"] = 2
        entry["tracknumber"] = 7
        entry["bitrate"] = 320
        entry["mtime"] = 0
        buf = io.BytesIO()
        entry.to_file(buf)
        return buf.getvalue(), offsets, struct

    def test_numeric_and_canonical_slots_match_rockbox(self):
        data, offsets, struct = self._entry()
        assert len(data) == 4 * len(self.ROCKBOX_SLOTS)
        slots = struct.unpack("<24I", data)
        assert slots[9] == 2026  # tag_year
        assert slots[10] == 2  # tag_discnumber
        assert slots[11] == 7  # tag_tracknumber
        assert slots[12] == offsets["canonicalartist"]  # tag_virt_canonicalartist
        assert slots[13] == 320  # tag_bitrate

    def test_roundtrip_preserves_fields(self):
        import io

        data, offsets, _ = self._entry()

        class FakeTagFile:
            def __init__(self, field):
                te = TagEntry(field)
                te.offset = offsets[field]
                self.offsets = {te.offset: te}

        from dap_db_manager.constants import FILE_TAGS

        tagfiles = {f: FakeTagFile(f) for f in FILE_TAGS}
        back = IndexEntry.from_file(io.BytesIO(data), tagfiles)
        assert back["date"] == 2026
        assert back["discnumber"] == 2
        assert back["tracknumber"] == 7
        assert back["canonicalartist"].offset == offsets["canonicalartist"]
