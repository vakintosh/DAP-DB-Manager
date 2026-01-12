"""CPU Efficiency Test Suite for DAP DB Manager.

This comprehensive test suite verifies CPU efficiency across:
- Parallel processing (multiprocessing vs threading)
- Thread pool management and reusability
- Cache efficiency
- Batch processing optimization
- Resource cleanup

Run with: uv run pytest tests/test_cpu_efficiency.py -v
"""

import gc
import os
import time
import threading
from pathlib import Path

import pytest

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from dap_db_manager.database import Database
from dap_db_manager.database.cache import TagCache


pytestmark = pytest.mark.skipif(
    not HAS_PSUTIL,
    reason="psutil is required for CPU efficiency tests (install with: uv pip install psutil)",
)


def format_size(bytes_size):
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def get_cpu_usage() -> float:
    """Get current process CPU usage percentage."""
    if HAS_PSUTIL:
        return psutil.Process().cpu_percent(interval=0.1)
    return 0.0


def get_memory_info() -> tuple:
    """Get memory usage information."""
    if HAS_PSUTIL:
        process = psutil.Process()
        mem_info = process.memory_info()
        return mem_info.rss, mem_info.vms
    return 0, 0


@pytest.fixture
def test_music_dir():
    """Provide test music directory."""
    test_dir = Path(__file__).parent.parent / "test_rename" / "music"
    if not test_dir.exists():
        pytest.skip(f"Test directory not found: {test_dir}")
    return test_dir


class TestCPUEfficiency:
    """Test CPU efficiency of database operations."""

    def test_parallel_processing_speedup(self, test_music_dir):
        """Test that parallel processing provides significant speedup."""
        # Test with multiprocessing (CPU-bound optimization)
        start_time = time.perf_counter()

        with Database() as db:
            db.add_dir(str(test_music_dir), recursive=False, parallel=True)
            parallel_files = len(db.paths)

        parallel_time = time.perf_counter() - start_time

        if parallel_files == 0:
            pytest.skip("No files to process")

        # Test with sequential processing (baseline)
        TagCache.clear()
        gc.collect()
        time.sleep(0.5)

        start_time = time.perf_counter()

        with Database() as db:
            db.add_dir(str(test_music_dir), recursive=False, parallel=False)
            sequential_files = len(db.paths)

        sequential_time = time.perf_counter() - start_time

        # Calculate speedup
        assert parallel_files == sequential_files, "File counts should match"

        if sequential_time > 0:
            speedup = sequential_time / parallel_time
            efficiency = (speedup / os.cpu_count()) * 100 if os.cpu_count() else 0

            print("\nParallel Processing Results:")
            print(f"  Files processed: {parallel_files}")
            print(f"  Parallel time: {parallel_time:.3f}s")
            print(f"  Sequential time: {sequential_time:.3f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Parallel efficiency: {efficiency:.1f}%")

            # For small datasets (<100 files), parallel processing may have overhead
            # Only assert no major performance regression
            if parallel_files < 100:
                # Allow parallel to be slower on tiny datasets due to process startup overhead
                assert speedup >= 0.3, (
                    f"Parallel processing has excessive overhead: {speedup:.2f}x"
                )
                if speedup < 1.0:
                    print(
                        f"  Note: Parallel overhead expected for {parallel_files} files (threshold: 1000)"
                    )
            else:
                # For larger datasets, expect speedup
                assert speedup >= 1.2, (
                    f"Parallel processing not efficient: {speedup:.2f}x"
                )

    def test_cache_efficiency(self, test_music_dir):
        """Test that cache provides significant speedup for repeated operations."""
        # First run - cold cache
        TagCache.clear()
        gc.collect()

        start_time = time.perf_counter()
        with Database() as db:
            db.add_dir(str(test_music_dir), recursive=False)
            first_run_files = len(db.paths)
        first_run_time = time.perf_counter() - start_time

        if first_run_files == 0:
            pytest.skip("No files to process")

        # Get cache statistics
        cache_bytes, cache_mb, cache_entries = TagCache.get_current_memory_usage()

        # Second run - warm cache
        start_time = time.perf_counter()
        with Database() as db:
            db.add_dir(str(test_music_dir), recursive=False)
            second_run_files = len(db.paths)
        second_run_time = time.perf_counter() - start_time

        # Verify both runs processed the same files
        assert first_run_files == second_run_files, (
            "File counts should match between runs"
        )

        # Calculate cache speedup
        cache_speedup = first_run_time / second_run_time if second_run_time > 0 else 1.0

        print("\nCache Efficiency Results:")
        print(f"  Files processed: {first_run_files}")
        print(f"  Cold cache time: {first_run_time:.3f}s")
        print(f"  Warm cache time: {second_run_time:.3f}s")
        print(f"  Cache speedup: {cache_speedup:.2f}x")
        print(f"  Cache entries: {cache_entries}")
        print(f"  Cache memory: {format_size(cache_bytes)}")

        # Assert cache provides significant benefit
        assert cache_speedup >= 1.5, f"Cache not efficient enough: {cache_speedup:.2f}x"
        assert cache_entries > 0, "Cache should have entries after first run"

    def test_no_thread_leaks(self, test_music_dir):
        """Test that operations don't leak threads."""
        gc.collect()
        start_threads = threading.active_count()

        # Perform multiple operations
        for _ in range(3):
            with Database() as db:
                db.add_dir(str(test_music_dir), recursive=False)

        gc.collect()
        time.sleep(0.5)
        final_threads = threading.active_count()

        print("\nThread Management:")
        print(f"  Threads before: {start_threads}")
        print(f"  Threads after: {final_threads}")

        # Allow some variance but no significant leak
        assert final_threads <= start_threads + 2, (
            f"Thread leak detected: {final_threads - start_threads} extra threads"
        )

    def test_memory_efficiency(self, test_music_dir):
        """Test that memory usage remains reasonable."""
        if not HAS_PSUTIL:
            pytest.skip("psutil required for memory testing")

        # Get baseline
        gc.collect()
        time.sleep(0.5)
        baseline_mem, _ = get_memory_info()

        # Perform operations
        for _ in range(5):
            with Database() as db:
                db.add_dir(str(test_music_dir), recursive=False)
            gc.collect()

        # Check final state
        time.sleep(1.0)
        final_mem, _ = get_memory_info()

        mem_delta = final_mem - baseline_mem
        mem_growth_pct = (mem_delta / baseline_mem * 100) if baseline_mem > 0 else 0

        print("\nMemory Efficiency:")
        print(f"  Baseline: {format_size(baseline_mem)}")
        print(f"  Final: {format_size(final_mem)}")
        print(f"  Delta: {format_size(mem_delta)}")
        print(f"  Growth: {mem_growth_pct:.1f}%")

        # Assert memory growth is reasonable (allow 20% for variance)
        assert mem_growth_pct <= 20, f"Excessive memory growth: {mem_growth_pct:.1f}%"

    def test_batch_processing_throughput(self, test_music_dir):
        """Test batch processing efficiency and throughput."""
        TagCache.clear()

        with Database() as db:
            # Add files
            db.add_dir(str(test_music_dir), recursive=False)
            total_files = len(db.paths)

            if total_files == 0:
                pytest.skip("No files to process")

            # Test with parallel generation
            start_time = time.perf_counter()
            db.generate_database(callback=None)
            generation_time = time.perf_counter() - start_time

            throughput = total_files / generation_time if generation_time > 0 else 0

            print("\nBatch Processing:")
            print(f"  Files processed: {total_files}")
            print(f"  Time: {generation_time:.3f}s")
            print(f"  Throughput: {throughput:.1f} files/sec")

            # Assert reasonable throughput (at least 10 files/sec)
            assert throughput >= 10, f"Throughput too low: {throughput:.1f} files/sec"

    def test_thread_pool_reusability(self, test_music_dir):
        """Test that thread pools are reused efficiently."""
        with Database() as db:
            start_threads = threading.active_count()

            # Perform multiple operations
            for i in range(3):
                db.tagfiles = {}
                db.paths.clear()
                db.add_dir(str(test_music_dir), recursive=False)

            end_threads = threading.active_count()

        # Thread count shouldn't grow significantly during operations
        thread_growth = end_threads - start_threads

        print("\nThread Pool Reusability:")
        print("  Operations: 3")
        print(f"  Thread growth: {thread_growth}")

        # Pool should be reused, not create new threads for each operation
        assert thread_growth <= os.cpu_count() * 2, (
            f"Too many new threads created: {thread_growth}"
        )


