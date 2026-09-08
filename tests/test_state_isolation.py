"""Regression tests for cross-test state leakage.

These guard against a test leaving global interpreter state enabled after it
finishes, which silently distorts every test that runs afterwards.
"""

import tracemalloc

import pytest

from dap_db_manager.database import TagCache


class TestTracemallocIsolation:
    """`tracemalloc` must never stay enabled past the test that started it.

    tracemalloc instruments every allocation, roughly halving the speed of
    allocation-heavy code. A test that calls tracemalloc.start() and then exits
    early -- via pytest.skip(), an assertion failure, or any exception -- before
    reaching tracemalloc.stop() leaves tracing on for the rest of the session.

    This caused two performance-regression tests to report ~130% and ~120%
    slowdowns that looked machine-dependent, but were entirely an artefact of
    tests/test_memory_efficiency.py calling start() above its skip guard: the
    leak only fired on machines missing tests/test_rename/, where the skip
    triggers.
    """

    def test_tracemalloc_not_left_tracing(self):
        """Nothing earlier in the session may leave tracing enabled."""
        assert not tracemalloc.is_tracing(), (
            "tracemalloc is still tracing -- an earlier test called "
            "tracemalloc.start() without a guaranteed stop(). This silently "
            "slows every subsequent test by roughly 2x."
        )

    def test_memory_efficiency_module_does_not_leak(self, pytestconfig):
        """Running the memory-efficiency module must not leave tracing on.

        Runs the module in a subprocess so this assertion is about that module
        specifically rather than whatever else the current session has done.
        """
        import subprocess
        import sys
        from pathlib import Path

        rootdir = Path(pytestconfig.rootdir)
        probe = (
            "import tracemalloc, pytest, sys;"
            "pytest.main(['-q', '--no-header', '-p', 'no:cacheprovider',"
            " '--no-cov', 'tests/test_memory_efficiency.py']);"
            "sys.exit(1 if tracemalloc.is_tracing() else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(rootdir),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "tests/test_memory_efficiency.py left tracemalloc tracing enabled.\n"
            f"stdout:\n{result.stdout[-2000:]}"
        )


class TestTagCacheLimitIsolation:
    """The global TagCache memory limit must be restored by whoever changes it."""

    def test_cache_limit_is_at_its_default(self):
        """A test that lowers the limit must restore it even on failure."""
        limit = TagCache.get_max_cache_memory()
        assert limit > 100, (
            f"TagCache max memory is {limit} MB -- a test lowered it and did "
            "not restore it. Subsequent tests will silently thrash the cache."
        )
