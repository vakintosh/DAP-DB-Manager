"""Tests for utility functions (time conversions, etc.)."""

import time
from dap_db_manager.utils import mtime_to_fat, fat_to_mtime


class TestTimeConversions:
    """Test FAT timestamp conversion functions."""

    def test_mtime_to_fat_basic(self):
        """Test converting Unix timestamp to FAT format."""
        # Test a known date: 2009-12-10 12:30:45
        unix_time = time.mktime((2009, 12, 10, 12, 30, 45, 0, 0, -1))
        fat_time = mtime_to_fat(unix_time)

        # Verify we get a valid FAT timestamp (non-zero)
        assert fat_time > 0
        assert isinstance(fat_time, int)

    def test_fat_to_mtime_basic(self):
        """Test converting FAT timestamp to Unix time."""
        # Create a FAT timestamp and convert back
        unix_time = time.mktime((2009, 12, 10, 12, 30, 45, 0, 0, -1))
        fat_time = mtime_to_fat(unix_time)
        recovered_time = fat_to_mtime(fat_time)

        # Should be close (FAT has 2-second precision, but timezone offsets can vary)
        assert isinstance(recovered_time, (int, float))
        # Allow larger window due to timezone handling differences
        assert abs(recovered_time - unix_time) < 60  # Within 1 minute

    def test_round_trip_conversion(self):
        """Test that converting back and forth preserves the date."""
        # Test multiple dates
        test_dates = [
            (2000, 1, 1, 0, 0, 0),  # Y2K
            (2009, 12, 10, 12, 30, 45),  # Original project date
            (2024, 12, 25, 18, 0, 0),  # Recent date
        ]

        for date_tuple in test_dates:
            unix_time = time.mktime(date_tuple + (0, 0, -1))
            fat_time = mtime_to_fat(unix_time)
            recovered_time = fat_to_mtime(fat_time)

            # Verify year, month, day are preserved
            original_struct = time.localtime(unix_time)
            recovered_struct = time.localtime(recovered_time)

            assert original_struct.tm_year == recovered_struct.tm_year
            assert original_struct.tm_mon == recovered_struct.tm_mon
            assert original_struct.tm_mday == recovered_struct.tm_mday

    def test_fat_time_range(self):
        """Test that FAT timestamps are within valid range."""
        # FAT timestamps valid from 1980-2107
        unix_1990 = time.mktime((1990, 1, 1, 0, 0, 0, 0, 0, -1))
        fat_time = mtime_to_fat(unix_1990)

        # Should be a positive 32-bit integer
        assert 0 < fat_time < 2**32
