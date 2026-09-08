"""Test memory efficiency and check for memory leaks with test_rename data.

This module tests:
1. Database loading and operations with test_rename files
2. Memory usage tracking throughout operations
3. Resource cleanup verification
4. Thread pool shutdown
5. Cache management efficiency
"""

import gc
import threading
import time
import tracemalloc
from pathlib import Path

import pytest

from dap_db_manager.database import Database, TagCache


def format_size(bytes_size):
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def get_memory_usage():
    """Get current memory usage."""
    current, peak = tracemalloc.get_traced_memory()
    return current, peak


def print_memory_stats(label):
    """Print memory statistics with a label."""
    current, peak = get_memory_usage()
    cache_bytes, cache_mb, cache_entries = TagCache.get_current_memory_usage()

    print(f"\n{'=' * 70}")
    print(f"{label}")
    print(f"{'=' * 70}")
    print(
        f"Process Memory - Current: {format_size(current)}, Peak: {format_size(peak)}"
    )
    print(
        f"TagCache       - Used: {format_size(cache_bytes)} ({cache_mb:.2f} MB), Entries: {cache_entries}"
    )
    print(f"{'=' * 70}")


def test_memory_leak_detection():
    """Test for memory leaks by running operations multiple times."""
    test_dir = Path(__file__).parent / "test_rename" / "music"
    if not test_dir.exists():
        pytest.skip(f"Test directory not found: {test_dir}")

    # Started only after the skip guard: pytest.skip() raises, so a start()
    # above this point would never reach the stop() below and would leave
    # tracing enabled for the rest of the session.
    tracemalloc.start()

    memory_snapshots = []

    for iteration in range(3):
        # Create database in context manager (ensures cleanup)
        with Database() as db:
            # Add files (some may be corrupted, that's expected)
            db.add_dir(str(test_dir), recursive=False, dircallback=None)
            # At least some files should be added (even if some are corrupted)
            assert len(db.paths) + len(db.failed) > 0, "No files found"

            # Generate database (skip if no valid files)
            if len(db.paths) > 0:
                db.generate_database(callback=None)

            # Get memory snapshot
            current, _ = get_memory_usage()
            cache_bytes, _, _ = TagCache.get_current_memory_usage()
            memory_snapshots.append((current, cache_bytes))

        # Force garbage collection
        gc.collect()

    # Analyze memory growth - allow up to 10% growth (some variance is normal)
    for i in range(1, len(memory_snapshots)):
        prev_proc, prev_cache = memory_snapshots[i - 1]
        curr_proc, curr_cache = memory_snapshots[i]

        proc_growth = curr_proc - prev_proc
        proc_growth_pct = (proc_growth / prev_proc * 100) if prev_proc > 0 else 0

        assert proc_growth_pct <= 10, (
            f"Memory leak detected: {proc_growth_pct:.1f}% growth"
        )

    tracemalloc.stop()


def test_database_operations():
    """Test database operations with test_rename data."""
    test_db_dir = Path(__file__).parent / "test_rename" / "db"
    test_music_dir = Path(__file__).parent / "test_rename" / "music"

    if not test_db_dir.exists() or not test_music_dir.exists():
        pytest.skip("Test directories not found")

    # Started only after the skip guard -- see test_memory_leak_detection.
    tracemalloc.start()

    # Test 1: Read existing database
    with Database() as db:
        db = Database.read(str(test_db_dir), callback=lambda *args, **kwargs: None)
        assert db.index.count > 0, "No entries loaded from database"

    gc.collect()

    # Test 2: Scan music directory (some files may be corrupted)
    with Database() as db:
        db.add_dir(str(test_music_dir), recursive=False, dircallback=None)
        assert len(db.paths) + len(db.failed) > 0, "No music files found"

    gc.collect()

    # Test 3: Generate database (only if valid files exist)
    with Database() as db:
        db.add_dir(str(test_music_dir), recursive=False, dircallback=None)
        if len(db.paths) > 0:
            db.generate_database(callback=None)
            assert db.index.count > 0, "No entries in generated database"

    gc.collect()
    tracemalloc.stop()


def test_executor_cleanup():
    """Test that executor pools are properly shut down."""
    test_music_dir = Path(__file__).parent / "test_rename" / "music"

    if not test_music_dir.exists():
        pytest.skip("Test directory not found")

    initial_threads = threading.active_count()

    # Create and use database
    db = Database()
    db.add_dir(str(test_music_dir), recursive=False, dircallback=None)
    # Only generate if we have valid files
    if len(db.paths) > 0:
        db.generate_database(callback=None)

    # Shutdown database
    db.shutdown(wait=True)
    del db
    gc.collect()

    # Wait a bit for cleanup
    time.sleep(0.5)

    final_threads = threading.active_count()

    # Check if threads were cleaned up (allow some variance for daemon threads)
    assert final_threads <= initial_threads + 2, (
        f"{final_threads - initial_threads} extra threads remaining"
    )


def test_cache_management():
    """Test TagCache memory management."""
    test_music_dir = Path(__file__).parent / "test_rename" / "music"

    if not test_music_dir.exists():
        pytest.skip("Test directory not found")

    # Test cache limits
    initial_limit = TagCache.get_max_cache_memory()

    try:
        # Set a lower limit to test trimming
        TagCache.set_max_cache_memory(100)

        with Database() as db:
            # Add files (some may be corrupted and that's OK)
            db.add_dir(str(test_music_dir), recursive=False, dircallback=None)

            # Verify cache stays within limits
            cache_bytes, cache_mb, cache_entries = TagCache.get_current_memory_usage()
            assert cache_mb <= 100, f"Cache exceeded limit: {cache_mb:.2f} MB > 100 MB"
    finally:
        # Restore original limit even if the assertion above fails, otherwise
        # every later test runs against a 100 MB cache.
        TagCache.set_max_cache_memory(initial_limit)

    # Test cache cleanup
    TagCache.clear()
    cache_bytes, cache_mb, cache_entries = TagCache.get_current_memory_usage()
    assert cache_entries == 0, f"{cache_entries} entries remaining after clear"
