"""Audio file tagging sub-package.

This package provides functionality for reading and manipulating audio file
metadata across various formats (MP3, FLAC, MP4, Vorbis, etc.).

Sub-packages:
    tag/: Tag reading and manipulation (refactored from tag.py)
        - core.py: Core Tag class
        - formats.py: Audio format definitions
        - utils.py: Conversion utilities
        - mappings/: Field mappings for different formats
    titleformat/: Foobar2000-style format string parsing

Main exports:
    read: Read audio file tags
    Tag: Tag manipulation class
    TagFile: Tag file structure class
    TagEntry: Tag entry class
    format: Format tags using titleformat strings
"""

__all__ = ["tag", "titleformat", "read", "format", "Tag", "TagFile", "TagEntry"]

from .tag import read, Tag, TagFile, TagEntry
from .titleformat import format
