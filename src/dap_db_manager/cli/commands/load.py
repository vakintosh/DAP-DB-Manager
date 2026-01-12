"""Load command - Display database information."""

import argparse
import logging
import sys
from pathlib import Path

from ...database import Database
from ..callbacks import log_callback
from ...constants import FILE_TAGS
from ..utils import ExitCode, json_output
from ..schemas import ErrorResponse, LoadSuccessResponse


def cmd_load(args: argparse.Namespace) -> None:
    """Load and display database information.

    Args:
        args: Parsed command-line arguments

    Exit Codes:
        0: Success
        10: Invalid input (directory doesn't exist)
        20: Data error (failed to load database)
    """
    db_path = Path(args.db_dir).resolve()
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

    # Load database
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

    logging.info("✓ Database loaded successfully")

    # JSON output mode
    if use_json:
        tag_counts = {}
        for field in FILE_TAGS:
            tag_counts[field] = len(db.tagfiles[field].entries)

        json_output(
            LoadSuccessResponse(
                db_path=str(db_path), entries=db.index.count, tag_counts=tag_counts
            ),
            ExitCode.SUCCESS,
        )

    # Print database information
    print("\nDatabase Information:")
    print(f"  Location: {db_path}")
    print(f"  Entries:  {db.index.count}")

    # Show tag file counts

    print("\nTag Files:")
    for field in FILE_TAGS:
        count = len(db.tagfiles[field].entries)
        print(f"  {field:12s}: {count:6d} entries")

    # If verbose, show sample entries
    if logging.getLogger().level <= logging.DEBUG:
        print("\nSample Entries (first 10):")
        for i, entry in enumerate(db.index.entries[:10]):
            print(f"  {i + 1}. {entry.path.data}")

    sys.exit(ExitCode.SUCCESS)
