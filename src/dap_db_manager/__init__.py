"""DAP DB Manager.

A Python application for managing Rockbox database files with a wxPython GUI
and command-line interface. Supports reading audio file tags and generating
database files for Rockbox firmware.

Main modules:
    cli: Command-line interface (ddm command)
    database: Database generation and management
    gui: wxPython GUI application
    tagging: Audio file tag reading and titleformat parsing

Core modules:
    config: Configuration management
    constants: Constants and definitions
    indexfile: Index file handling
    utils: Utility functions
"""

try:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:
        # Python < 3.8
        from importlib_metadata import version, PackageNotFoundError  # type: ignore

    __version__ = version("dap-db-manager")
except (PackageNotFoundError, ImportError):
    # Package not installed or importlib.metadata unavailable
    # Read directly from pyproject.toml
    try:
        from pathlib import Path
        import tomllib  # Python 3.11+ built-in

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
            __version__ = pyproject_data["project"]["version"]
    except Exception:
        # Last resort fallback if pyproject.toml can't be read
        __version__ = "unknown"

__all__ = [
    # Sub-packages
    "cli",
    "database",
    "gui",
    "tagging",
    # Core modules
    "config",
    "constants",
    "indexfile",
    "utils",
]
