# pyright: reportAny=false
"""Unit tests for batch waveform peaks manager and CLI commands."""

import argparse
import os
from pathlib import Path
import struct
import time
from unittest.mock import patch
import wave

import pytest

from dap_db_manager.cli import main, parse_args
from dap_db_manager.cli.commands.generate import cmd_generate
from dap_db_manager.cli.commands.peaks import cmd_peaks
from dap_db_manager.cli.commands.update import cmd_update
from dap_db_manager.peaks.hasher import peaks_filename_for_path
from dap_db_manager.peaks.manager import (
    AUDIO_EXTENSIONS,
    generate_peaks_for_library,
    process_single_track,
    resolve_peaks_dir,
)
from dap_db_manager.peaks.writer import (
    PEAKS_NUM_BUCKETS,
    deserialize_peaks,
    write_peaks_file,
)


def _create_wav(path: Path, duration_s: float = 0.1, sample_val: int = 5000) -> None:
    """Create a minimal valid PCM WAV file for testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        n_samples = int(8000 * duration_s)
        data = struct.pack(f"<{n_samples}h", *([sample_val] * n_samples))
        w.writeframes(data)


def test_supported_audio_extensions() -> None:
    expected = {".mp3", ".flac", ".m4a", ".aac", ".alac", ".wav", ".ogg", ".opus"}
    assert AUDIO_EXTENSIONS == expected


def test_resolve_peaks_dir(tmp_path: Path) -> None:
    # 1. Target directory is named .rockbox
    rockbox_dir = tmp_path / ".rockbox"
    assert resolve_peaks_dir(rockbox_dir) == rockbox_dir / "soulectionpod" / "peaks"

    # 2. Target directory is a child of .rockbox
    db_dir = rockbox_dir / "database"
    assert resolve_peaks_dir(db_dir) == rockbox_dir / "soulectionpod" / "peaks"

    # 3. Target directory has a .rockbox child directory
    music_root = tmp_path / "dap_root"
    (music_root / ".rockbox").mkdir(parents=True, exist_ok=True)
    assert (
        resolve_peaks_dir(music_root)
        == music_root / ".rockbox" / "soulectionpod" / "peaks"
    )

    # 4. Target directory is a generic root without existing .rockbox
    plain_dir = tmp_path / "generic"
    assert (
        resolve_peaks_dir(plain_dir)
        == plain_dir / ".rockbox" / "soulectionpod" / "peaks"
    )


def test_process_single_track_generates(tmp_path: Path) -> None:
    audio_path = tmp_path / "track.wav"
    _create_wav(audio_path, duration_s=0.1)

    rel_path = "Artist/Album/track.wav"
    out_dir = tmp_path / "peaks_out"

    result = process_single_track(audio_path, rel_path, out_dir)
    assert result == "generated"

    expected_file = out_dir / peaks_filename_for_path(rel_path)
    assert expected_file.is_file()

    duration_ms, peaks = deserialize_peaks(expected_file.read_bytes())
    assert duration_ms == 100
    assert len(peaks) == PEAKS_NUM_BUCKETS


def test_process_single_track_skips_up_to_date(tmp_path: Path) -> None:
    audio_path = tmp_path / "track.wav"
    _create_wav(audio_path, duration_s=0.1)

    rel_path = "track.wav"
    out_dir = tmp_path / "peaks_out"

    # Initial generation
    res1 = process_single_track(audio_path, rel_path, out_dir)
    assert res1 == "generated"

    expected_file = out_dir / peaks_filename_for_path(rel_path)
    assert expected_file.is_file()

    # Second run without force: should skip
    res2 = process_single_track(audio_path, rel_path, out_dir, force=False)
    assert res2 == "skipped"

    # If audio is touched to make it newer than peaks file
    future_time = time.time() + 10
    os.utime(audio_path, (future_time, future_time))
    res3 = process_single_track(audio_path, rel_path, out_dir, force=False)
    assert res3 == "generated"


def test_process_single_track_force_overwrites(tmp_path: Path) -> None:
    audio_path = tmp_path / "track.wav"
    _create_wav(audio_path, duration_s=0.1)

    rel_path = "track.wav"
    out_dir = tmp_path / "peaks_out"

    res1 = process_single_track(audio_path, rel_path, out_dir)
    assert res1 == "generated"

    # Force re-generation
    res2 = process_single_track(audio_path, rel_path, out_dir, force=True)
    assert res2 == "generated"


def test_process_single_track_error_handling(tmp_path: Path) -> None:
    non_existent = tmp_path / "missing.wav"
    out_dir = tmp_path / "peaks_out"

    result = process_single_track(non_existent, "missing.wav", out_dir)
    assert result == "error"


def test_generate_peaks_for_library_empty(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    out_dir = tmp_path / "peaks"

    total, generated, skipped = generate_peaks_for_library(music_dir, out_dir)
    assert (total, generated, skipped) == (0, 0, 0)


def test_generate_peaks_for_library_with_tracks(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    out_dir = tmp_path / "peaks"

    _create_wav(music_dir / "artist1" / "song1.wav", duration_s=0.1)
    _create_wav(music_dir / "artist2" / "song2.wav", duration_s=0.2)
    # Non-audio file should be ignored
    text_file = music_dir / "notes.txt"
    _ = text_file.write_text("Hello world")

    progress_calls: list[tuple[int, int]] = []

    def on_progress(completed: int, total: int) -> None:
        progress_calls.append((completed, total))

    total, generated, skipped = generate_peaks_for_library(
        music_dir=music_dir,
        output_dir=out_dir,
        jobs=2,
        force=False,
        progress_callback=on_progress,
    )

    assert total == 2
    assert generated == 2
    assert skipped == 0
    assert len(progress_calls) == 2
    assert (2, 2) in progress_calls

    # Verify sidecar files created
    f1 = out_dir / peaks_filename_for_path("music/artist1/song1.wav")
    f2 = out_dir / peaks_filename_for_path("music/artist2/song2.wav")
    assert f1.is_file()
    assert f2.is_file()

    # Re-run without force -> both skipped
    total2, generated2, skipped2 = generate_peaks_for_library(
        music_dir=music_dir,
        output_dir=out_dir,
        jobs=2,
        force=False,
    )
    assert total2 == 2
    assert generated2 == 0
    assert skipped2 == 2

    # Re-run with force -> both generated
    total3, generated3, skipped3 = generate_peaks_for_library(
        music_dir=music_dir,
        output_dir=out_dir,
        jobs=2,
        force=True,
    )
    assert total3 == 2
    assert generated3 == 2
    assert skipped3 == 0


def test_cmd_peaks_generate_cli(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    _create_wav(music_dir / "track.wav", duration_s=0.1)
    out_dir = tmp_path / "peaks_custom"

    args = argparse.Namespace(
        peaks_action="generate",
        music_dir=str(music_dir),
        output=str(out_dir),
        jobs=1,
        force=False,
    )

    exit_code = cmd_peaks(args)
    assert exit_code == 0

    expected = out_dir / peaks_filename_for_path("music/track.wav")
    assert expected.is_file()


def test_cmd_peaks_generate_default_output(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    _create_wav(music_dir / "track.wav", duration_s=0.1)

    args = argparse.Namespace(
        peaks_action="generate",
        music_dir=str(music_dir),
        output=None,
        jobs=1,
        force=False,
    )

    exit_code = cmd_peaks(args)
    assert exit_code == 0

    default_out = music_dir / ".rockbox" / "soulectionpod" / "peaks"
    expected = default_out / peaks_filename_for_path("music/track.wav")
    assert expected.is_file()


def test_cmd_peaks_generate_invalid_dir(tmp_path: Path) -> None:
    args = argparse.Namespace(
        peaks_action="generate",
        music_dir=str(tmp_path / "does_not_exist"),
        output=None,
        jobs=1,
        force=False,
    )
    exit_code = cmd_peaks(args)
    assert exit_code == 1


def test_cmd_peaks_inspect_cli(tmp_path: Path) -> None:
    peaks_path = tmp_path / "test.peaks"
    peaks_data = [i % 256 for i in range(PEAKS_NUM_BUCKETS)]
    write_peaks_file(peaks_path, duration_ms=12345, peaks=peaks_data)

    args = argparse.Namespace(
        peaks_action="inspect",
        peaks_file=str(peaks_path),
    )

    exit_code = cmd_peaks(args)
    assert exit_code == 0


def test_cmd_peaks_inspect_missing_file(tmp_path: Path) -> None:
    args = argparse.Namespace(
        peaks_action="inspect",
        peaks_file=str(tmp_path / "nonexistent.peaks"),
    )
    exit_code = cmd_peaks(args)
    assert exit_code == 1


def test_cmd_peaks_inspect_missing_arg() -> None:
    args = argparse.Namespace(
        peaks_action="inspect",
        peaks_file=None,
        peaks_file_opt=None,
    )
    exit_code = cmd_peaks(args)
    assert exit_code == 1


def test_cmd_peaks_unknown_action() -> None:
    args = argparse.Namespace(
        peaks_action="unknown",
    )
    exit_code = cmd_peaks(args)
    assert exit_code == 1


def test_cli_parser_generate_peaks_flags() -> None:
    # Default should be True
    with patch("sys.argv", ["ddm", "generate", "--music-dir", "music", "-o", "out"]):
        _, args = parse_args()
        assert args.peaks is True

    # Explicit --no-peaks
    with patch(
        "sys.argv",
        ["ddm", "generate", "--music-dir", "music", "-o", "out", "--no-peaks"],
    ):
        _, args = parse_args()
        assert args.peaks is False

    # Explicit --peaks
    with patch(
        "sys.argv",
        ["ddm", "generate", "--music-dir", "music", "-o", "out", "--peaks"],
    ):
        _, args = parse_args()
        assert args.peaks is True


def test_cli_parser_update_peaks_flags() -> None:
    # Default should be True
    with patch("sys.argv", ["ddm", "update", "--db-dir", "db", "--music-dir", "music"]):
        _, args = parse_args()
        assert args.peaks is True

    # Explicit --no-peaks
    with patch(
        "sys.argv",
        ["ddm", "update", "--db-dir", "db", "--music-dir", "music", "--no-peaks"],
    ):
        _, args = parse_args()
        assert args.peaks is False


def test_cli_parser_peaks_subcommands() -> None:
    with patch(
        "sys.argv",
        [
            "ddm",
            "peaks",
            "generate",
            "--music-dir",
            "music",
            "-o",
            "out",
            "--force",
            "-j",
            "4",
        ],
    ):
        _, args = parse_args()
        assert args.command == "peaks"
        assert args.peaks_action == "generate"
        assert args.music_dir == Path("music")
        assert args.output == Path("out")
        assert args.force is True
        assert args.jobs == 4

    with patch(
        "sys.argv",
        ["ddm", "peaks", "inspect", "my_song.peaks"],
    ):
        _, args = parse_args()
        assert args.command == "peaks"
        assert args.peaks_action == "inspect"
        assert args.peaks_file == Path("my_song.peaks")


def test_cli_main_dispatches_peaks(tmp_path: Path) -> None:
    peaks_path = tmp_path / "song.peaks"
    peaks_data = [128] * PEAKS_NUM_BUCKETS
    write_peaks_file(peaks_path, duration_ms=5000, peaks=peaks_data)

    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["ddm", "peaks", "inspect", str(peaks_path)]):
            main()
    assert exc.value.code == 0


def test_cmd_generate_invokes_peaks_when_enabled(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    args = argparse.Namespace(
        music_dir=str(music_dir),
        output=str(out_dir),
        json=False,
        save_tags=False,
        load_tags=False,
        config=None,
        no_parallel=True,
        workers=None,
        no_preserve_stats=True,
        preserve_stats_from=None,
        dap_root=None,
        peaks=True,
    )

    with (
        patch("dap_db_manager.cli.commands.generate.Database") as mock_db,
        patch(
            "dap_db_manager.cli.commands.generate.generate_peaks_for_library"
        ) as mock_gen_peaks,
        patch("dap_db_manager.cli.commands.generate.Config"),
        patch("dap_db_manager.cli.commands.generate.TagCache"),
        pytest.raises(SystemExit),
    ):
        instance = mock_db.return_value
        instance.index.count = 1
        instance.paths = ["song.mp3"]
        instance.failed = []
        instance.tagfiles = {}
        cmd_generate(args)

    assert mock_gen_peaks.called
    call_args = mock_gen_peaks.call_args
    assert call_args.kwargs["music_dir"] == music_dir
    assert (
        call_args.kwargs["output_dir"]
        == out_dir / ".rockbox" / "soulectionpod" / "peaks"
    )


def test_cmd_update_invokes_peaks_when_enabled(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    music_dir = tmp_path / "music"
    music_dir.mkdir()

    args = argparse.Namespace(
        db_dir=str(db_dir),
        music_dir=str(music_dir),
        output=None,
        json=False,
        no_parallel=True,
        workers=None,
        dap_root=None,
        peaks=True,
    )

    with (
        patch("dap_db_manager.cli.commands.update.Database") as mock_db,
        patch(
            "dap_db_manager.cli.commands.update.generate_peaks_for_library"
        ) as mock_gen_peaks,
        pytest.raises(SystemExit),
    ):
        instance = mock_db.read.return_value
        instance.index.count = 1
        instance.paths = ["song.mp3"]
        instance.failed = []
        instance.tagfiles = {}
        instance.update_database.return_value = {
            "added": 0,
            "renamed": 0,
            "modified": 0,
            "deleted": 0,
            "unchanged": 1,
            "failed": 0,
            "final_active": 1,
            "final_deleted": 0,
        }
        cmd_update(args)

    assert mock_gen_peaks.called


def test_dap_root_relative_path_resolution(tmp_path: Path) -> None:
    # Test that dap_root is used for relative paths
    dap_root = tmp_path / "dap"
    music_dir = dap_root / "Music"
    music_dir.mkdir(parents=True)
    _create_wav(music_dir / "track.wav", duration_s=0.1)

    out_dir = tmp_path / "peaks"

    total, generated, skipped = generate_peaks_for_library(
        music_dir=music_dir,
        output_dir=out_dir,
        dap_root=dap_root,
        jobs=1,
    )

    assert total == 1
    assert generated == 1
    assert skipped == 0
    files = list(out_dir.glob("*"))
    assert len(files) == 1
    expected = peaks_filename_for_path("Music/track.wav")
    assert files[0].name == expected


def test_music_dir_name_prepend(tmp_path: Path) -> None:
    # Test that when dap_root is None, and music_dir is "Music", "music/" is prepended
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    _create_wav(music_dir / "track.wav", duration_s=0.1)

    out_dir = tmp_path / "peaks"

    total, generated, skipped = generate_peaks_for_library(
        music_dir=music_dir,
        output_dir=out_dir,
        dap_root=None,
        jobs=1,
    )
    assert total == 1
    assert generated == 1
    assert skipped == 0
    expected = peaks_filename_for_path("music/track.wav")
    files = list(out_dir.glob("*"))
    assert files[0].name == expected
