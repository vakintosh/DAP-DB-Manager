#!/usr/bin/env python3
"""Memory profiling for dap-db-manager.

Usage:
    python profiling/memory_profile.py /path/to/music

This will profile memory usage during database generation.

Requires: memory_profiler (pip install memory_profiler)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from memory_profiler import profile
except ImportError:
    print("Error: memory_profiler not installed")
    print("Install with: pip install memory_profiler")
    sys.exit(1)

from dap_db_manager.database import Database


@profile
def generate_database(music_dir: str):
    """Generate database with memory profiling."""
    db = Database()
    db.scan(music_dir)
    return db


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python memory_profile.py /path/to/music")
        sys.exit(1)

    music_dir = sys.argv[1]
    if not Path(music_dir).exists():
        print(f"Error: Directory does not exist: {music_dir}")
        sys.exit(1)

    print(f"Memory profiling database generation for: {music_dir}")
    print("=" * 70)

    db = generate_database(music_dir)

    print("\n" + "=" * 70)
    print(f"✓ Database generated with {len(db.idx)} entries")
