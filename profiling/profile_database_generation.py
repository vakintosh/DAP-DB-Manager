#!/usr/bin/env python3
"""Profile database generation to find performance bottlenecks.

Usage:
    python profiling/profile_database_generation.py /path/to/music

This will generate a profile of the database generation process and print
statistics about where time is being spent.
"""

import sys
import cProfile
import pstats
from pathlib import Path
from io import StringIO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dap_db_manager.database import Database


def profile_database_generation(music_dir: str):
    """Profile database generation."""
    print(f"Profiling database generation for: {music_dir}")
    print("=" * 70)

    # Create profiler
    profiler = cProfile.Profile()

    # Profile the generation
    profiler.enable()
    try:
        db = Database()
        db.add_dir(music_dir, recursive=True)
        db.generate_database()
    finally:
        profiler.disable()

    # Print statistics
    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)

    print("\n=== Top 20 functions by cumulative time ===")
    stats.sort_stats("cumulative")
    stats.print_stats(20)
    print(s.getvalue())

    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)
    print("\n=== Top 20 functions by total time ===")
    stats.sort_stats("tottime")
    stats.print_stats(20)
    print(s.getvalue())

    # Save to file for detailed analysis
    output_file = Path(__file__).parent / "profile_database_generation.prof"
    profiler.dump_stats(str(output_file))
    print(f"\n✓ Full profile saved to: {output_file}")
    print(f"\nAnalyze with: python -m pstats {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python profile_database_generation.py /path/to/music")
        sys.exit(1)

    music_dir = sys.argv[1]
    if not Path(music_dir).exists():
        print(f"Error: Directory does not exist: {music_dir}")
        sys.exit(1)

    profile_database_generation(music_dir)
