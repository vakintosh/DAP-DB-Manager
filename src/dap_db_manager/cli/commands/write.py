"""Write command - Copy database to new location."""

import argparse
import logging
import sys
from pathlib import Path

from ...database import Database
from ..callbacks import log_callback
from ..utils import ExitCode, json_output
from ..schemas import ErrorResponse, WriteSuccessResponse


def cmd_write(args: argparse.Namespace) -> None:
    """Write database to a new location.

    Args:
        args: Parsed command-line arguments

    Exit Codes:
        0: Success
        10: Invalid input (directory doesn't exist)
        20: Data error (failed to load database)
        32: Database write failed
    """
    db_path = Path(args.db_dir).resolve()
    output_path = Path(args.output).resolve()
    use_json = getattr(args, "json", False)

    # In JSON mode, suppress INFO/DEBUG logs to keep output clean for parsing
    # Only ERROR and above will be shown
    if use_json and logging.getLogger().level < logging.WARNING:
        logging.getLogger().setLevel(logging.WARNING)

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

    logging.info("Loading database from: %s", db_path)

    try:
        # Use log_callback if logging is enabled, otherwise use no-op
        callback = (
            log_callback
            if logging.getLogger().level <= logging.INFO
            else lambda msg, **kwargs: None
        )
        db = Database.read(str(db_path), callback=callback)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="data_error", message=f"Failed to load database: {e}"
                ),
                ExitCode.DATA_ERROR,
            )
        logging.error("Failed to load database: %s", e)
        sys.exit(ExitCode.DATA_ERROR)

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

    logging.info("Writing database to: %s", output_path)

    try:
        # Use log_callback if logging is enabled, otherwise use no-op
        write_callback = (
            log_callback
            if logging.getLogger().level <= logging.INFO
            else lambda msg, **kwargs: None
        )
        db.write(str(output_path), callback=write_callback)
    except Exception as e:
        if use_json:
            json_output(
                ErrorResponse(
                    error="write_failed", message=f"Failed to write database: {e}"
                ),
                ExitCode.WRITE_FAILED,
            )
        logging.error("Failed to write database: %s", e)
        sys.exit(ExitCode.WRITE_FAILED)

    logging.info("✓ Database written successfully")

    if use_json:
        json_output(
            WriteSuccessResponse(
                source=str(db_path),
                destination=str(output_path),
                entries=db.index.count,
            ),
            ExitCode.SUCCESS,
        )

    print("\nDatabase copied:")
    print(f"  From: {db_path}")
    print(f"  To:   {output_path}")
    sys.exit(ExitCode.SUCCESS)
