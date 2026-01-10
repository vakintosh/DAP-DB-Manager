from pathlib import Path
import struct
from operator import attrgetter

from ...constants import MAGIC, ENCODING, SUPPORTED_VERSIONS


class TagFile:
    def __init__(self, entries=None):
        self.magic = MAGIC
        self.entrydict = {}
        self.entries = []
        self.offsets = {}
        if entries is not None:
            for entry in entries:
                self.append(entry)

    def __contains__(self, key):
        return key in self.entrydict

    def __getitem__(self, key):
        return self.entrydict[key]

    def __iter__(self):
        return iter(self.entries)

    @property
    def count(self):
        return len(self.entries)

    @property
    def size(self):
        return sum(entry.size for entry in self.entries)

    def append(self, entry):
        self.entrydict[entry.key] = entry
        self.entries.append(entry)

    def sort(self):
        self.entries.sort(key=attrgetter("sort"))

    def to_file(self, f):
        self.offsets.clear()
        f.write(struct.pack("III", self.magic, self.size, self.count))
        for entry in self.entries:
            self.offsets[f.tell()] = entry
            entry.to_file(f)

    def write(self, filename, buffer_size=1048576):
        """Write tag file to disk with optimized buffering for better I/O performance.

        Args:
            filename: Path to write the tag file
            buffer_size: Buffer size in bytes. Default: 1MB (1048576) for optimal performance.
                        Set to None to use system default (~8KB).
        """
        if buffer_size is not None:
            with open(filename, "wb", buffering=buffer_size) as f:
                self.to_file(f)
        else:
            with open(filename, "wb") as f:
                self.to_file(f)

    @staticmethod
    def from_file(f, is_path=False):
        """Return a TagFile given a file object.

        Raises:
            struct.error: If file format is invalid
            ValueError: If file is corrupted or incomplete
            EOFError: If file ends unexpectedly
        """
        tf = TagFile()
        try:
            header = f.read(4 * 3)
            if len(header) < 12:
                raise EOFError(
                    f"Incomplete file header: expected 12 bytes, got {len(header)}"
                )

            magic, size, entry_count = struct.unpack("III", header)

            if magic not in SUPPORTED_VERSIONS:
                raise ValueError(
                    f"Unsupported database version: got {magic} (0x{magic:08x}). "
                    f"Supported versions: {[f'{v} (0x{v:08x})' for v in SUPPORTED_VERSIONS]}. "
                    f"File may be corrupted or from a newer Rockbox version."
                )

            # Store the actual magic from file for proper round-trip
            tf.magic = magic

            if entry_count < 0 or entry_count > 1000000:  # Sanity check
                raise ValueError(
                    f"Invalid entry count: {entry_count}. File may be corrupted."
                )

            for i in range(entry_count):
                offset = f.tell()
                try:
                    entry = TagEntry.from_file(f, is_path)
                    tf.offsets[offset] = entry
                    tf.append(entry)
                except (struct.error, ValueError) as e:
                    raise ValueError(
                        f"Failed to read entry {i + 1}/{entry_count} at offset {offset}: {e}"
                    )

            if tf.size != size:
                raise ValueError(
                    f"Size mismatch: header says {size} bytes, but got {tf.size} bytes. File may be corrupted."
                )

            return tf
        except struct.error as e:
            raise ValueError(f"Invalid file format: {e}")
        except Exception as e:
            if isinstance(e, (ValueError, EOFError)):
                raise
            raise ValueError(f"Unexpected error reading file: {e}")

    @staticmethod
    def read(filename, is_path=None):
        """Return a TagFile given a file name.

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is corrupted or has invalid format
            EOFError: If file ends unexpectedly
            PermissionError: If file cannot be read
        """
        if is_path is None:
            base = Path(filename).name
            if base.startswith("database_"):
                is_path = base[9:] == "4.tcd"
            else:
                is_path = False

        try:
            with open(filename, "rb") as f:
                return TagFile.from_file(f, is_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Tag file not found: {filename}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading tag file: {filename}")
        except (ValueError, EOFError) as e:
            # Re-raise with filename context
            raise type(e)(f"Error reading {filename}: {e}")
        except Exception as e:
            raise ValueError(f"Unexpected error reading {filename}: {e}")


class TagEntry:
    __slots__ = (
        "_TagEntry__data_str",
        "_TagEntry__data_bytes",
        "_TagEntry__sort",
        "is_path",
        "index_entries",
        "_TagEntry__index",
        "offset",
    )

    def __init__(self, data="<Untagged>", sort=None, is_path=False):
        # Store string data directly for performance (lazy encoding)
        self.__data_str = data  # type: ignore[misc]
        self.__data_bytes = None  # type: ignore[misc]  # Encoded lazily when needed
        self.__sort = sort  # type: ignore[misc]
        self.is_path = is_path
        self.index_entries = []
        self.__index = None  # type: ignore[misc]
        self.offset = None

    def add_index_entry(self, entry):
        self.index_entries.append(entry)

    def __get_data(self):
        """Get tag data as string.

        Returns the cached string value if available, otherwise decodes
        from bytes with fallback encoding support.
        """
        if self.__data_str is not None:
            return self.__data_str

        # Decode from bytes (for entries loaded from file)
        assert self.__data_bytes is not None
        try:
            return str(self.__data_bytes, ENCODING)
        except UnicodeDecodeError:
            # Try Latin-1 as fallback - it can decode any byte sequence
            try:
                return str(self.__data_bytes, "latin-1")
            except UnicodeDecodeError:
                # Last resort: replace invalid characters
                return str(self.__data_bytes, ENCODING, errors="replace")

    def __set_data(self, data):
        """Set tag data from string."""
        self.__data_str = data
        self.__data_bytes = None  # type: ignore[misc]  # Clear cached bytes

    data = property(__get_data, __set_data)

    @property
    def __data(self):
        """Get encoded data bytes (lazy encoding)."""
        if self.__data_bytes is None:
            if self.__data_str is not None:
                self.__data_bytes = self.__data_str.encode(ENCODING)  # type: ignore[misc]
            else:
                self.__data_bytes = b""  # type: ignore[misc]
        return self.__data_bytes

    @property
    def key(self):
        # Optimize: return cached string directly to avoid property overhead
        return self.__data_str if self.__data_str is not None else self.data

    def __get_raw_data(self):
        return (self.__data + b"\x00").ljust(self.length, b"X")

    def __set_raw_data(self, raw_data):
        """Set raw data from bytes (when reading from file)."""
        self.__data_bytes = raw_data.partition(b"\x00")[0]  # type: ignore[misc]
        self.__data_str = None  # Clear cached string

    raw_data = property(__get_raw_data, __set_raw_data)

    def __get_index(self):
        return self.__index if self.__index is not None else 0xFFFFFFFF

    def __set_index(self, index):
        self.__index = index  # type: ignore[misc]

    index = property(__get_index, __set_index)

    def __get_sort(self):
        # Optimize: use cached string directly if available
        if self.__sort is not None:
            return self.__sort
        # Use __data_str directly to avoid property overhead
        return self.__data_str if self.__data_str is not None else self.data

    def __set_sort(self, sort):
        if sort is not None:
            sort = sort.lower()
        self.__sort = sort

    sort = property(__get_sort, __set_sort)

    def sort_value(self):
        return self.offset if self.offset is not None else self.sort

    def matches(self, str):
        return self.data == str

    @property
    def length(self):
        """
        Length must be a multiple of 8 (including the nul-terminator), UNLESS
        this is part of the 'path' database file, in which case Length is simply
        the length of the data plus a nul-terminator
        """
        if self.is_path:
            return len(self.__data) + 1
        else:
            data_len = len(self.__data) + 1
            return ((data_len + 7) // 8) * 8

    @property
    def size(self):
        return self.length + 4 * 2

    def __str__(self):
        return self.data

    def __repr__(self):
        return f"TagEntry({self.data!r})"

    def to_file(self, f):
        self.offset = f.tell()
        f.write(struct.pack("II", self.length, self.index))
        f.write(self.raw_data)

    @staticmethod
    def from_file(f, is_path=False):
        """Return a TagFile given a file object."""
        # Store offset BEFORE reading header to match how it's written in to_file()
        offset_before = f.tell()
        length, index = struct.unpack("II", f.read(4 * 2))
        entry = TagEntry()
        entry.offset = offset_before
        entry.raw_data = f.read(length)
        entry.index = index
        entry.is_path = is_path
        return entry
