"""
Tag subpackage - Audio file tag reading and manipulation.

This package provides a unified interface for reading and manipulating
audio file metadata across various formats (MP3, FLAC, MP4, etc.).
"""

from .core import Tag
from .formats import read, SUPPORTED_EXTENSIONS, FORMAT_MAPPING
from .mappings import setup_all_mappings
from .tagfile import TagFile, TagEntry

# Initialize all tag field mappings
setup_all_mappings()

__all__ = [
    "Tag",
    "read",
    "SUPPORTED_EXTENSIONS",
    "FORMAT_MAPPING",
    "TagFile",
    "TagEntry",
]
