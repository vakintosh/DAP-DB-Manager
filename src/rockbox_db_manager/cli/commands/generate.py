"""Generate command - Create Rockbox database from music folder."""

import argparse
import logging
import sys
import time
from pathlib import Path

from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.console import Console
from rich.table import Table

from ...database import Database
from ...database.cache import TagCache
from ...config import Config
from ...constants import FILE_TAGS
from ..callbacks import ProgressCallback, log_callback
from ..utils import ExitCode, json_output
from ..schemas import ErrorResponse, GenerateSuccessResponse


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate database from music folder.

    Args:
        args: Parsed command-line arguments

    Exit Codes:
        0: Success
        10: Invalid input (missing/invalid directories)
        11: Invalid configuration file
        20: Data errors (corrupt files, missing tags)
        30: Database generation failed
        32: Database write failed
        41: Operation cancelled (Ctrl+C)
    """
    start_time = time.time()
    use_json = getattr(args, "json", False)

    # In JSON mode, suppress INFO/DEBUG logs to keep output clean for parsing
    # Only ERROR and above will be shown
    if use_json and logging.getLogger().level < logging.WARNING:
        logging.getLogger().setLevel(logging.WARNING)

    music_path = Path(args.music_dir).resolve()

    if not music_path.exists():
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Music path does not exist: {music_path}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Music path does not exist: %s", music_path)
        sys.exit(ExitCode.INVALID_INPUT)

    if not music_path.is_dir():
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Music path is not a directory: {music_path}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Music path is not a directory: %s", music_path)
        sys.exit(ExitCode.INVALID_INPUT)

    logging.info("Generating database from: %s", music_path)

    # Extract iPod root for cross-compilation (if provided)
    ipod_root = None
    if hasattr(args, "ipod_root") and args.ipod_root:
        ipod_root = str(args.ipod_root.resolve())
        logging.info("Using iPod root for path translation: %s", ipod_root)

        # Validate that music_path is under ipod_root
        if not str(music_path).startswith(ipod_root):
            if use_json:
                json_output(
                    ErrorResponse(
                        error="invalid_input",
                        message=f"Music directory ({music_path}) must be under iPod root ({ipod_root})",
                    ),
                    ExitCode.INVALID_INPUT,
                )
            logging.error(
                "Music directory (%s) must be under iPod root (%s)",
                music_path,
                ipod_root,
            )
            sys.exit(ExitCode.INVALID_INPUT)

    # Load configuration
    config = Config()

    # Auto-detect mount notation on first run if not configured
    if not config.is_mount_notation_configured():
        device_path = ipod_root if ipod_root else args.output
        if not use_json:
            logging.info("First run detected - auto-detecting mount notation...")
        config.auto_detect_mount_notation(
            device_path, callback=logging.info if not use_json else None
        )

    # Create database instance
    db = Database(config=config, ipod_root=ipod_root)

    # Log mount notation
    mount_notation = db.config.get_mount_notation()
    if mount_notation:
        logging.info("Using mount notation: %s", mount_notation)
    else:
        logging.info("No mount notation configured (paths will use simple format)")

    # Suppress console output if JSON mode
    console = Console(quiet=use_json)

    # Configure parallelization
    if hasattr(args, "no_parallel") and args.no_parallel:
        db.use_parallel = False
        logging.info("Parallel processing disabled")

    if hasattr(args, "workers") and args.workers:
        db.max_workers = args.workers
        logging.info("Using %s worker threads", args.workers)

    # Load configuration if provided
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            if use_json:
                json_output(
                    ErrorResponse(
                        error="invalid_config",
                        message=f"Config file does not exist: {config_path}",
                    ),
                    ExitCode.INVALID_CONFIG,
                )
            logging.error("Config file does not exist: %s", config_path)
            sys.exit(ExitCode.INVALID_CONFIG)

        logging.info("Loading configuration from: %s", config_path)
        config = Config()
        config.load()

        # Apply format settings from config
        for field in [
            "artist",
            "album",
            "genre",
            "title",
            "composer",
            "comment",
            "albumartist",
            "grouping",
        ]:
            try:
                format_str = config.get_format(field)
                sort_str = config.get_sort_format(field)
                if format_str:
                    db.set_format(field, format_str, sort_str)
                    logging.debug("Set format for %s: %s", field, format_str)
            except KeyError:
                pass

    # Load tags from cache if provided
    if args.load_tags:
        tags_path = Path(args.load_tags)
        # Try with .gz extension if file doesn't exist
        if not tags_path.exists() and not str(tags_path).endswith(".gz"):
            tags_path_gz = Path(str(tags_path) + ".gz")
            if tags_path_gz.exists():
                tags_path = tags_path_gz
                logging.debug("Using compressed cache file: %s", tags_path)

        if not tags_path.exists():
            logging.warning("Tags file does not exist: %s", tags_path)
        else:
            logging.info("Loading tags from: %s", tags_path)
            db.load_tags(str(tags_path), callback=log_callback)
            tag_cache = TagCache.get_cache()
            logging.info("Loaded %s cached tags", len(tag_cache))
    else:
        # Clear any stale cache from previous operations
        TagCache.clear()
        logging.debug("Cleared stale tag cache")

    # Set up callback and progress bar (console already created with quiet=use_json)
    # Always show progress bar with message and timer
    try:
        with Progress(
            TextColumn("[cyan]Scanning music directory..."),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Scanning task - message and timer only
            scan_task = progress.add_task("", total=None)
            callback = ProgressCallback(progress, scan_task)

            parallel_flag = not (hasattr(args, "no_parallel") and args.no_parallel)
            db.add_dir(
                str(music_path),
                dircallback=callback,
                filecallback=callback,
                parallel=parallel_flag,
            )

            progress.update(scan_task, total=callback.count, completed=callback.count)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="data_error",
                    message=f"Failed to scan music directory: {e}",
                ),
                ExitCode.DATA_ERROR,
            )
        logging.error("Failed to scan music directory: %s", e)
        sys.exit(ExitCode.DATA_ERROR)

    total_files = len(db.paths)
    failed_files = len(db.failed)

    if total_files == 0:
        if use_json:
            json_output(
                ErrorResponse(
                    error="data_error",
                    message=f"No music files found in: {music_path}",
                ),
                ExitCode.DATA_ERROR,
            )
        logging.error("No music files found in: %s", music_path)
        sys.exit(ExitCode.DATA_ERROR)

    console.print(
        f"\n[green]✓[/green] Scanned {total_files} files ({failed_files} failed)"
    )

    if failed_files > 0:
        logging.warning("Failed to read %s files:", failed_files)
        for failed in db.failed[:10]:  # Show first 10
            logging.warning("  - %s", failed)
        if failed_files > 10:
            logging.warning("  ... and %s more", failed_files - 10)

    # Save tags to cache if requested
    if args.save_tags:
        tags_path = Path(args.save_tags)
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Saving tags cache..."),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            save_task = progress.add_task("save", total=len(db.paths))

            def save_callback(msg):
                if isinstance(msg, int):
                    # Initial count
                    progress.update(save_task, total=msg)
                elif isinstance(msg, str):
                    # Each file saved
                    progress.advance(save_task, 1)

            actual_path, saved_count = db.save_tags(
                str(tags_path), callback=save_callback
            )
        console.print(
            f"[green]✓[/green] Saved {saved_count} tags to cache: {actual_path}"
        )

    # Generate database
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Generating database entries..."),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            gen_task = progress.add_task("generate", total=total_files)

            def gen_callback(current_count, total_count):
                progress.update(gen_task, completed=current_count)

            parallel_flag = not (hasattr(args, "no_parallel") and args.no_parallel)
            db.generate_database(callback=gen_callback, parallel=parallel_flag)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="generation_failed",
                    message=f"Database generation failed: {e}",
                ),
                ExitCode.GENERATION_FAILED,
            )
        logging.error("Database generation failed: %s", e)
        sys.exit(ExitCode.GENERATION_FAILED)

    console.print(f"[green]✓[/green] Generated {db.index.count} database entries")

    # Write database to output directory
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = music_path / ".rockbox"

    # Validate output directory can be created
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="invalid_input",
                    message=f"Cannot create output directory {output_path}: {e}",
                ),
                ExitCode.INVALID_INPUT,
            )
        logging.error("Cannot create output directory %s: %s", output_path, e)
        sys.exit(ExitCode.INVALID_INPUT)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Writing database files..."),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} files"),
            console=console,
        ) as progress:
            write_task = progress.add_task("write", total=10)  # 9 tag files + 1 index

            def write_callback(msg, **kwargs):
                if "done" in str(msg):
                    progress.advance(write_task, 1)
                elif logging.getLogger().level <= logging.DEBUG:
                    log_callback(msg, **kwargs)

            db.write(str(output_path), callback=write_callback)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="write_failed",
                    message=f"Failed to write database: {e}",
                ),
                ExitCode.WRITE_FAILED,
            )
        logging.error("Failed to write database: %s", e)
        sys.exit(ExitCode.WRITE_FAILED)

    console.print("[green]✓[/green] Database generation complete")

    duration_ms = int((time.time() - start_time) * 1000)

    # JSON output mode
    if use_json:
        # Count entries per tag file
        tag_counts = {}
        for field in FILE_TAGS:
            tag_counts[field] = len(db.tagfiles[field].entries)

        # Exit with appropriate code
        if failed_files > total_files * 0.1:  # More than 10% failed
            json_output(
                GenerateSuccessResponse(
                    status="completed_with_errors",
                    input_dir=str(music_path),
                    output_dir=str(output_path),
                    tracks=db.index.count,
                    files_scanned=total_files,
                    files_failed=failed_files,
                    duration_ms=duration_ms,
                    warning=f"High failure rate: {failed_files}/{total_files} files failed",
                    **tag_counts,  # Unpack tag counts as extra fields
                ),
                ExitCode.DATA_ERROR,
            )

        json_output(
            GenerateSuccessResponse(
                status="success",
                input_dir=str(music_path),
                output_dir=str(output_path),
                tracks=db.index.count,
                files_scanned=total_files,
                files_failed=failed_files,
                duration_ms=duration_ms,
                **tag_counts,  # Unpack tag counts as extra fields
            ),
            ExitCode.SUCCESS,
        )

    # Print summary table (normal mode)
    table = Table(title="\nDatabase Summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Input", str(music_path))
    table.add_row("Output", str(output_path))
    table.add_row("Files", str(total_files))
    table.add_row("Entries", str(db.index.count))
    table.add_row("Failed", str(failed_files))

    # Log failed files if any
    if db.failed:
        logging.warning("Failed to read tags from %s files", len(db.failed))
        if logging.getLogger().level <= logging.DEBUG:
            for failed_file in db.failed[:10]:  # Show first 10
                logging.debug("  Failed: %s", failed_file)

    console.print(table)

    # Exit with appropriate code
    if failed_files > total_files * 0.1:  # More than 10% failed
        logging.warning(
            "High failure rate: %s/%s files failed", failed_files, total_files
        )
        sys.exit(ExitCode.DATA_ERROR)

    sys.exit(ExitCode.SUCCESS)
