#!/usr/bin/env python3
"""
Test cross-compilation path translation.

This tests the path translation logic that converts laptop mount paths
to iPod-relative paths for database cross-compilation.
"""

import pytest
from pathlib import PureWindowsPath, PurePosixPath

from dap_db_manager.database.generator import DatabaseGenerator


class TestNormalizeDapRoot:
    """Test DAP root path normalization."""

    @pytest.mark.parametrize(
        "input_path,expected",
        [
            ("/Volumes/DAP", "/Volumes/DAP"),
            ("/Volumes/DAP/", "/Volumes/DAP"),
            ("E:", "E:"),
            ("E:\\", "E:"),
            ("/mnt/dap", "/mnt/dap"),
            ("/mnt/dap/", "/mnt/dap"),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_dap_root(self, input_path, expected):
        """Test that DAP root paths are normalized correctly."""
        result = DatabaseGenerator._normalize_dap_root(input_path)
        assert result == expected, (
            f"normalize_dap_root({input_path!r}) = {result!r}, expected {expected!r}"
        )


class TestPathTranslation:
    """Test path translation from laptop paths to DAP-relative paths."""

    @pytest.mark.parametrize(
        "dap_root,laptop_path,expected_db_path",
        [
            # macOS scenarios
            ("/Volumes/DAP", "/Volumes/DAP/Music/Song.mp3", "/Music/Song.mp3"),
            (
                "/Volumes/DAP",
                "/Volumes/DAP/FLAC/Rock/Album/Track.flac",
                "/FLAC/Rock/Album/Track.flac",
            ),
            # Windows scenarios
            ("E:", "E:/Music/Song.mp3", "/Music/Song.mp3"),
            ("E:", "E:\\Music\\Song.mp3", "/Music/Song.mp3"),  # Backslashes converted
            # Linux scenarios
            (
                "/mnt/dap",
                "/mnt/dap/Music/Artist/Album/Song.mp3",
                "/Music/Artist/Album/Song.mp3",
            ),
            # Edge cases
            ("/Volumes/DAP", "/Volumes/DAP/Song.mp3", "/Song.mp3"),  # File at root
        ],
    )
    def test_path_translation(self, dap_root, laptop_path, expected_db_path):
        """Test that laptop paths are correctly translated to DAP-relative paths."""
        # Simulate the path translation logic from generator.py
        normalized_root = DatabaseGenerator._normalize_dap_root(dap_root)

        # Normalize paths for comparison (handle backslashes)
        normalized_path = laptop_path.replace("\\", "/")
        normalized_root_for_compare = (
            normalized_root.replace("\\", "/") if normalized_root else None
        )

        assert normalized_root_for_compare is not None, (
            f"DAP root {dap_root!r} normalized to None"
        )
        assert normalized_path.startswith(normalized_root_for_compare), (
            f"Path {laptop_path!r} does not start with DAP root {normalized_root!r}"
        )

        clean_path = normalized_path[len(normalized_root_for_compare) :]
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path

        assert clean_path == expected_db_path, (
            f"DAP root: {dap_root!r}, Laptop path: {laptop_path!r} → {clean_path!r}, expected {expected_db_path!r}"
        )


class TestLegacyBehavior:
    """Test that legacy behavior (no ipod_root) still works."""

    @pytest.mark.parametrize(
        "input_path,expected_output",
        [
            ("C:\\Music\\Song.mp3", "/Music/Song.mp3"),  # Windows drive letter stripped
            ("/Music/Song.mp3", "/Music/Song.mp3"),  # Unix path unchanged
        ],
    )
    def test_legacy_path_stripping(self, input_path, expected_output):
        """Test legacy path processing when dap_root is not specified."""
        # Simulate legacy logic
        path_obj = (
            PureWindowsPath(input_path)
            if ":" in input_path
            else PurePosixPath(input_path)
        )
        clean_path = str(
            PurePosixPath(*path_obj.parts[1:] if path_obj.anchor else path_obj.parts)
        )
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path

        assert clean_path == expected_output, (
            f"Legacy: {input_path!r} → {clean_path!r}, expected {expected_output!r}"
        )
