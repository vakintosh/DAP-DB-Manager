"""I/O operations for Rockbox database files.

This module handles reading and writing Rockbox database files in the
TagCache Database (.tcd) format.
"""

from pathlib import Path
from typing import Callable

from ..constants import FILE_TAGS, FILE_TAG_INDICES
from ..tagging.tag.tagfile import TagFile
from ..indexfile import IndexFile
import sys


def myprint(*args, **kwargs):
    """Simple print wrapper for I/O callback functions."""
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")

    sys.stdout.write(sep.join(str(a) for a in args) + end)


class DatabaseIO:
    """Handles reading and writing Rockbox database files."""

    # Buffer size for efficient I/O operations
    # Modern systems benefit from larger buffers (256KB provides significant speedup)
    BUFFER_SIZE = 262144  # 256KB buffer

    @classmethod
    def write(
        cls, tagfiles: dict, index, out_dir: str = "", callback: Callable = myprint
    ) -> None:
        """Write the database to a directory.

        Files that will be written:
            database_0.tcd  (artist)
            database_1.tcd  (album)
            database_2.tcd  (genre)
            database_3.tcd  (title)
            database_4.tcd  (filename/path)
            database_5.tcd  (composer)
            database_6.tcd  (comment)
            database_7.tcd  (album artist)
            database_8.tcd  (grouping)
            database_12.tcd (canonicalartist)
            database_idx.tcd (index)

        Args:
            tagfiles: Dictionary of TagFile objects
            index: IndexFile object
            out_dir: Output directory path
            callback: Progress callback function
        """
        # Write the tag files with optimized buffering
        # Note: Use FILE_TAG_INDICES to get correct file numbers (0-8, then 12)
        out_path = Path(out_dir) if out_dir else Path.cwd()
        for i, field in enumerate(FILE_TAGS):
            file_num = FILE_TAG_INDICES[i]
            filename = out_path / f"database_{file_num}.tcd"
            callback(f"Writing {filename} . . .", end="")
            tagfiles[field].write(str(filename), buffer_size=cls.BUFFER_SIZE)
            callback("done")

        # Write the index file with optimized buffering
        filename = out_path / "database_idx.tcd"
        callback(f"Writing {filename} . . .", end="")
        index.write(str(filename), buffer_size=cls.BUFFER_SIZE)
        callback("done")

    @classmethod
    def read(cls, in_dir: str = "", callback: Callable = myprint) -> tuple:
        """Read the database from a directory.

        Files that will be read:
            database_0.tcd  (artist)
            database_1.tcd  (album)
            database_2.tcd  (genre)
            database_3.tcd  (title)
            database_4.tcd  (filename/path)
            database_5.tcd  (composer)
            database_6.tcd  (comment)
            database_7.tcd  (album artist)
            database_8.tcd  (grouping)
            database_12.tcd (canonicalartist)
            database_idx.tcd (index)

        Args:
            in_dir: Input directory path
            callback: Progress callback function

        Returns:
            Tuple of (tagfiles_dict, index_object)
        """
        tagfiles = {}
        in_path = Path(in_dir) if in_dir else Path.cwd()

        # Read the tag files using FILE_TAG_INDICES for correct file numbers
        for i, field in enumerate(FILE_TAGS):
            file_num = FILE_TAG_INDICES[i]
            filename = in_path / f"database_{file_num}.tcd"
            callback(f"Reading {filename} . . .", end="")
            tagfiles[field] = TagFile.read(str(filename))
            callback("done")

        # Read the index file
        filename = in_path / "database_idx.tcd"
        callback(f"Reading {filename} . . .", end="")
        index = IndexFile.read(str(filename), tagfiles)
        callback("done")

        return tagfiles, index
