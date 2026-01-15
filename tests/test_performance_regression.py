"""Performance regression tests.

These tests track performance over time to detect regressions.
Baseline performance metrics are stored in .performance_baselines.json

Run with: pytest tests/test_performance_regression.py
Update baselines: pytest tests/test_performance_regression.py --update-baselines
"""

import json
import time
import pytest
import statistics
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict
from datetime import datetime

from dap_db_manager.database import Database
from dap_db_manager.tagging.tag.tagfile import TagFile, TagEntry
from dap_db_manager.tagging.titleformat import statement
from dap_db_manager.utils import mtime_to_fat, fat_to_mtime


BASELINE_FILE = Path(__file__).parent / ".performance_baselines.json"

# Performance thresholds (% slower than baseline)
THRESHOLD_WARNING = 10  # Warn if 10% slower
THRESHOLD_FAIL = 25  # Fail if 25% slower


@dataclass
class PerformanceMetric:
    """Statistical performance metric with trend tracking."""

    mean: float
    median: float
    std_dev: float
    min: float
    max: float
    samples: List[float]
    last_updated: str

    def is_regression(self, current: float, threshold_pct: float) -> bool:
        """Check if current value represents a regression."""
        # Use median instead of mean for robustness to outliers
        baseline = self.median
        change_pct = ((current - baseline) / baseline) * 100
        return change_pct > threshold_pct

    def add_sample(self, value: float, max_samples: int = 100):
        """Add new sample and update statistics."""
        self.samples.append(value)

        # Keep only recent samples (rolling window)
        if len(self.samples) > max_samples:
            self.samples = self.samples[-max_samples:]

        self.mean = statistics.mean(self.samples)
        self.median = statistics.median(self.samples)
        self.std_dev = statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0
        self.min = min(self.samples)
        self.max = max(self.samples)
        self.last_updated = datetime.now().isoformat()


class PerformanceTracker:
    """Track performance metrics against baselines with statistical analysis."""

    def __init__(self):
        self.metrics: Dict[str, PerformanceMetric] = self._load_baselines()
        self.update_mode = False
        self._cache_dirty = False

    def _load_baselines(self) -> Dict[str, PerformanceMetric]:
        """Load baseline performance metrics with backward compatibility."""
        if BASELINE_FILE.exists():
            with open(BASELINE_FILE, "r") as f:
                data = json.load(f)
                metrics = {}
                for name, metric_data in data.items():
                    # Backward compatibility: convert old float format to new PerformanceMetric
                    if isinstance(metric_data, (float, int)):
                        # Old format: just a single baseline value
                        metrics[name] = PerformanceMetric(
                            mean=float(metric_data),
                            median=float(metric_data),
                            std_dev=0.0,
                            min=float(metric_data),
                            max=float(metric_data),
                            samples=[float(metric_data)],
                            last_updated=datetime.now().isoformat(),
                        )
                    else:
                        # New format: PerformanceMetric dict
                        metrics[name] = PerformanceMetric(**metric_data)
                return metrics
        return {}

    def _save_baselines(self):
        """Save baseline performance metrics."""
        if not self._cache_dirty:
            return

        with open(BASELINE_FILE, "w") as f:
            data = {name: asdict(metric) for name, metric in self.metrics.items()}
            json.dump(data, f, indent=2)
        self._cache_dirty = False

    def track(self, test_name: str, duration: float, tolerance_multiplier: float = 1.0):
        """Track performance metric with statistical analysis.

        Args:
            test_name: Name of the test
            duration: Measured duration in seconds
            tolerance_multiplier: Multiplier for thresholds (use >1 for naturally variable tests)
        """
        # Get or create metric
        if test_name not in self.metrics:
            # First run - establish baseline
            self.metrics[test_name] = PerformanceMetric(
                mean=duration,
                median=duration,
                std_dev=0.0,
                min=duration,
                max=duration,
                samples=[duration],
                last_updated=datetime.now().isoformat(),
            )
            self._cache_dirty = True
            pytest.skip(f"Established baseline for {test_name}: {duration:.4f}s")

        metric = self.metrics[test_name]

        if self.update_mode:
            # Update baseline with new sample
            metric.add_sample(duration)
            self._cache_dirty = True
            return

        # Check for regression using statistical analysis
        threshold_warn = THRESHOLD_WARNING * tolerance_multiplier
        threshold_fail = THRESHOLD_FAIL * tolerance_multiplier

        # Use median for robust comparison
        baseline = metric.median
        change_pct = ((duration - baseline) / baseline) * 100

        # Also check if current value is beyond acceptable variance
        # (using standard deviation)
        z_score = (duration - metric.mean) / metric.std_dev if metric.std_dev > 0 else 0

        if change_pct > threshold_fail or z_score > 3:  # 3 sigma rule
            pytest.fail(
                f"Performance regression detected! {test_name} is {change_pct:.1f}% slower "
                f"(median baseline: {baseline:.4f}s, current: {duration:.4f}s, z-score: {z_score:.2f})"
            )
        elif change_pct > threshold_warn or z_score > 2:
            import warnings

            warnings.warn(
                f"Performance warning: {test_name} is {change_pct:.1f}% slower "
                f"(median baseline: {baseline:.4f}s, current: {duration:.4f}s, z-score: {z_score:.2f})",
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
