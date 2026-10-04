"""Audio peak extractor streaming raw PCM from ffmpeg."""

from pathlib import Path
import struct
import subprocess

from mutagen._file import File  # pyright: ignore[reportUnknownVariableType]

from dap_db_manager.peaks.writer import PEAKS_NUM_BUCKETS

SAMPLE_RATE: int = 8000  # 8 kHz mono 16-bit signed PCM
BYTES_PER_SAMPLE: int = 2


def extract_peaks_from_pcm(
    pcm_bytes: bytes, num_buckets: int = PEAKS_NUM_BUCKETS
) -> list[int]:
    """Calculate normalized peak amplitudes (0..255) for num_buckets from signed 16-bit PCM bytes.

    Args:
        pcm_bytes: Raw 16-bit signed little-endian PCM audio bytes.
        num_buckets: Number of peak buckets to produce (defaults to PEAKS_NUM_BUCKETS).

    Returns:
        List of normalized peak amplitudes (0-255) of length num_buckets.
    """
    total_samples = len(pcm_bytes) // BYTES_PER_SAMPLE
    if total_samples == 0:
        return [0] * num_buckets

    peaks: list[int] = []

    if total_samples < num_buckets:
        for i in range(num_buckets):
            if i >= total_samples:
                peaks.append(0)
                continue
            chunk = pcm_bytes[i * BYTES_PER_SAMPLE : (i + 1) * BYTES_PER_SAMPLE]
            val = abs(struct.unpack("<h", chunk)[0])
            peaks.append(min(255, int((val * 255) / 32767)))
    else:
        for i in range(num_buckets):
            start_sample = (i * total_samples) // num_buckets
            end_sample = ((i + 1) * total_samples) // num_buckets
            if start_sample >= total_samples or start_sample >= end_sample:
                peaks.append(0)
                continue

            chunk = pcm_bytes[
                start_sample * BYTES_PER_SAMPLE : end_sample * BYTES_PER_SAMPLE
            ]
            num_chunk_samples = len(chunk) // BYTES_PER_SAMPLE
            if num_chunk_samples == 0:
                peaks.append(0)
                continue

            chunk_samples: tuple[int, ...] = struct.unpack(
                f"<{num_chunk_samples}h", chunk
            )
            max_val = max(abs(s) for s in chunk_samples)
            # Quantize 0..32767 to 0..255
            norm_peak = min(255, int((max_val * 255) / 32767))
            peaks.append(norm_peak)

    # Dynamic track normalization: scale so track max peak is at least 200/255 if not dead silent
    max_track_peak = max(peaks) if peaks else 0
    if 0 < max_track_peak < 180:
        scale = 200.0 / max_track_peak
        peaks = [min(255, int(p * scale)) for p in peaks]

    return peaks


def extract_peaks(
    audio_path: str | Path, duration_ms: int | None = None
) -> tuple[int, list[int]]:
    """Decode audio via ffmpeg stream to 8kHz mono PCM and extract 288 peaks.

    Args:
        audio_path: Path to the audio file.
        duration_ms: Optional track duration in milliseconds. If None or <= 0,
            duration is probed via mutagen or inferred from PCM sample count.

    Returns:
        Tuple of (duration_ms, list of 288 peak values).

    Raises:
        FileNotFoundError: If audio_path does not exist or is not a file.
        RuntimeError: If ffmpeg fails to decode the audio file.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    resolved_duration_ms = (
        duration_ms if duration_ms is not None and duration_ms > 0 else 0
    )
    if resolved_duration_ms == 0:
        try:
            audio: object = File(str(path))
            if audio is not None and getattr(audio, "info", None) is not None:
                info: object = getattr(audio, "info", None)
                length: object = getattr(info, "length", 0.0)
                if isinstance(length, (int, float)) and length > 0:
                    resolved_duration_ms = int(length * 1000)
        except Exception:
            resolved_duration_ms = 0

    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-",
    ]

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        stdout, stderr = proc.communicate(timeout=60)
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="ignore") if stderr else ""
            raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err_msg}")

    peaks = extract_peaks_from_pcm(stdout, PEAKS_NUM_BUCKETS)
    if resolved_duration_ms == 0:
        total_samples = len(stdout) // BYTES_PER_SAMPLE
        resolved_duration_ms = int((total_samples * 1000) / SAMPLE_RATE)

    return resolved_duration_ms, peaks
