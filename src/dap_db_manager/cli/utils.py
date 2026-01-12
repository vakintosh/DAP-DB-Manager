"""Utility functions for CLI operations."""

import json
import logging
import sys
from enum import IntEnum
from typing import Union

from pydantic import BaseModel


class ExitCode(IntEnum):
    """Exit codes for CLI commands.

    These codes allow automated systems to understand command results
    without parsing logs.
    """

    # Success
    SUCCESS = 0

    # Input errors (10-19)
    INVALID_INPUT = 10  # Missing directories, bad arguments
    INVALID_CONFIG = 11  # Configuration file errors

    # Data errors (20-29)
    DATA_ERROR = 20  # Corrupt audio files, unreadable tags
    MISSING_TAGS = 21  # Required metadata missing

    # Operation errors (30-39)
    GENERATION_FAILED = 30  # Database generation failure
    VALIDATION_FAILED = 31  # Database validation failure
    WRITE_FAILED = 32  # Database write failure

    # Internal errors (40-49)
    INTERNAL_ERROR = 40  # Unexpected bugs
    CANCELLED = 41  # Operation cancelled by user (Ctrl+C)


def setup_logging(level: str) -> None:
    """Configure logging based on user-specified level.

    Args:
        level: Logging level (debug, info, warning, error, critical)
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def json_output(data: Union[BaseModel, dict], exit_code: int = 0) -> None:
    """Output JSON to stdout and exit with specified code.

    Args:
        data: Pydantic model or dictionary to output as JSON
        exit_code: Exit code to use (default: 0)
    """
    if isinstance(data, BaseModel):
        # Use Pydantic's model_dump with exclude_none to omit None values
        json_str = data.model_dump_json(indent=2, exclude_none=True)
        print(json_str)
    else:
        # Fallback for plain dicts (backwards compatibility)
        print(json.dumps(data, indent=2))
    sys.exit(exit_code)
