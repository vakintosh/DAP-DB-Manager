#!/usr/bin/env python3
"""Profile tag parsing operations to find bottlenecks.

Usage:
    python profiling/profile_tag_parsing.py /path/to/audio/file.mp3

This will profile the tag reading process for a single file.
"""

import sys
import cProfile
import pstats
from pathlib import Path
from io import StringIO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dap_db_manager.tagging.tag.core import Tagger


def profile_tag_parsing(audio_file: str):
    """Profile tag parsing for a single audio file."""
    print(f"Profiling tag parsing for: {audio_file}")
    print("=" * 70)

    # Create profiler
    profiler = cProfile.Profile()

    # Profile the parsing
    profiler.enable()
    try:
        tagger = Tagger()
        tags = tagger.get_tags(audio_file)

        # Access various tag fields to profile retrieval
        _ = tags.get_string("artist")
        _ = tags.get_string("album")
        _ = tags.get_string("title")
        _ = tags.get_string("tracknumber")
        _ = tags.get_string("genre")
        _ = tags.get_string("year")
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

    # Save to file
    output_file = Path(__file__).parent / "profile_tag_parsing.prof"
    profiler.dump_stats(str(output_file))
    print(f"\n✓ Full profile saved to: {output_file}")
    print(f"\nAnalyze with: python -m pstats {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python profile_tag_parsing.py /path/to/audio/file.mp3")
        sys.exit(1)

    audio_file = sys.argv[1]
    if not Path(audio_file).exists():
        print(f"Error: File does not exist: {audio_file}")
        sys.exit(1)

    profile_tag_parsing(audio_file)
