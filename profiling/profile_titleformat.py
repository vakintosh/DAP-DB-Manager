#!/usr/bin/env python3
"""Profile titleformat parsing and evaluation.

Usage:
    python profiling/profile_titleformat.py "%artist% - %album% - %title%"

This will profile titleformat parsing and evaluation.
"""

import sys
import cProfile
import pstats
from pathlib import Path
from io import StringIO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dap_db_manager.tagging.titleformat import statement


class MockTags:
    """Mock tags object for testing."""

    def get_string(self, field):
        """Return mock tag data."""
        mock_data = {
            "artist": ["Test Artist"],
            "album": ["Test Album"],
            "title": ["Test Title"],
            "albumartist": ["Test Album Artist"],
            "genre": ["Rock"],
            "year": ["2024"],
            "tracknumber": ["01"],
            "discnumber": ["1"],
            "bitrate": ["320000"],
            "length": ["180.5"],
        }
        return mock_data.get(field, [f"Mock {field}"])


def profile_titleformat(format_string: str, iterations: int = 1000):
    """Profile titleformat parsing and evaluation."""
    print(f"Profiling titleformat: {format_string}")
    print(f"Iterations: {iterations}")
    print("=" * 70)

    # Create profiler
    profiler = cProfile.Profile()
    tags = MockTags()

    # Profile parsing and evaluation
    profiler.enable()
    try:
        # Parse the format string (returns tuple)
        parsed, _ = statement.parse(format_string)

        # Evaluate multiple times to get meaningful data
        for _ in range(iterations):
            parsed.format(tags)
    finally:
        profiler.disable()

    # Print statistics
    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)

    print("\n=== Top 30 functions by cumulative time ===")
    stats.sort_stats("cumulative")
    stats.print_stats(30)
    print(s.getvalue())

    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)
    print("\n=== Top 30 functions by total time ===")
    stats.sort_stats("tottime")
    stats.print_stats(30)
    print(s.getvalue())

    # Save to file
    output_file = Path(__file__).parent / "profile_titleformat.prof"
    profiler.dump_stats(str(output_file))
    print(f"\n✓ Full profile saved to: {output_file}")
    print(f"\nAnalyze with: python -m pstats {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python profile_titleformat.py <format_string> [iterations]")
        print("\nExamples:")
        print('  python profile_titleformat.py "%artist% - %album%"')
        print(
            '  python profile_titleformat.py "$if(%albumartist%,%albumartist%,%artist%)" 5000'
        )
        sys.exit(1)

    format_string = sys.argv[1]
    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    profile_titleformat(format_string, iterations)
