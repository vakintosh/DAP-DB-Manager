"""Command-line interface for Rockbox Database Manager (rdbm).

This package provides the 'rdbm' command-line tool with various subcommands:
    generate: Generate Rockbox database from music directory
    load: Load and display existing database files
    validate: Validate database file integrity
    inspect: Inspect individual database files

Modules:
    commands/: Command implementations (generate, load, validate, etc.)
    callbacks.py: Common callback functions
    utils.py: CLI utility functions
"""

import argparse
import logging
import sys

from rich_argparse import RichHelpFormatter
from pathlib import Path

from .utils import setup_logging, ExitCode
from .commands import (
    cmd_generate,
    cmd_load,
    cmd_validate,
    cmd_write,
    cmd_inspect,
    cmd_update,
    cmd_detect_mounts,
)
from ..config import Config
from ..database.cache import TagCache

# Import version from parent package (dynamically read from pyproject.toml)
from .. import __version__

__all__ = [
    "main",
    "cmd_generate",
    "cmd_load",
    "cmd_validate",
    "cmd_write",
    "cmd_inspect",
    "cmd_update",
    "cmd_detect_mounts",
    "setup_logging",
]


class RichRawHelpFormatter(RichHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Combines Rich formatting with the ability to keep line breaks (Raw)."""

    pass


def add_global_options(parser_group):
    """Add global options to an argument group."""
    parser_group.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )
    parser_group.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser_group.add_argument(
        "-l",
        "--log-level",
        # choices=["debug", "info", "warning", "error"],
        default=None,
        help="Set logging level (disabled by default)",
    )
    parser_group.add_argument(
        "--cache-size",
        type=int,
        metavar="SIZE",
        help="Override tag cache size (default: from config, typically 50000)",
    )
    parser_group.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format for machine parsing (suppresses progress indicators)",
    )


def parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Create and configure argument parser, then parse command-line arguments.

    Returns:
        tuple: (parser, args) - The ArgumentParser instance and parsed arguments.
    """

    # Main parser
    parser = argparse.ArgumentParser(
        prog="rdbm",
        usage="rdbm <command> [options]",
        description="Rockbox Database Manager - Generate and manage Rockbox database files",
        formatter_class=RichRawHelpFormatter,
        add_help=False,
    )

    # Add global options to main parser
    main_global_group = parser.add_argument_group("Global Options")
    add_global_options(main_global_group)

    # Subcommands
    subparsers = parser.add_subparsers(
        title="Commands",
        dest="command",
        metavar="",
    )

    # ──────────────────────────────
    # generate
    # ──────────────────────────────
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate Rockbox database from music folder (supports cross-compilation with --ipod-root)",
        usage="rdbm generate --music-dir <path/to/source/music/dir> --output <path/to/target/database/dir> [options]",
        description="Scan music folder and generate Rockbox database files. Supports cross-compilation with --ipod-root for 180x faster database generation on laptop/server instead of on device.",
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    generate_required = generate_parser.add_argument_group("Required")
    generate_required.add_argument(
        "--music-dir", type=Path, required=True, help="Path to music directory to scan"
    )
    generate_required.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Target directory for database files",
    )
    generate_options = generate_parser.add_argument_group("Options")
    generate_options.add_argument("-c", "--config", help="Path to configuration file")
    generate_options.add_argument(
        "--load-tags",
        type=Path,
        help="Load tags from cache file (speeds up regeneration)",
    )
    generate_options.add_argument(
        "--save-tags",
        type=Path,
        help="Save tags to cache file for future use",
    )
    generate_options.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing (useful for debugging or small datasets)",
    )
    generate_options.add_argument(
        "--workers",
        type=int,
        metavar="N",
        help="Number of worker threads for parallel processing (default: auto-calculated as CPU count + 4, max 32)",
    )
    generate_options.add_argument(
        "--ipod-root",
        type=Path,
        metavar="PATH",
        help=(
            "iPod mount point for cross-compilation. When generating database on a laptop "
            "for an iPod, specify the mount point (e.g., /Volumes/IPOD or E:) to strip from paths. "
            "Example: /Volumes/IPOD/Music/Song.mp3 → /Music/Song.mp3 in database"
        ),
    )
    generate_global = generate_parser.add_argument_group("Global Options")
    add_global_options(generate_global)
    generate_parser.set_defaults(func=cmd_generate)

    # ──────────────────────────────
    # load
    # ──────────────────────────────
    load_parser = subparsers.add_parser(
        "load",
        help="Load and display database information",
        usage="rdbm load --db-dir <path/to/database/dir> [options]",
        description="Read existing Rockbox database and show information",
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    load_required = load_parser.add_argument_group("Required")
    load_required.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Path to database directory",
    )
    load_global = load_parser.add_argument_group("Global Options")
    add_global_options(load_global)
    load_parser.set_defaults(func=cmd_load)

    # ──────────────────────────────
    # validate
    # ──────────────────────────────
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate database integrity",
        usage="rdbm validate --db-dir <path/to/database/dir> [options]",
        description="Check database files for corruption and structural issues",
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    validate_required = validate_parser.add_argument_group("Required")
    validate_required.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Path to database directory to validate",
    )
    validate_options = validate_parser.add_argument_group("Options")
    validate_options.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode for automation - only output errors, no progress indicators",
    )
    validate_global = validate_parser.add_argument_group("Global Options")
    add_global_options(validate_global)
    validate_parser.set_defaults(func=cmd_validate)

    # ──────────────────────────────
    # write
    # ──────────────────────────────
    write_parser = subparsers.add_parser(
        "write",
        help="Copy database to new location",
        usage="rdbm write --db-dir <path/to/source/database/dir> --output <path/to/destination/dir> [options]",
        description="Load database and write to a different location",
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    write_required = write_parser.add_argument_group("Required")
    write_required.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Path to source database directory",
    )
    write_required.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path to destination directory",
    )
    write_global = write_parser.add_argument_group("Global Options")
    add_global_options(write_global)
    write_parser.set_defaults(func=cmd_write)

    # ──────────────────────────────
    # inspect
    # ──────────────────────────────
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect raw database file structure",
        usage="rdbm inspect --db-dir <path/to/database/dir> [--file-number N] [options]",
        description=(
            "Parse and display raw Rockbox database file contents "
            "(low-level inspection)"
        ),
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    inspect_required = inspect_parser.add_argument_group("Required")
    inspect_required.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Path to database directory",
    )
    inspect_options = inspect_parser.add_argument_group("Options")
    inspect_options.add_argument(
        "--file-number",
        type=int,
        help=(
            "Database file number (0-8): "
            "0=artist, 1=album, 2=genre, 3=title, 4=filename, "
            "5=composer, 6=comment, 7=albumartist, 8=grouping. "
            "Omit for index file."
        ),
    )
    inspect_options.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Show only header information, not entries",
    )
    inspect_global = inspect_parser.add_argument_group("Global Options")
    add_global_options(inspect_global)
    # inspect_parser.add_argument(
    #     "-v",
    #     "--verbose",
    #     action="store_true",
    #     help="Show complete raw output",
    # )
    inspect_parser.set_defaults(func=cmd_inspect)

    # ──────────────────────────────
    # update
    # ──────────────────────────────
    update_parser = subparsers.add_parser(
        "update",
        help="Update database with new/deleted/renamed files (supports cross-compilation with --ipod-root)",
        usage="rdbm update --db-dir <path/to/database> --music-dir <path/to/music> [options]",
        description="Incrementally update existing database: scans for new files, detects renamed/moved files to preserve statistics, marks missing files as deleted. Faster than full rebuild. Supports cross-compilation with --ipod-root (180x faster on laptop/server). Similar to Rockbox's 'Update Now' feature.",
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    update_required = update_parser.add_argument_group("Required")
    update_required.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Path to existing database directory",
    )
    update_required.add_argument(
        "--music-dir",
        type=Path,
        required=True,
        help="Path to music directory to scan",
    )
    update_options = update_parser.add_argument_group("Options")
    update_options.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory (default: update database in place)",
    )
    update_options.add_argument(
        "--ipod-root",
        type=Path,
        metavar="PATH",
        help=(
            "iPod mount point for cross-compilation. When updating database on a laptop "
            "for an iPod, specify the mount point (e.g., /Volumes/IPOD or E:) to strip from paths. "
            "Example: /Volumes/IPOD/Music/Song.mp3 → /Music/Song.mp3 in database"
        ),
    )
    update_global = update_parser.add_argument_group("Global Options")
    add_global_options(update_global)
    update_parser.set_defaults(func=cmd_update)

    # ──────────────────────────────
    # detect-mounts
    # ──────────────────────────────
    detect_mounts_parser = subparsers.add_parser(
        "detect-mounts",
        help="Detect Rockbox mount notation from existing database or set manually",
        usage="rdbm detect-mounts --db-dir <path/to/database> [--set-mount <notation>] [options]",
        description=(
            "Analyze an existing Rockbox database to detect internal mount notation "
            "(e.g., /<HDD0>, /<HDD1>, /<MMC0>), or manually set mount notation if no database exists yet. "
            "Mount notation is saved to config and automatically used by generate/update commands. "
            "Run this BEFORE generating your first database to ensure correct path formatting."
        ),
        formatter_class=RichHelpFormatter,
        add_help=False,
    )
    detect_mounts_required = detect_mounts_parser.add_argument_group("Required")
    detect_mounts_required.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Path to existing Rockbox database directory (or .rockbox folder)",
    )
    detect_mounts_options = detect_mounts_parser.add_argument_group("Options")
    detect_mounts_options.add_argument(
        "--set-mount",
        type=str,
        metavar="NOTATION",
        help="Manually set mount notation (e.g., /<HDD0>, /<MMC0>) and save to config",
    )
    detect_mounts_global = detect_mounts_parser.add_argument_group("Global Options")
    add_global_options(detect_mounts_global)
    detect_mounts_parser.set_defaults(func=cmd_detect_mounts)

    # Parse args
    return parser, parser.parse_args()


def main():
    """Main CLI entry point."""
    parser, args = parse_args()
    # Show help if no command is provided
    if not args.command:
        parser.print_help()
        sys.exit(ExitCode.SUCCESS)

    # Logging setup
    if args.log_level:
        setup_logging(args.log_level)
    else:
        setup_logging("critical")

    # Initialize cache configuration from user settings
    config = Config()
    cache_memory = (
        args.cache_size
        if hasattr(args, "cache_size") and args.cache_size
        else config.get_tag_cache_memory()
    )

    try:
        TagCache.set_max_cache_memory(cache_memory)
        logging.debug("Tag cache memory limit set to: %s MB", cache_memory)
    except ValueError as e:
        logging.error("Invalid cache memory limit: %s", e)
        sys.exit(ExitCode.INTERNAL_ERROR)

    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        logging.info("\nOperation cancelled by user")
        sys.exit(ExitCode.CANCELLED)
    except Exception as e:
        logging.error("Error: %s", e, exc_info=args.log_level == "debug")
        sys.exit(ExitCode.INTERNAL_ERROR)


if __name__ == "__main__":
    main()
