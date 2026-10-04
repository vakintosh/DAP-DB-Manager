"""Tests for 300-byte waveform peaks binary writer and validator."""

from pathlib import Path
import pytest

from dap_db_manager.peaks.writer import (
    HEADER_STRUCT,
    PEAKS_FILE_SIZE,
    PEAKS_HEADER_SIZE,
    PEAKS_MAGIC,
    PEAKS_NUM_BUCKETS,
    PEAKS_VERSION,
    deserialize_peaks,
    serialize_peaks,
    write_peaks_file,
)


def test_constants() -> None:
    assert PEAKS_MAGIC == b"PEAK"
    assert PEAKS_VERSION == 1
    assert PEAKS_NUM_BUCKETS == 288
    assert PEAKS_HEADER_SIZE == 12
    assert PEAKS_FILE_SIZE == 300
    assert HEADER_STRUCT.size == 12


def test_serialize_and_deserialize_roundtrip() -> None:
    duration_ms = 345678
    peaks = [i % 256 for i in range(PEAKS_NUM_BUCKETS)]

    serialized = serialize_peaks(duration_ms, peaks)
    assert len(serialized) == PEAKS_FILE_SIZE
    assert serialized[:4] == PEAKS_MAGIC

    unpacked_duration, unpacked_peaks = deserialize_peaks(serialized)
    assert unpacked_duration == duration_ms
    assert unpacked_peaks == peaks


def test_serialize_with_bytes_input() -> None:
    duration_ms = 120000
    payload = bytes(range(PEAKS_NUM_BUCKETS % 256)) + bytes(
        PEAKS_NUM_BUCKETS - (PEAKS_NUM_BUCKETS % 256)
    )
    assert len(payload) == PEAKS_NUM_BUCKETS

    serialized = serialize_peaks(duration_ms, payload)
    assert len(serialized) == PEAKS_FILE_SIZE

    unpacked_duration, unpacked_peaks = deserialize_peaks(serialized)
    assert unpacked_duration == duration_ms
    assert unpacked_peaks == list(payload)


def test_serialize_clamps_peak_values() -> None:
    duration_ms = 50000
    peaks = [-10, 0, 128, 255, 300, 1000] + [50] * (PEAKS_NUM_BUCKETS - 6)
    serialized = serialize_peaks(duration_ms, peaks)

    _, unpacked_peaks = deserialize_peaks(serialized)
    assert unpacked_peaks[0] == 0
    assert unpacked_peaks[1] == 0
    assert unpacked_peaks[2] == 128
    assert unpacked_peaks[3] == 255
    assert unpacked_peaks[4] == 255
    assert unpacked_peaks[5] == 255
    assert unpacked_peaks[6:] == [50] * (PEAKS_NUM_BUCKETS - 6)


def test_serialize_invalid_bucket_count() -> None:
    with pytest.raises(ValueError, match="Expected 288 peak buckets"):
        _ = serialize_peaks(1000, [0] * 287)

    with pytest.raises(ValueError, match="Expected 288 peak buckets"):
        _ = serialize_peaks(1000, [0] * 289)

    with pytest.raises(ValueError, match="Expected 288 peak buckets"):
        _ = serialize_peaks(1000, b"")


def test_deserialize_invalid_length() -> None:
    with pytest.raises(ValueError, match="Invalid peaks data length"):
        _ = deserialize_peaks(b"")

    with pytest.raises(ValueError, match="Invalid peaks data length"):
        _ = deserialize_peaks(b"PEAK" + b"\x00" * 200)

    with pytest.raises(ValueError, match="Invalid peaks data length"):
        _ = deserialize_peaks(b"\x00" * 301)


def test_deserialize_invalid_magic() -> None:
    bad_header = HEADER_STRUCT.pack(b"XEAK", PEAKS_VERSION, PEAKS_NUM_BUCKETS, 1000)
    data = bad_header + bytes(PEAKS_NUM_BUCKETS)
    assert len(data) == PEAKS_FILE_SIZE

    with pytest.raises(ValueError, match="Invalid magic"):
        _ = deserialize_peaks(data)


def test_deserialize_invalid_version() -> None:
    bad_header = HEADER_STRUCT.pack(PEAKS_MAGIC, 2, PEAKS_NUM_BUCKETS, 1000)
    data = bad_header + bytes(PEAKS_NUM_BUCKETS)

    with pytest.raises(ValueError, match="Unsupported version"):
        _ = deserialize_peaks(data)


def test_deserialize_invalid_bucket_count_in_header() -> None:
    bad_header = HEADER_STRUCT.pack(PEAKS_MAGIC, PEAKS_VERSION, 100, 1000)
    data = bad_header + bytes(PEAKS_NUM_BUCKETS)

    with pytest.raises(ValueError, match="Invalid bucket count"):
        _ = deserialize_peaks(data)


def test_write_peaks_file_atomic(tmp_path: Path) -> None:
    target_dir = tmp_path / "sub" / "nested"
    target_file = target_dir / "test_track.peaks"
    duration_ms = 60000
    peaks = [42] * PEAKS_NUM_BUCKETS

    # Ensure parent doesn't exist initially
    assert not target_dir.exists()

    write_peaks_file(target_file, duration_ms, peaks)

    assert target_file.exists()
    assert not target_file.with_suffix(".tmp").exists()

    raw = target_file.read_bytes()
    assert len(raw) == PEAKS_FILE_SIZE

    unpacked_duration, unpacked_peaks = deserialize_peaks(raw)
    assert unpacked_duration == duration_ms
    assert unpacked_peaks == peaks


def test_write_peaks_file_str_path(tmp_path: Path) -> None:
    target_file = tmp_path / "str_test.peaks"
    duration_ms = 12345
    peaks = bytes([10] * PEAKS_NUM_BUCKETS)

    write_peaks_file(str(target_file), duration_ms, peaks)

    assert target_file.exists()
    unpacked_duration, unpacked_peaks = deserialize_peaks(target_file.read_bytes())
    assert unpacked_duration == duration_ms
    assert unpacked_peaks == [10] * PEAKS_NUM_BUCKETS
