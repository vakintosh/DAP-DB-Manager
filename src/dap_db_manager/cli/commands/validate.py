"""Validate command - Check database integrity."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console
from rich.table import Table

from ...database import Database
from ...constants import FILE_TAGS, FILE_TAG_INDICES
from ..utils import ExitCode, json_output
from ..schemas import ErrorResponse, ValidationFailedResponse, ValidationSuccessResponse


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate database integrity.

    Args:
        args: Parsed command-line arguments

    Exit Codes:
        0: Validation passed
        10: Invalid input (directory doesn't exist)
        31: Validation failed (database issues found)
    """
    db_path = Path(args.db_dir).resolve()
    quiet = getattr(args, "quiet", False)
    use_json = getattr(args, "json", False)

    # In JSON mode, suppress INFO/DEBUG logs to keep output clean for parsing
    # Only ERROR and above will be shown
    if use_json and logging.getLogger().level < logging.WARNING:
        logging.getLogger().setLevel(logging.WARNING)

    console = Console(quiet=quiet or use_json)

    if not db_path.exists():
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Database path does not exist: {db_path}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Database path does not exist: %s", db_path)
        sys.exit(ExitCode.INVALID_INPUT)

    if not db_path.is_dir():
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Database path is not a directory: {db_path}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Database path is not a directory: %s", db_path)
        sys.exit(ExitCode.INVALID_INPUT)

    console.print(f"\n[cyan]Validating database:[/cyan] {db_path}\n")

    issues: List[str] = []
    warnings: List[str] = []

    # Check if all required files exist
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        console=console,
    ) as progress:
        check_task = progress.add_task("Checking database files...", total=None)

        required_files = [
            f"database_{FILE_TAG_INDICES[i]}.tcd" for i in range(len(FILE_TAGS))
        ]
        required_files.append("database_idx.tcd")

        missing_files = []
        empty_files = []
        for filename in required_files:
            filepath = db_path / filename
            if not filepath.exists():
                missing_files.append(filename)
            elif filepath.stat().st_size == 0:
                empty_files.append(filename)

        if missing_files:
            issues.append(
                f"Missing {len(missing_files)} required database files: {', '.join(missing_files)}"
            )
            progress.update(check_task, description="[red]✗ Missing database files")
        elif empty_files:
            issues.append(
                f"Found {len(empty_files)} empty database files: {', '.join(empty_files)}"
            )
            progress.update(check_task, description="[red]✗ Empty database files")
        else:
            progress.update(
                check_task, description="[green]✓ All database files present"
            )

    # Try to read the database
    if not missing_files:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}"),
            console=console,
        ) as progress:
            read_task = progress.add_task("Loading database...", total=None)

            try:
                db = Database.read(str(db_path), callback=lambda msg, **kwargs: None)
                progress.update(
                    read_task, description="[green]✓ Database loaded successfully"
                )

                # Validate database structure
                validation_task = progress.add_task(
                    "Validating structure...", total=None
                )

                # Check index entries
                if db.index.count == 0:
                    warnings.append("Database has no entries (empty database)")

                # Check for orphaned references
                orphaned_count = 0
                NULL_INDEX = 4294967295  # -1 in uint32, indicates no value
                for i, entry in enumerate(db.index.entries):
                    # Check if all tag references are valid
                    for field in FILE_TAGS:
                        tag_entry = getattr(entry, field, None)
                        if tag_entry and hasattr(tag_entry, "index"):
                            tag_index = tag_entry.index
                            # Skip NULL_INDEX as it's valid (means no value)
                            if tag_index != NULL_INDEX and tag_index >= len(
                                db.tagfiles[field].entries
                            ):
                                orphaned_count += 1
                                if orphaned_count <= 5:  # Show first 5
                                    issues.append(
                                        f"Entry {i}: Invalid {field} reference (index {tag_index})"
                                    )

                if orphaned_count > 5:
                    issues.append(
                        f"... and {orphaned_count - 5} more orphaned references"
                    )

                if orphaned_count == 0:
                    progress.update(
                        validation_task,
                        description="[green]✓ No orphaned references found",
                    )
                else:
                    progress.update(
                        validation_task,
                        description=f"[red]✗ Found {orphaned_count} orphaned references",
                    )

                # Check for duplicate entries
                paths = [
                    entry.path.data
                    for entry in db.index.entries
                    if hasattr(entry, "path") and hasattr(entry.path, "data")
                ]
                duplicates = len(paths) - len(set(paths))
                if duplicates > 0:
                    warnings.append(f"Found {duplicates} duplicate file paths in index")

            except Exception as e:
                progress.update(read_task, description="[red]✗ Failed to load database")
                issues.append(f"Failed to read database: {str(e)}")

    # Print results
    console.print()

    if issues:
        if use_json:
            json_output(
                ValidationFailedResponse(
                    errors=issues,
                    warnings=warnings if warnings else None,
                    db_path=str(db_path),
                ),
                ExitCode.VALIDATION_FAILED,
            )

        console.print("[red bold]✗ Validation Failed[/red bold]\n")
        console.print("[red]Issues found:[/red]")
        for issue in issues:
            console.print(f"  [red]•[/red] {issue}")

        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]•[/yellow] {warning}")

        console.print()
        sys.exit(ExitCode.VALIDATION_FAILED)
    else:
        # Prepare statistics for JSON output
        tag_stats = {}
        if not missing_files and "db" in locals():
            for field in FILE_TAGS:
                tag_stats[field] = len(db.tagfiles[field].entries)
            tag_stats["index"] = db.index.count

        if use_json:
            json_output(
                ValidationSuccessResponse(
                    db_path=str(db_path),
                    entries=tag_stats.get("index", 0),
                    warnings=warnings if warnings else None,
                    tag_counts=tag_stats if tag_stats else None,
                ),
                ExitCode.SUCCESS,
            )

        console.print("[green bold]✓ Validation Passed[/green bold]\n")

        if warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]•[/yellow] {warning}")

    # Print statistics if database loaded successfully
    if not missing_files and "db" in locals():
        console.print()
        table = Table(title="Database Statistics")
        table.add_column("Tag File", style="cyan")
        table.add_column("Entries", justify="right", style="magenta")

        for field in FILE_TAGS:
            count = len(db.tagfiles[field].entries)
            table.add_row(field, str(count))

        table.add_row("[bold]index[/bold]", f"[bold]{db.index.count}[/bold]")
        console.print(table)

    console.print()
    sys.exit(ExitCode.SUCCESS)
