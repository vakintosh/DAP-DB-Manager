"""Performance regression tests.

These tests track performance over time to detect regressions.
Baseline performance metrics are stored in .performance_baselines.json

Run with: pytest tests/test_performance_regression.py
Update baselines: pytest tests/test_performance_regression.py --update-baselines
"""

import json
import time
import pytest
from pathlib import Path

from dap_db_manager.database import Database
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from dap_db_manager.tagging.titleformat import statement
from dap_db_manager.utils import mtime_to_fat, fat_to_mtime


BASELINE_FILE = Path(__file__).parent / ".performance_baselines.json"

# Performance thresholds (% slower than baseline)
THRESHOLD_WARNING = 10  # Warn if 10% slower
THRESHOLD_FAIL = 25  # Fail if 25% slower


class PerformanceTracker:
    """Track performance metrics against baselines."""

    def __init__(self):
        self.baselines = self._load_baselines()
        self.update_mode = False

    def _load_baselines(self):
        """Load baseline performance metrics."""
        if BASELINE_FILE.exists():
            with open(BASELINE_FILE, "r") as f:
                return json.load(f)
        return {}

    def _save_baselines(self):
        """Save baseline performance metrics."""
        with open(BASELINE_FILE, "w") as f:
            json.dump(self.baselines, f, indent=2)

    def track(self, test_name: str, duration: float, tolerance_multiplier: float = 1.0):
        """Track performance and compare to baseline.

        Args:
            test_name: Name of the test
            duration: Measured duration in seconds
            tolerance_multiplier: Multiplier for thresholds (use >1 for naturally variable tests)
        """
        if self.update_mode:
            self.baselines[test_name] = duration
            self._save_baselines()
            return

        if test_name not in self.baselines:
            # No baseline, save current as baseline
            self.baselines[test_name] = duration
            self._save_baselines()
            pytest.skip(
                f"No baseline for {test_name}, saved {duration:.4f}s as baseline"
            )

        baseline = self.baselines[test_name]
        change_pct = ((duration - baseline) / baseline) * 100

        threshold_warn = THRESHOLD_WARNING * tolerance_multiplier
        threshold_fail = THRESHOLD_FAIL * tolerance_multiplier

        if change_pct > threshold_fail:
            pytest.fail(
                f"Performance regression detected! {test_name} is {change_pct:.1f}% slower "
                f"(baseline: {baseline:.4f}s, current: {duration:.4f}s)"
            )
        elif change_pct > threshold_warn:
            import warnings

            warnings.warn(
                f"Performance warning: {test_name} is {change_pct:.1f}% slower "
                f"(baseline: {baseline:.4f}s, current: {duration:.4f}s)",
                UserWarning,
            )


@pytest.fixture
def performance_tracker(request):
    """Create performance tracker fixture."""
    tracker = PerformanceTracker()
    # Check if --update-baselines flag is set
    tracker.update_mode = request.config.getoption("--update-baselines", False)
    return tracker


class TestPerformanceRegression:
    """Performance regression tests."""

    def test_tagfile_creation_performance(self, performance_tracker):
        """Track TagFile creation performance."""
        iterations = 100

        start = time.perf_counter()
        tagfile = TagFile()
        for i in range(iterations):
            tagfile.append(TagEntry(f"Artist {i}"))
        duration = time.perf_counter() - start

        performance_tracker.track("tagfile_creation_100", duration)

    def test_tagfile_write_performance(self, performance_tracker, tmp_path):
        """Track TagFile write performance."""
        tagfile = TagFile()
        for i in range(1000):
            tagfile.append(TagEntry(f"Artist {i}"))

        output_path = tmp_path / "test.tag"

        start = time.perf_counter()
        tagfile.write(str(output_path))
        duration = time.perf_counter() - start

        performance_tracker.track(
            "tagfile_write_1000", duration, tolerance_multiplier=1.5
        )

    def test_tagfile_read_performance(self, performance_tracker, tmp_path):
        """Track TagFile read performance."""
        # Create test file
        tagfile = TagFile()
        for i in range(1000):
            tagfile.append(TagEntry(f"Artist {i}"))

        test_path = tmp_path / "test.tag"
        tagfile.write(str(test_path))

        start = time.perf_counter()
        TagFile.read(str(test_path))
        duration = time.perf_counter() - start

        # Higher tolerance for I/O operations due to disk/system variability
        performance_tracker.track(
            "tagfile_read_1000", duration, tolerance_multiplier=2.0
        )

    def test_titleformat_parsing_performance(self, performance_tracker):
        """Track titleformat parsing performance."""
        format_string = "%artist% - %album% [$year(%date%)]"
        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            _parsed, _ = statement.parse(format_string)
        duration = time.perf_counter() - start

        performance_tracker.track("titleformat_parse_complex_100", duration)

    def test_titleformat_evaluation_performance(self, performance_tracker):
        """Track titleformat evaluation performance."""
        format_string = "%artist% - %album% - %title%"
        parsed, _ = statement.parse(format_string)

        class MockTags:
            def get_string(self, field):
                return [f"Test {field}"]

        tags = MockTags()
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            _result = parsed.format(tags)
        duration = time.perf_counter() - start

        performance_tracker.track("titleformat_eval_simple_1000", duration)

    def test_utils_conversion_performance(self, performance_tracker):
        """Track utility function performance."""
        timestamp = time.time()
        iterations = 10000

        start = time.perf_counter()
        for _ in range(iterations):
            fat_time = mtime_to_fat(timestamp)
            _ = fat_to_mtime(fat_time)
        duration = time.perf_counter() - start

        performance_tracker.track("utils_conversion_10000", duration)

    def test_database_initialization_performance(self, performance_tracker):
        """Track Database initialization performance."""
        iterations = 100

        start = time.perf_counter()
        for _ in range(iterations):
            _db = Database()
        duration = time.perf_counter() - start

        performance_tracker.track("database_init_100", duration)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
