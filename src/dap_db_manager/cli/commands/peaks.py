"""CLI command for generating and inspecting waveform peaks."""

import argparse
from pathlib import Path
from typing import cast

from rich.console import Console
from rich.table import Table

from dap_db_manager.peaks.manager import generate_peaks_for_library
from dap_db_manager.peaks.writer import deserialize_peaks


def cmd_peaks(args: argparse.Namespace) -> int:
    """Execute waveform peaks subcommands (generate, inspect).

    Args:
        args: Parsed command-line arguments.

    Returns:
        0 on success, non-zero on failure.
    """
    console = Console()
    action = cast(str | None, getattr(args, "peaks_action", None))

    if action == "generate":
        raw_music_dir = cast(str | Path | None, getattr(args, "music_dir", None))
        if raw_music_dir is None:
            console.print("[red]Error:[/red] music_dir is required")
            return 1

        music_dir = Path(raw_music_dir)
        if not music_dir.is_dir():
            console.print(f"[red]Error:[/red] Music directory not found: {music_dir}")
            return 1

        output_arg = cast(str | Path | None, getattr(args, "output", None))
        output_dir = (
            Path(output_arg)
            if output_arg is not None
            else (music_dir / ".rockbox" / "soulectionpod" / "peaks")
        )

        dap_root_arg = cast(str | Path | None, getattr(args, "dap_root", None))
        dap_root = Path(dap_root_arg) if dap_root_arg is not None else None
        jobs = cast(int | None, getattr(args, "jobs", None))
        force = bool(getattr(args, "force", False))

        total, generated, skipped = generate_peaks_for_library(
            music_dir=music_dir,
            output_dir=output_dir,
            dap_root=dap_root,
            jobs=jobs,
            force=force,
        )

        table = Table(title="Waveform Peaks Generation Summary")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Music Directory", str(music_dir))
        table.add_row("Output Directory", str(output_dir))
        table.add_row("Total Audio Tracks", str(total))
        table.add_row("Generated", str(generated))
        table.add_row("Skipped (Up to date)", str(skipped))

        failed = total - generated - skipped
        if failed > 0:
            table.add_row("Failed", str(failed), style="red")

        console.print(table)
        return 0

    if action == "inspect":
        peaks_file_arg = cast(
            str | Path | None,
            getattr(args, "peaks_file", None) or getattr(args, "peaks_file_opt", None),
        )
        if peaks_file_arg is None:
            console.print(
                "[red]Error:[/red] Path to .peaks file is required for inspect"
            )
            return 1

        peaks_file = Path(peaks_file_arg)
        if not peaks_file.is_file():
            console.print(f"[red]Error:[/red] Peaks file not found: {peaks_file}")
            return 1

        try:
            data = peaks_file.read_bytes()
            duration_ms, peaks = deserialize_peaks(data)
        except Exception as e:
            console.print(
                f"[red]Error:[/red] Failed to read peaks file {peaks_file}: {e}"
            )
            return 1

        bucket_count = len(peaks)
        min_val = min(peaks) if peaks else 0
        max_val = max(peaks) if peaks else 0
        avg_val = (sum(peaks) / bucket_count) if bucket_count > 0 else 0.0

        table = Table(title="Waveform Peaks Inspection")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("File", str(peaks_file))
        table.add_row("Duration", f"{duration_ms} ms ({duration_ms / 1000.0:.2f} s)")
        table.add_row("Bucket Count", str(bucket_count))
        table.add_row("Min Peak", str(min_val))
        table.add_row("Max Peak", str(max_val))
        table.add_row("Average Peak", f"{avg_val:.2f}")

        console.print(table)
        return 0

    console.print(
        f"[red]Error:[/red] Subcommand required ('generate' or 'inspect'), got '{action}'"
    )
    return 1
