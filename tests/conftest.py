"""Pytest configuration and fixtures."""

import sys
from pathlib import Path
import pytest

from dap_db_manager.database import Database
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="Update performance baselines instead of comparing",
    )


@pytest.fixture
def temp_music_dir(tmp_path):
    """Create a temporary directory with sample music files."""
    music_dir = tmp_path / "music"
    music_dir.mkdir()

    # Create subdirectories
    (music_dir / "Artist1" / "Album1").mkdir(parents=True)
    (music_dir / "Artist2" / "Album2").mkdir(parents=True)

    return music_dir


@pytest.fixture
def sample_tagfile():
    """Create a sample TagFile for testing."""

    tagfile = TagFile()
    tagfile.append(TagEntry("Artist 1"))
    tagfile.append(TagEntry("Artist 2"))
    tagfile.append(TagEntry("Artist 3"))

    return tagfile


@pytest.fixture
def sample_database():
    """Create a sample Database for testing."""
    return Database()
