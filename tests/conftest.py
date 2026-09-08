"""Pytest configuration and fixtures."""

import os
import sys
import tracemalloc
from pathlib import Path
import pytest

from dap_db_manager.database import Database, TagCache
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


@pytest.fixture(autouse=True)
def _no_global_state_leaks():
    """Stop any test from leaking global interpreter state into the next one.

    Two pieces of state are process-global and silently distort every later
    test if left modified:

    - **tracemalloc.** It instruments every allocation, so leaving it enabled
      roughly halves the speed of allocation-heavy code. A test that calls
      ``tracemalloc.start()`` and then exits early -- ``pytest.skip()``, a
      failed assertion, any exception -- never reaches its ``stop()``. This
      previously made two performance-regression tests report ~130% and ~120%
      slowdowns that looked machine-dependent.
    - **TagCache max memory.** A test that lowers the limit to exercise
      trimming leaves every later test thrashing a small cache.

    Individual tests should still clean up after themselves; this is a net, not
    a licence. It restores rather than asserts, so it never masks a genuine
    failure by turning it into a fixture error.
    """
    cache_limit = TagCache.get_max_cache_memory()

    yield

    if tracemalloc.is_tracing():
        tracemalloc.stop()

    if TagCache.get_max_cache_memory() != cache_limit:
        TagCache.set_max_cache_memory(cache_limit)


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


def music_test_folder() -> Path:
    """Locate the shared music fixture directory.

    The suite previously hardcoded an absolute path into a sibling checkout,
    so these tests only ran on one machine at one path and silently skipped
    everywhere else. Resolution order:

    1. ``$DDM_TEST_DATA`` -- explicit override, e.g. in CI or a container.
    2. ``<repo>/../test-fixtures/music_test_folder`` -- the default layout.

    Tests guard on ``music_test_folder().exists()`` and skip when the fixture
    data is unavailable, so a checkout without it still runs the rest.
    """
    env = os.environ.get("DDM_TEST_DATA")
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent / "test-fixtures" / "music_test_folder"
