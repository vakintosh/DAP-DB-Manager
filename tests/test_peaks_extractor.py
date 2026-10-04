"""Tests for streaming audio peak extractor via ffmpeg."""

import math
from pathlib import Path
import struct
import wave

import pytest

from dap_db_manager.peaks.extractor import (
    BYTES_PER_SAMPLE,
    SAMPLE_RATE,
    extract_peaks,
    extract_peaks_from_pcm,
)
from dap_db_manager.peaks.writer import PEAKS_NUM_BUCKETS


def test_extractor_constants() -> None:
    assert SAMPLE_RATE == 8000
    assert BYTES_PER_SAMPLE == 2


def test_extract_peaks_from_empty_pcm() -> None:
    peaks = extract_peaks_from_pcm(b"", num_buckets=PEAKS_NUM_BUCKETS)
    assert len(peaks) == PEAKS_NUM_BUCKETS
    assert all(p == 0 for p in peaks)


def test_extract_peaks_from_silence() -> None:
    num_samples = PEAKS_NUM_BUCKETS * 4
    pcm = struct.pack(f"<{num_samples}h", *([0] * num_samples))
    peaks = extract_peaks_from_pcm(pcm, num_buckets=PEAKS_NUM_BUCKETS)
    assert len(peaks) == PEAKS_NUM_BUCKETS
    assert all(p == 0 for p in peaks)


def test_extract_peaks_full_scale() -> None:
    # 32767 and -32768 should both reach 255
    pcm = struct.pack("<4h", 32767, -32768, 16384, -16384)
    peaks = extract_peaks_from_pcm(pcm, num_buckets=2)
    assert len(peaks) == 2
    assert peaks[0] == 255
    assert peaks[1] == 127


def test_extract_peaks_partial_scale() -> None:
    # Non-scaled track (max peak >= 180)
    # 25000 / 32767 * 255 = 194.55 -> 194
    # 12500 / 32767 * 255 = 97.27 -> 97
    pcm = struct.pack("<2h", 25000, 12500)
    peaks = extract_peaks_from_pcm(pcm, num_buckets=2)
    assert len(peaks) == 2
    assert peaks[0] == 194
    assert peaks[1] == 97


def test_dynamic_range_scaling_quiet_waveforms() -> None:
    # Max amplitude 10000 -> raw peak: int(10000 * 255 / 32767) = 77 (< 180)
    # Amplitude 5000 -> raw peak: int(5000 * 255 / 32767) = 38
    # Scaling factor = 200.0 / 77
    # Scaled max peak: int(77 * 200.0 / 77) = 200
    # Scaled second peak: int(38 * 200.0 / 77) = 98
    pcm = struct.pack("<2h", 10000, 5000)
    peaks = extract_peaks_from_pcm(pcm, num_buckets=2)
    assert len(peaks) == 2
    assert peaks[0] == 200
    assert peaks[1] == 98


def test_extract_peaks_file_not_found() -> None:
    missing_path = Path("/tmp/non_existent_audio_sample_for_test.mp3")
    with pytest.raises(FileNotFoundError, match="Audio file not found"):
        _ = extract_peaks(missing_path)


def test_extract_peaks_synthetic_wav(tmp_path: Path) -> None:
    wav_path = tmp_path / "sine_8khz.wav"
    sample_rate = 8000
    num_samples = 4000  # 0.5s at 8kHz
    samples = [
        int(20000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        for i in range(num_samples)
    ]
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw_pcm = struct.pack(f"<{num_samples}h", *samples)
        _ = wf.writeframes(raw_pcm)

    # 1. Probed duration (mutagen / sample count fallback)
    duration_ms, peaks = extract_peaks(wav_path)
    assert duration_ms == 500
    assert len(peaks) == PEAKS_NUM_BUCKETS
    assert all(0 <= p <= 255 for p in peaks)
    assert max(peaks) > 100

    # 2. Explicit duration_ms
    explicit_dur, explicit_peaks = extract_peaks(wav_path, duration_ms=1234)
    assert explicit_dur == 1234
    assert explicit_peaks == peaks


def test_extract_peaks_ffmpeg_failure(tmp_path: Path) -> None:
    corrupted_file = tmp_path / "corrupted.mp3"
    _ = corrupted_file.write_bytes(b"NOT_A_VALID_AUDIO_FILE_DATA")

    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        _ = extract_peaks(corrupted_file)


def test_extract_peaks_fewer_samples_than_buckets() -> None:
    # 2 samples into 5 buckets -> samples_per_bucket = max(1, 2//5) = 1
    # Buckets 0, 1 get samples, buckets 2, 3, 4 should get 0
    pcm = struct.pack("<2h", 25000, 20000)
    peaks = extract_peaks_from_pcm(pcm, num_buckets=5)
    assert len(peaks) == 5
    assert peaks[0] == 194
    assert peaks[1] == 155
    assert peaks[2:] == [0, 0, 0]


def test_extract_peaks_mutagen_missing_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wav_path = tmp_path / "fallback.wav"
    sample_rate = 8000
    num_samples = 1600  # 200ms at 8kHz
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        _ = wf.writeframes(struct.pack(f"<{num_samples}h", *([1000] * num_samples)))

    def _mock_file(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("dap_db_manager.peaks.extractor.File", _mock_file)

    dur, peaks = extract_peaks(wav_path)
    assert dur == 200  # 1600 samples / 8000 Hz * 1000 ms
    assert len(peaks) == PEAKS_NUM_BUCKETS
