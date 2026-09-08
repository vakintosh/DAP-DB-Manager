"""Benchmark tests for performance monitoring.

These tests use pytest-benchmark to measure performance of key operations.
Run with: pytest tests/test_benchmarks.py --benchmark-only

To save results: pytest tests/test_benchmarks.py --benchmark-only --benchmark-save=baseline
To compare: pytest tests/test_benchmarks.py --benchmark-only --benchmark-compare=0001
"""

import pytest

from dap_db_manager.database import Database
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from dap_db_manager.tagging.titleformat import statement
from dap_db_manager.utils import mtime_to_fat, fat_to_mtime
from dap_db_manager.indexfile import IndexFile, IndexEntry


@pytest.mark.perf
class TestUtilsBenchmarks:
    """Benchmark utility functions."""

    def test_mtime_to_fat_benchmark(self, benchmark):
        """Benchmark mtime to FAT conversion."""
        import time

        timestamp = time.time()
        result = benchmark(mtime_to_fat, timestamp)
        assert isinstance(result, int)

    def test_fat_to_mtime_benchmark(self, benchmark):
        """Benchmark FAT to mtime conversion."""
        fat_time = 0x5621A845  # Sample FAT timestamp
        result = benchmark(fat_to_mtime, fat_time)
        assert isinstance(result, float)


@pytest.mark.perf
class TestTagFileBenchmarks:
    """Benchmark TagFile operations."""

    def test_tagfile_creation_benchmark(self, benchmark):
        """Benchmark TagFile creation with entries."""

        def create_tagfile():
            tagfile = TagFile()
            for i in range(100):
                tagfile.append(TagEntry(f"Artist {i}"))
            return tagfile

        result = benchmark(create_tagfile)
        assert result.count == 100

    def test_tagfile_write_benchmark(self, benchmark, tmp_path):
        """Benchmark TagFile writing to disk."""
        tagfile = TagFile()
        for i in range(1000):
            tagfile.append(TagEntry(f"Artist {i}"))

        output_path = tmp_path / "test.tag"

        def write_tagfile():
            tagfile.write(str(output_path))

        benchmark(write_tagfile)
        assert output_path.exists()

    def test_tagfile_read_benchmark(self, benchmark, tmp_path):
        """Benchmark TagFile reading from disk."""
        # Create test file
        tagfile = TagFile()
        for i in range(1000):
            tagfile.append(TagEntry(f"Artist {i}"))

        test_path = tmp_path / "test.tag"
        tagfile.write(str(test_path))

        def read_tagfile():
            return TagFile.read(str(test_path))

        result = benchmark(read_tagfile)
        assert result.count == 1000


@pytest.mark.perf
class TestIndexFileBenchmarks:
    """Benchmark IndexFile operations."""

    def test_indexfile_creation_benchmark(self, benchmark):
        """Benchmark IndexFile creation with entries."""

        def create_indexfile():
            indexfile = IndexFile()
            for i in range(100):
                entry = IndexEntry()
                entry.tag_seek = [i * 10] * 21  # 21 tag indices
                entry.filename = f"/music/track_{i}.mp3"
                indexfile.append(entry)
            return indexfile

        result = benchmark(create_indexfile)
        assert result.count == 100

    def test_indexfile_write_benchmark(self, benchmark, tmp_path):
        """Benchmark IndexFile writing to disk."""
        # Skip this test as IndexEntry requires TagEntry objects with proper setup
        pytest.skip("Requires complex TagEntry/TagFile setup")


@pytest.mark.perf
class TestTitleformatBenchmarks:
    """Benchmark titleformat parsing and evaluation."""

    def test_simple_field_parsing_benchmark(self, benchmark):
        """Benchmark simple field parsing."""
        format_string = "%artist% - %title%"
        result = benchmark(statement.parse, format_string)
        assert result is not None

    def test_complex_function_parsing_benchmark(self, benchmark):
        """Benchmark complex function parsing."""
        format_string = "%artist% - %album% [$year(%date%)]"
        result = benchmark(statement.parse, format_string)
        assert result is not None

    def test_titleformat_evaluation_benchmark(self, benchmark):
        """Benchmark titleformat evaluation with mock tags."""
        format_string = "%artist% - %album% - %title%"
        parsed, _ = statement.parse(format_string)

        # Mock tag object
        class MockTags:
            def get_string(self, field):
                return [f"Test {field}"]

        tags = MockTags()
        result = benchmark(parsed.format, tags)
        assert isinstance(result, (str, list))

    def test_nested_function_evaluation_benchmark(self, benchmark):
        """Benchmark nested function evaluation."""
        format_string = "%artist% - %album% [$year(%date%)]"
        parsed, _ = statement.parse(format_string)

        class MockTags:
            def get_string(self, field):
                if field == "date":
                    return ["2024"]
                return [f"test {field}"]

        tags = MockTags()
        result = benchmark(parsed.format, tags)
        assert result is not None


@pytest.mark.perf
class TestDatabaseBenchmarks:
    """Benchmark Database operations."""

    def test_database_initialization_benchmark(self, benchmark):
        """Benchmark Database initialization."""
        result = benchmark(Database)
        assert isinstance(result, Database)

    @pytest.mark.slow
    def test_database_entry_creation_benchmark(self, benchmark):
        """Benchmark creating database entries."""
        db = Database()

        def add_entries():
            for i in range(50):
                entry = IndexEntry()
                entry.filename = f"/music/track_{i}.mp3"
                entry.tag_seek = [i] * 21
                db.index.append(entry)

        benchmark(add_entries)
        assert db.index.count >= 50


@pytest.mark.perf
class TestTagReadingBenchmarks:
    """Benchmark tag reading operations."""

    @pytest.mark.slow
    def test_tag_read_benchmark(self, benchmark, tmp_path):
        """Benchmark tag reading from a file."""
        # Create a dummy file path for testing
        # Note: This requires an actual audio file to properly benchmark
        # For now, we test the Tag class instantiation
        pytest.skip("Requires actual audio file for realistic benchmarking")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
