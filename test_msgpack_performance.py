#!/usr/bin/env python3
"""Quick test to verify msgpack performance improvement in cache operations."""

import time
import tempfile
import os
from pathlib import Path

# Test the cache module
from src.dap_db_manager.database.cache import TagCache, USE_MSGPACK

def generate_test_data(num_entries=1000):
    """Generate test tag data."""
    test_data = {}
    for i in range(num_entries):
        path = f"/music/artist{i % 100}/album{i % 50}/track{i}.mp3"
        tags = {
            'artist': [f'Artist {i % 100}'],
            'album': [f'Album {i % 50}'],
            'title': [f'Track {i}'],
            'genre': ['Rock'],
            'date': ['2024'],
            'tracknumber': [str(i % 20 + 1)],
            'length': ['240.5'],
            'bitrate': ['320']
        }
        test_data[path.lower()] = ((1024 * 100, 1700000000 + i), tags)
    return test_data

def test_cache_performance():
    """Test cache save/load performance."""
    print(f"Using msgpack: {USE_MSGPACK}")
    print("\n" + "="*60)

    # Generate test data
    num_entries = 5000
    print(f"Generating {num_entries} test entries...")
    test_data = generate_test_data(num_entries)

    # Load test data into cache
    TagCache.clear()
    for path, data in test_data.items():
        TagCache.set(path, data)

    paths_set = set(test_data.keys())

    # Test save performance
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "test_cache.gz")

        print(f"\nTesting SAVE performance with {num_entries} entries...")
        start = time.perf_counter()
        TagCache.save(cache_file, paths_set)
        save_time = time.perf_counter() - start

        file_size = Path(cache_file).stat().st_size / (1024 * 1024)  # MB
        print(f"  Save time: {save_time:.3f}s")
        print(f"  File size: {file_size:.2f} MB")
        print(f"  Speed: {num_entries / save_time:.0f} entries/sec")

        # Test load performance
        TagCache.clear()
        paths_set = set()

        print(f"\nTesting LOAD performance with {num_entries} entries...")
        start = time.perf_counter()
        TagCache.load(cache_file, paths_set)
        load_time = time.perf_counter() - start

        print(f"  Load time: {load_time:.3f}s")
        print(f"  Speed: {num_entries / load_time:.0f} entries/sec")
        print(f"  Entries loaded: {len(paths_set)}")

        # Summary
        print("\n" + "="*60)
        print("SUMMARY:")
        print(f"  Total time: {save_time + load_time:.3f}s")
        print(f"  Serialization format: {'MessagePack' if USE_MSGPACK else 'Pickle'}")
        if USE_MSGPACK:
            print(f"  ✓ Using optimized MessagePack serialization!")
            print(f"  Expected: 20-40% faster than pickle")
        else:
            print(f"  ⚠ Using fallback pickle (install msgpack for better performance)")

if __name__ == "__main__":
    test_cache_performance()
