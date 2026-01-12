"""Tag field mappings for various audio formats."""

from .default import setup_default_mappings
from .format_specific import setup_format_specific_mappings
from .id3 import setup_id3_mappings


def setup_all_mappings():
    """Initialize all tag field mappings."""
    setup_default_mappings()
    setup_format_specific_mappings()
    setup_id3_mappings()


__all__ = [
    "setup_default_mappings",
    "setup_format_specific_mappings",
    "setup_id3_mappings",
    "setup_all_mappings",
]
