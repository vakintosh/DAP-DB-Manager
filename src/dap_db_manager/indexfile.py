import struct

from .utils import fat_to_mtime, mtime_to_fat
from .constants import (
    MAGIC,
    TAGS,
    FILE_TAGS,
    EMBEDDED_TAGS,
    SUPPORTED_VERSIONS,
    FLAG_DELETED,
    FLAG_DIRCACHE,
    FLAG_DIRTYNUM,
    FLAG_TRKNUMGEN,
    FLAG_RESURRECTED,
)
from .tagging.tag.tagfile import TagEntry
import logging


class IndexFile:
    def __init__(self, entries=None, tagfiles=None):
        self.magic = MAGIC
        self.serial = 0
        self.commitid = 0
        self.dirty = 0
        self.entries = entries if entries is not None else []

        # The index must have references to the tagfiles so that it can
        # calculate the size part of the header.
        self.tagfiles = tagfiles if tagfiles is not None else {}

    def __getitem__(self, key):
        return self.entries.__getitem__(key)

    def append(self, entry):
        self.entries.append(entry)

    @property
    def count(self):
        return len(self.entries)

    @property
    def size(self):
        """The size in an IndexFile represents the amount of memory that needs
        to be allocated to hold the tagcache.  It is calculated as the sum of
        the size of each TagFile (except the path TagFile), plus the size of
        the IndexFile (data size + header size).

        """
        return (
            sum(f.size for k, f in self.tagfiles.items() if k != "path")
            + self.header_size
            + self.data_size
        )

    @property
    def data_size(self):
        return IndexEntry.size * self.count

    header_size = 6 * 4

    def sort(self):
        self.entries.sort(key=lambda entry: entry.sort)

    def to_file(self, f):
        self.commitid += 1
        self.dirty = 0
        f.write(
            struct.pack(
                "IIIIII",
                self.magic,
                self.size,
                self.count,
                self.serial,
                self.commitid,
                self.dirty,
            )
        )
        for entry in self.entries:
            entry.to_file(f)

    def write(self, filename, buffer_size=None):
        """Write index file to disk with optional buffering for better I/O performance.

        Args:
            filename: Path to write the index file
            buffer_size: Optional buffer size in bytes. If None, uses system default.
                        Recommended: 262144 (256KB) for optimal performance on modern systems.
        """
        if buffer_size is not None:
            with open(filename, "wb", buffering=buffer_size) as f:
                self.to_file(f)
        else:
            with open(filename, "wb") as f:
                self.to_file(f)

    @staticmethod
    def from_file(f, tagfiles):
        index = IndexFile(tagfiles=tagfiles)
        index.magic, size, count, index.serial, index.commitid, index.dirty = (
            struct.unpack("IIIIII", f.read(4 * 6))
        )

        # Validate database version
        if index.magic not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported database version: got {index.magic} (0x{index.magic:08x}). "
                f"Supported versions: {[f'{v} (0x{v:08x})' for v in SUPPORTED_VERSIONS]}. "
                f"File may be corrupted or from a newer Rockbox version."
            )

        for i in range(count):
            index.append(IndexEntry.from_file(f, tagfiles))

        # Validate size but don't fail - database versions may calculate differently
        if size != index.size:
            logging.warning(
                f"Database size mismatch: header says {size} bytes, calculated {index.size} bytes. "
                f"This may indicate a version difference or corrupted database, but continuing anyway."
            )

        return index

    @staticmethod
    def read(filename, tagfiles):
        with open(filename, "rb") as f:
            return IndexFile.from_file(f, tagfiles)


class IndexEntry(dict):
    def __init__(self):
        for field in FILE_TAGS:
            self[field] = None
        for field in EMBEDDED_TAGS:
            self[field] = 0

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value

    size = 4 * len(TAGS)

    def copy(self):
        other = IndexEntry()
        other.update(self)
        return other

    # Flag helper methods to match Rockbox behavior
    def set_flag(self, flag_bit):
        """Set a flag bit (OR operation)."""
        self["flag"] |= flag_bit

    def clear_flag(self, flag_bit):
        """Clear a flag bit (AND NOT operation)."""
        self["flag"] &= ~flag_bit

    def has_flag(self, flag_bit):
        """Check if a flag bit is set."""
        return bool(self["flag"] & flag_bit)

    def is_deleted(self):
        """Check if entry is marked as deleted."""
        return self.has_flag(FLAG_DELETED)

    def is_dircache(self):
        """Check if filename is a dircache pointer (memory only)."""
        return self.has_flag(FLAG_DIRCACHE)

    def is_dirty_numeric(self):
        """Check if numeric data has been modified."""
        return self.has_flag(FLAG_DIRTYNUM)

    def is_track_num_generated(self):
        """Check if track number was auto-generated."""
        return self.has_flag(FLAG_TRKNUMGEN)

    def is_resurrected(self):
        """Check if statistics were resurrected from old DB."""
        return self.has_flag(FLAG_RESURRECTED)

    def to_file(self, f):
        for field in FILE_TAGS:
            tagentry = self[field]
            assert isinstance(tagentry, TagEntry) and tagentry.offset is not None
            f.write(struct.pack("I", tagentry.offset))

        for field in EMBEDDED_TAGS:
            value = self[field]
            # mtime needs to be converted from float back to FAT format integer
            if field == "mtime":
                value = mtime_to_fat(value)
            f.write(struct.pack("I", value))

    @staticmethod
    def from_file(f, tagfiles):
        """Read the index entry from a file.

        If tagfiles is a dictionary of { field: TagFile } pairs, which will be
        used to extract the actual TagEntry for each offset in the file.

        """

        index_entry = IndexEntry()
        for field in FILE_TAGS:
            offset = struct.unpack("I", f.read(4))[0]

            # Handle invalid or missing offsets gracefully
            if offset == 0 or offset not in tagfiles[field].offsets:
                # Create a placeholder entry for invalid/missing references
                index_entry[field] = TagEntry("<Invalid Reference>")
            else:
                index_entry[field] = tagfiles[field].offsets[offset]

        for field in EMBEDDED_TAGS:
            index_entry[field] = struct.unpack("I", f.read(4))[0]
        index_entry.mtime = fat_to_mtime(index_entry.mtime)

        return index_entry
