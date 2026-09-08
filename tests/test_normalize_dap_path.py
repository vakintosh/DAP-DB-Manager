"""Tests for utils.normalize_dap_path.

These characterise the behaviour that was previously duplicated in two places:

- ``DatabaseGenerator._prepare_entry_data`` (generator.py) -- strips ``dap_root``
  and prepends the mount notation when building database entries.
- ``Database.update``'s local ``normalize_scanned_path`` (database/__init__.py)
  -- strips ``dap_root`` to compare scanned paths against database paths.

Both matched ``dap_root`` **case-insensitively**, which matters on macOS and
Windows where the filesystem is case-insensitive but the string casing of a
mount point is not guaranteed to match what the user typed. The helper must
preserve that.
"""

import pytest

from dap_db_manager.utils import normalize_dap_path


class TestStripDapRoot:
    """Stripping the local root, for cross-compilation."""

    def test_strips_dap_root(self):
        assert (
            normalize_dap_path("/Volumes/DAP/Music/Song.mp3", dap_root="/Volumes/DAP")
            == "/Music/Song.mp3"
        )

    def test_dap_root_match_is_case_insensitive(self):
        """macOS/Windows are case-insensitive; the casing of a mount point is not
        guaranteed to match what the user passed."""
        assert (
            normalize_dap_path("/Volumes/dap/Music/Song.mp3", dap_root="/Volumes/DAP")
            == "/Music/Song.mp3"
        )
        assert (
            normalize_dap_path("/VOLUMES/DAP/Music/Song.mp3", dap_root="/volumes/dap")
            == "/Music/Song.mp3"
        )

    def test_preserves_case_of_the_remainder(self):
        """Only the *match* is case-insensitive; the path itself is untouched."""
        assert (
            normalize_dap_path("/Volumes/dap/MuSiC/SoNg.MP3", dap_root="/Volumes/DAP")
            == "/MuSiC/SoNg.MP3"
        )

    def test_trailing_slash_on_dap_root_is_tolerated(self):
        assert (
            normalize_dap_path("/Volumes/DAP/Music/Song.mp3", dap_root="/Volumes/DAP/")
            == "/Music/Song.mp3"
        )

    def test_backslashes_are_normalised(self):
        assert (
            normalize_dap_path(r"E:\Music\Song.mp3", dap_root="E:")
            == "/Music/Song.mp3"
        )

    def test_returns_none_when_path_is_outside_dap_root(self):
        """The generator skips these files and logs a warning."""
        assert normalize_dap_path("/elsewhere/Song.mp3", dap_root="/Volumes/DAP") is None

    def test_result_always_has_a_leading_slash(self):
        assert (
            normalize_dap_path("/Volumes/DAP/Song.mp3", dap_root="/Volumes/DAP")
            == "/Song.mp3"
        )


class TestMountNotation:
    """Prepending the on-device mount notation, e.g. /<HDD0>."""

    def test_prepends_mount_point(self):
        assert (
            normalize_dap_path(
                "/Volumes/DAP/Music/Song.mp3",
                dap_root="/Volumes/DAP",
                mount_point="/<HDD0>",
            )
            == "/<HDD0>/Music/Song.mp3"
        )

    def test_trailing_slash_on_mount_point_is_tolerated(self):
        assert (
            normalize_dap_path(
                "/Volumes/DAP/Music/Song.mp3",
                dap_root="/Volumes/DAP",
                mount_point="/<HDD0>/",
            )
            == "/<HDD0>/Music/Song.mp3"
        )

    def test_mount_point_without_dap_root(self):
        assert (
            normalize_dap_path("/Music/Song.mp3", mount_point="/<HDD0>")
            == "/<HDD0>/Music/Song.mp3"
        )


class TestNoDapRoot:
    """Without dap_root the drive/anchor is dropped, matching the generator."""

    def test_absolute_posix_path_is_returned_rooted(self):
        assert normalize_dap_path("/Music/Song.mp3") == "/Music/Song.mp3"

    def test_windows_drive_letter_is_dropped(self):
        assert normalize_dap_path(r"E:\Music\Song.mp3") == "/Music/Song.mp3"

    def test_relative_path_gains_a_leading_slash(self):
        assert normalize_dap_path("Music/Song.mp3") == "/Music/Song.mp3"


class TestEdgeCases:
    def test_empty_path_returns_none(self):
        assert normalize_dap_path("") is None

    def test_none_path_returns_none(self):
        assert normalize_dap_path(None) is None

    def test_dap_root_equal_to_path_yields_root(self):
        result = normalize_dap_path("/Volumes/DAP", dap_root="/Volumes/DAP")
        assert result == "/"

    def test_empty_dap_root_is_treated_as_absent(self):
        assert normalize_dap_path("/Music/Song.mp3", dap_root="") == "/Music/Song.mp3"
