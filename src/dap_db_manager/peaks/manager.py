"""Batch waveform peaks manager."""

from collections.abc import Callable
import concurrent.futures
import logging
import os
from pathlib import Path

from dap_db_manager.peaks.extractor import extract_peaks
from dap_db_manager.peaks.hasher import peaks_filename_for_path
from dap_db_manager.peaks.writer import write_peaks_file

AUDIO_EXTENSIONS: set[str] = {
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".alac",
    ".wav",
    ".ogg",
    ".opus",
}


def resolve_peaks_dir(target_dir: Path) -> Path:
    """Determine the waveform peaks directory based on whether target_dir is .rockbox or root.

    Args:
        target_dir: Destination or database directory.

    Returns:
        Path to the peaks sidecar directory under soulectionpod/peaks.
    """
    path = Path(target_dir)
    if path.name == ".rockbox":
        return path / "soulectionpod" / "peaks"
    if path.parent.name == ".rockbox":
        return path.parent / "soulectionpod" / "peaks"
    if (path / ".rockbox").is_dir():
        return path / ".rockbox" / "soulectionpod" / "peaks"
    return path / ".rockbox" / "soulectionpod" / "peaks"


def process_single_track(
    audio_path: Path,
    rel_path: str,
    output_dir: Path,
    force: bool = False,
) -> str:
    """Extract and write peaks file for a single audio track.

    Args:
        audio_path: Path to the audio file on disk.
        rel_path: Relative track path string used for hashing.
        output_dir: Destination directory where .peaks file will be saved.
        force: If True, overwrite existing .peaks file even if up to date.

    Returns:
        "skipped" if file already exists and is up to date,
        "generated" if peaks were extracted and written,
        "error" if extraction or writing failed.
    """
    audio_file = Path(audio_path)
    out_dir = Path(output_dir)
    dest = out_dir / peaks_filename_for_path(rel_path)

    if not force and dest.exists():
        try:
            if dest.stat().st_mtime >= audio_file.stat().st_mtime:
                return "skipped"
        except OSError:
            pass

    try:
        duration_ms, peaks = extract_peaks(audio_file)
        write_peaks_file(dest, duration_ms, peaks)
        return "generated"
    except Exception as e:
        logging.error("Failed to generate peaks for %s: %s", audio_file, e)
        return "error"


def generate_peaks_for_library(
    music_dir: Path,
    output_dir: Path,
    dap_root: Path | None = None,
    jobs: int | None = None,
    force: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[int, int, int]:
    """Generate waveform peaks for all audio files in a music directory.

    Args:
        music_dir: Path to the music directory.
        output_dir: Destination directory for .peaks sidecar cache files.
        dap_root: Optional root directory of the DAP for relative path calculation.
        jobs: Number of worker processes (default: os.cpu_count() or 4).
        force: If True, re-generate peaks even if cached files are up to date.
        progress_callback: Optional callback invoked with (completed, total) after each track.

    Returns:
        Tuple of (total_tracks, generated_count, skipped_count).
    """
    music_path = Path(music_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    tracks: list[tuple[Path, str]] = []
    if music_path.is_dir():
        for p in music_path.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                try:
                    if dap_root is not None and p.is_relative_to(dap_root):
                        rel = str(p.relative_to(dap_root))
                    else:
                        rel = str(p.relative_to(music_path))
                except ValueError:
                    rel = p.name

                if not rel.lower().startswith("music/") and music_path.name.lower() == "music":
                    rel = f"music/{rel}"

                tracks.append((p, rel))

    tracks.sort(key=lambda t: t[1])
    total_tracks = len(tracks)
    if total_tracks == 0:
        return 0, 0, 0

    max_workers = jobs or os.cpu_count() or 4
    generated_count = 0
    skipped_count = 0
    completed = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_track, audio_file, rel_path, out_path, force)
            for audio_file, rel_path in tracks
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
            except Exception as e:
                logging.error("Worker error during peak generation: %s", e)
                res = "error"

            if res == "generated":
                generated_count += 1
            elif res == "skipped":
                skipped_count += 1

            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total_tracks)

    return total_tracks, generated_count, skipped_count
