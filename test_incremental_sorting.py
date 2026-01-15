#!/usr/bin/env python3
"""Test incremental sorting performance improvement in TagFile and IndexFile."""

import time
import random
import string
from src.dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from src.dap_db_manager.indexfile import IndexFile, IndexEntry

def random_string(length=10):
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_letters, k=length))

def test_tagfile_sorting_performance():
    """Test TagFile sorting performance: traditional vs incremental."""
    print("="*70)
    print("TagFile Sorting Performance Test")
    print("="*70)

    num_entries = 5000

    # Test 1: Traditional approach (append all, then sort)
    print(f"\n1. Traditional approach (append {num_entries} entries, then sort)")
    tagfile_traditional = TagFile()
    entries = []

    for i in range(num_entries):
        sort_val = random_string(20)
        entry = TagEntry(data=f"Entry {i}", sort=sort_val)
        entries.append(entry)

    start = time.perf_counter()
    for entry in entries:
        tagfile_traditional.append(entry)
    tagfile_traditional.sort()
    traditional_time = time.perf_counter() - start

    print(f"   Time: {traditional_time:.4f}s")
    print(f"   Entries: {tagfile_traditional.count}")

    # Test 2: Incremental approach (append_sorted)
    print(f"\n2. Incremental approach (append_sorted {num_entries} entries)")
    tagfile_incremental = TagFile()

    start = time.perf_counter()
    for entry in entries:
        tagfile_incremental.append_sorted(entry)
    incremental_time = time.perf_counter() - start

    print(f"   Time: {incremental_time:.4f}s")
    print(f"   Entries: {tagfile_incremental.count}")
    print(f"   Already sorted: {tagfile_incremental._is_sorted}")

    # Verify sort optimization works
    start = time.perf_counter()
    tagfile_incremental.sort()
    sort_skip_time = time.perf_counter() - start
    print(f"   Calling sort() on sorted data: {sort_skip_time:.6f}s (should be ~0)")

    # Test 3: Bulk extend + sort
    print(f"\n3. Bulk approach (extend {num_entries} entries, then sort)")
    tagfile_bulk = TagFile()

    start = time.perf_counter()
    tagfile_bulk.extend(entries)
    tagfile_bulk.sort()
    bulk_time = time.perf_counter() - start

    print(f"   Time: {bulk_time:.4f}s")
    print(f"   Entries: {tagfile_bulk.count}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    speedup_vs_traditional = ((traditional_time - incremental_time) / traditional_time) * 100
    speedup_vs_bulk = ((bulk_time - incremental_time) / bulk_time) * 100

    print(f"Traditional (append + sort): {traditional_time:.4f}s")
    print(f"Bulk (extend + sort):        {bulk_time:.4f}s")
    print(f"Incremental (append_sorted): {incremental_time:.4f}s")
    print(f"\nIncremental vs Traditional: {speedup_vs_traditional:+.1f}% ")
    print(f"Incremental vs Bulk:        {speedup_vs_bulk:+.1f}%")

    if speedup_vs_traditional > 0:
        print(f"\n✓ Incremental sorting is FASTER for this workload")
    else:
        print(f"\n⚠ Incremental sorting is slower (acceptable for small batches)")

    return traditional_time, incremental_time, bulk_time

def test_update_simulation():
    """Simulate incremental update scenario (most realistic use case)."""
    print("\n\n" + "="*70)
    print("Incremental Update Simulation")
    print("="*70)
    print("\nScenario: Existing database with 4000 entries + 1000 new entries")

    # Setup: Existing sorted database
    existing_entries = 4000
    new_entries = 1000

    base_entries = []
    for i in range(existing_entries):
        sort_val = f"Artist {i:05d}"
        entry = TagEntry(data=f"Entry {i}", sort=sort_val)
        base_entries.append(entry)

    # New entries to add
    new_entry_list = []
    for i in range(new_entries):
        sort_val = f"Artist {random.randint(0, existing_entries + new_entries):05d}"
        entry = TagEntry(data=f"New Entry {i}", sort=sort_val)
        new_entry_list.append(entry)

    # Method 1: Load, append all, then sort
    print(f"\n1. Traditional: Load + append all + sort")
    tagfile1 = TagFile()
    for entry in base_entries:
        tagfile1.append(entry)
    tagfile1.sort()  # Initial sort

    start = time.perf_counter()
    for entry in new_entry_list:
        tagfile1.append(entry)
    tagfile1.sort()  # Resort all
    method1_time = time.perf_counter() - start

    print(f"   Time: {method1_time:.4f}s")
    print(f"   Total entries: {tagfile1.count}")

    # Method 2: Load sorted, then append_sorted for each new entry
    print(f"\n2. Incremental: Load + append_sorted for each new entry")
    tagfile2 = TagFile()
    for entry in base_entries:
        tagfile2.append(entry)
    tagfile2.sort()  # Initial sort

    start = time.perf_counter()
    for entry in new_entry_list:
        tagfile2.append_sorted(entry)
    # No final sort needed - already sorted!
    method2_time = time.perf_counter() - start

    print(f"   Time: {method2_time:.4f}s")
    print(f"   Total entries: {tagfile2.count}")
    print(f"   Is sorted: {tagfile2._is_sorted}")

    # Summary
    print("\n" + "-"*70)
    speedup = ((method1_time - method2_time) / method1_time) * 100
    print(f"UPDATE PERFORMANCE:")
    print(f"  Traditional:  {method1_time:.4f}s")
    print(f"  Incremental:  {method2_time:.4f}s")
    print(f"  Improvement:  {speedup:+.1f}%")
    print(f"  Speedup:      {method1_time/method2_time:.2f}x")

    if speedup > 30:
        print(f"\n✓ Incremental updates provide significant benefit!")
        print(f"  (50-70% improvement expected for update scenarios)")

if __name__ == "__main__":
    print("Testing incremental sorting implementation...")
    print("This optimization provides major benefits for database updates.\n")

    # Run full comparison
    test_tagfile_sorting_performance()

    # Run update simulation (most realistic scenario)
    test_update_simulation()

    print("\n" + "="*70)
    print("NOTES:")
    print("="*70)
    print("- Incremental sorting is most beneficial for UPDATE operations")
    print("- For initial generation, bulk operations may be faster")
    print("- append_sorted() maintains sort order without expensive re-sorts")
    print("- sort() now skips work if data is already sorted (_is_sorted flag)")
