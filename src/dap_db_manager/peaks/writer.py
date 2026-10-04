"""300-byte binary writer and format validator for waveform peaks."""

from collections.abc import Sequence
from pathlib import Path
import struct
from typing import cast

PEAKS_MAGIC: bytes = b"PEAK"
PEAKS_VERSION: int = 1
PEAKS_NUM_BUCKETS: int = 288
PEAKS_HEADER_SIZE: int = 12
PEAKS_FILE_SIZE: int = PEAKS_HEADER_SIZE + PEAKS_NUM_BUCKETS
HEADER_STRUCT: struct.Struct = struct.Struct("<4sHHI")


def serialize_peaks(duration_ms: int, peaks: Sequence[int] | bytes) -> bytes:
    """Serialize waveform peaks and track duration into 300-byte binary format.

    Args:
        duration_ms: Track duration in milliseconds.
        peaks: Exactly 288 peak values (0-255).

    Returns:
        300-byte binary peaks data.

    Raises:
        ValueError: If len(peaks) is not exactly 288.
    """
    if len(peaks) != PEAKS_NUM_BUCKETS:
        raise ValueError(f"Expected {PEAKS_NUM_BUCKETS} peak buckets, got {len(peaks)}")
    header = HEADER_STRUCT.pack(
        PEAKS_MAGIC,
        PEAKS_VERSION,
        PEAKS_NUM_BUCKETS,
        int(duration_ms) & 0xFFFFFFFF,
    )
    payload = bytes(min(255, max(0, int(p))) for p in peaks)
    return header + payload


def deserialize_peaks(data: bytes) -> tuple[int, list[int]]:
    """Deserialize 300-byte binary data into duration_ms and peak list.

    Args:
        data: 300-byte binary peaks data.

    Returns:
        Tuple of (duration_ms, list of 288 peak values).

    Raises:
        ValueError: If data size is not 300 bytes, or if magic, version,
            or bucket count in the header does not match expected values.
    """
    if len(data) != PEAKS_FILE_SIZE:
        raise ValueError(
            f"Invalid peaks data length: expected {PEAKS_FILE_SIZE} bytes, got {len(data)}"
        )
    unpacked = cast(
        tuple[bytes, int, int, int],
        HEADER_STRUCT.unpack(data[:PEAKS_HEADER_SIZE]),
    )
    magic, version, num_buckets, duration_ms = unpacked
    if magic != PEAKS_MAGIC:
        raise ValueError(f"Invalid magic: expected {PEAKS_MAGIC!r}, got {magic!r}")
    if version != PEAKS_VERSION:
        raise ValueError(
            f"Unsupported version: expected {PEAKS_VERSION}, got {version}"
        )
    if num_buckets != PEAKS_NUM_BUCKETS:
        raise ValueError(
            f"Invalid bucket count: expected {PEAKS_NUM_BUCKETS}, got {num_buckets}"
        )
    return duration_ms, list(data[PEAKS_HEADER_SIZE:])


def write_peaks_file(
    file_path: str | Path,
    duration_ms: int,
    peaks: Sequence[int] | bytes,
) -> None:
    """Write peaks binary data atomically to a file.

    Creates parent directories if necessary, writes to a temporary file
    with '.tmp' suffix, and atomically replaces the target file.

    Args:
        file_path: Target destination path for the .peaks file.
        duration_ms: Track duration in milliseconds.
        peaks: Exactly 288 peak values.
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    data = serialize_peaks(duration_ms=duration_ms, peaks=peaks)
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("wb") as f:
        _ = f.write(data)
    _ = temp_path.replace(path)
