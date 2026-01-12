"""Detect-mounts command - Detect Rockbox mount notation from existing database."""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ...database.mount_detector import MountDetector
from ...config import Config, get_config_path
from ..utils import ExitCode, json_output
from ..schemas import ErrorResponse


def cmd_detect_mounts(args: argparse.Namespace) -> None:
    """Detect mount notation from existing Rockbox database.

    Args:
        args: Parsed command-line arguments

    Exit Codes:
        0: Success
        10: Invalid input (directory doesn't exist)
        20: Data error (failed to read database)
    """
    db_path = Path(args.db_dir).resolve()
    use_json = getattr(args, "json", False)

    # In JSON mode, suppress INFO/DEBUG logs
    if use_json and logging.getLogger().level < logging.WARNING:
        logging.getLogger().setLevel(logging.WARNING)

    # Handle manual mount specification
    if hasattr(args, "set_mount") and args.set_mount:
        mount_notation = args.set_mount.strip()
        if not mount_notation.startswith("/"):
            mount_notation = "/" + mount_notation

        config = Config()
        config.set_mount_notation(mount_notation)
        config.save()

        if use_json:
            json_output(
                {
                    "status": "success",
                    "action": "manual_set",
                    "mount_notation": mount_notation,
                    "config_path": str(get_config_path()),
                },
                ExitCode.SUCCESS,
            )
        else:
            console = Console()
            console.print(
                f"\n[green]✓[/green] Manually set mount notation: [cyan]{mount_notation}[/cyan]"
            )
            console.print(f"[dim]  Saved to config: {get_config_path()}[/dim]\n")

        sys.exit(ExitCode.SUCCESS)

    # Validate database directory
    if not db_path.exists():
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Database directory does not exist: {db_path}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Database directory does not exist: %s", db_path)
        sys.exit(ExitCode.INVALID_INPUT)

    if not db_path.is_dir():
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Path is not a directory: {db_path}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Path is not a directory: %s", db_path)
        sys.exit(ExitCode.INVALID_INPUT)

    # Detect mounts
    try:
        mounts = MountDetector.detect_mounts(str(db_path))

        # Save primary mount to config if mounts were detected
        if mounts:
            config = Config()
            primary = max(mounts.values(), key=lambda m: m.count)
            config.set_mount_notation(primary.notation)
            config.save()
            logging.info("Saved primary mount notation to config: %s", primary.notation)
    except FileNotFoundError as e:
        # Try to suggest mount notation based on device hints
        suggested = MountDetector.suggest_mount_notation(str(db_path))

        if use_json:
            json_output(
                {
                    "error": "no_database",
                    "message": str(e),
                    "suggested_mount": suggested,
                    "help": f"Use --set-mount {suggested} to manually set mount notation",
                },
                ExitCode.INVALID_INPUT,
            )
        else:
            console = Console()
            console.print(
                Panel(
                    f"[yellow]No database found in {db_path}[/yellow]\n\n"
                    f"Cannot auto-detect mount notation without an existing database.\n\n"
                    f"[bold]Suggested mount notation:[/bold] [cyan]{suggested}[/cyan]\n\n"
                    f"To manually set mount notation, use:\n"
                    f"  [dim]rdbm detect-mounts --db-dir {db_path} --set-mount {suggested}[/dim]\n\n"
                    f"Common mount notations:\n"
                    f"  • [cyan]/<HDD0>[/cyan] - Most iPods, hard drive devices\n"
                    f"  • [cyan]/<MMC0>[/cyan] - SD card devices (Sansa, Clip, Fuze)\n"
                    f"  • [cyan]/<HDD1>[/cyan] - Secondary storage (if multi-volume)",
                    title="Database Not Found",
                    border_style="yellow",
                )
            )
        sys.exit(ExitCode.INVALID_INPUT)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="data_error", message=f"Failed to detect mounts: {e}"
                ),
                ExitCode.DATA_ERROR,
            )
        logging.error("Failed to detect mounts: %s", e)
        sys.exit(ExitCode.DATA_ERROR)

    # Output results
    if use_json:
        # JSON output
        mount_data = {}
        for notation, info in mounts.items():
            mount_data[notation] = {
                "count": info.count,
                "samples": info.sample_paths[:5],
            }

        json_output(
            {
                "status": "success",
                "db_path": str(db_path),
                "mount_count": len(mounts),
                "mounts": mount_data,
                "primary_mount": max(mounts.values(), key=lambda m: m.count).notation
                if mounts
                else None,
            },
            ExitCode.SUCCESS,
        )
    else:
        # Rich console output
        console = Console()

        if not mounts:
            console.print(
                Panel(
                    "[yellow]No Rockbox mount notation detected in database.[/yellow]\n\n"
                    "Paths appear to use simple format (e.g., [cyan]/Music/...[/cyan])\n\n"
                    "This may indicate:\n"
                    "  • Database was generated without mount notation\n"
                    "  • Database is for a device that doesn't use mount prefixes\n"
                    "  • Database is empty or corrupted",
                    title="Mount Detection Results",
                    border_style="yellow",
                )
            )
            sys.exit(ExitCode.SUCCESS)

        # Create table
        table = Table(
            title="Detected Mount Points", show_header=True, header_style="bold magenta"
        )
        table.add_column("Mount Notation", style="cyan", no_wrap=True)
        table.add_column("File Count", justify="right", style="green")
        table.add_column("Sample Paths", style="dim")

        # Sort by count (descending)
        sorted_mounts = sorted(mounts.values(), key=lambda m: m.count, reverse=True)

        for mount_info in sorted_mounts:
            # Format sample paths (show first 3)
            samples = "\n".join(mount_info.sample_paths[:3])
            table.add_row(mount_info.notation, str(mount_info.count), samples)

        console.print()
        console.print(table)
        console.print()

        # Show primary mount
        primary = sorted_mounts[0]
        console.print(
            f"[bold green]✓[/bold green] Primary mount: [cyan]{primary.notation}[/cyan] "
            f"({primary.count} files)"
        )
        console.print(f"[dim]  Saved to config: {get_config_path()}[/dim]")

        # Warning for multiple mounts
        if len(mounts) > 1:
            console.print()
            console.print(
                Panel(
                    "[yellow]⚠ Multiple mount points detected![/yellow]\n\n"
                    f"This device has [bold]{len(mounts)}[/bold] mount points, "
                    "which typically indicates:\n"
                    "  • Internal storage + SD card\n"
                    "  • Multiple storage partitions\n\n"
                    "When generating/updating the database, ensure files are mapped "
                    "to the correct mount point based on their physical location.",
                    border_style="yellow",
                )
            )

        console.print()

    sys.exit(ExitCode.SUCCESS)
