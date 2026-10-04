"""Waveform peaks generation and caching package."""

from dap_db_manager.peaks.extractor import extract_peaks, extract_peaks_from_pcm
from dap_db_manager.peaks.hasher import (
    fnv1a_64,
    hash_track_path,
    normalize_path,
    peaks_filename_for_path,
)
from dap_db_manager.peaks.manager import (
    AUDIO_EXTENSIONS,
    generate_peaks_for_library,
    process_single_track,
    resolve_peaks_dir,
)
from dap_db_manager.peaks.writer import (
    PEAKS_FILE_SIZE,
    PEAKS_HEADER_SIZE,
    PEAKS_MAGIC,
    PEAKS_NUM_BUCKETS,
    PEAKS_VERSION,
    deserialize_peaks,
    serialize_peaks,
    write_peaks_file,
)

__all__ = [
    "AUDIO_EXTENSIONS",
    "PEAKS_FILE_SIZE",
    "PEAKS_HEADER_SIZE",
    "PEAKS_MAGIC",
    "PEAKS_NUM_BUCKETS",
    "PEAKS_VERSION",
    "deserialize_peaks",
    "extract_peaks",
    "extract_peaks_from_pcm",
    "fnv1a_64",
    "generate_peaks_for_library",
    "hash_track_path",
    "normalize_path",
    "peaks_filename_for_path",
    "process_single_track",
    "resolve_peaks_dir",
    "serialize_peaks",
    "write_peaks_file",
]