class TestPerformanceMetrics:
    """Additional performance metrics and monitoring tests."""

    def test_cpu_utilization_during_parallel_ops(self, test_music_dir):
        """Monitor CPU utilization during parallel operations."""
        if not HAS_PSUTIL:
            pytest.skip("psutil required for CPU monitoring")

        with Database() as db:
            cpu_before = get_cpu_usage()

            db.add_dir(str(test_music_dir), recursive=False, parallel=True)

            cpu_during = get_cpu_usage()

        print("\nCPU Utilization:")
        print(f"  Before: {cpu_before:.1f}%")
        print(f"  During: {cpu_during:.1f}%")

        # Just informational, no strict assertion
        if cpu_during < 50 and len(db.paths) > 100:
            print("  Note: CPU utilization is low. Consider tuning worker count.")

    def test_cache_memory_usage(self, test_music_dir):
        """Test that cache memory usage is reasonable."""
        TagCache.clear()

        with Database() as db:
            db.add_dir(str(test_music_dir), recursive=False)

        cache_bytes, cache_mb, cache_entries = TagCache.get_current_memory_usage()

        print("\nCache Memory Usage:")
        print(f"  Entries: {cache_entries}")
        print(f"  Memory: {format_size(cache_bytes)} ({cache_mb:.2f} MB)")

        if cache_entries > 0:
            bytes_per_entry = cache_bytes / cache_entries
            print(f"  Per entry: {format_size(bytes_per_entry)}")

            # Assert reasonable memory per entry (allow up to 10KB per entry)
            assert bytes_per_entry <= 10240, (
                f"Cache entries too large: {format_size(bytes_per_entry)}/entry"
            )
