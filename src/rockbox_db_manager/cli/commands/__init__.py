"""CLI command implementations.

Each module in this package implements a specific rdbm subcommand:
    generate.py: Generate database from music directory
    load.py: Load and display existing database
    validate.py: Validate database integrity
    write.py: Write database files to disk
    inspect.py: Inspect individual database files
    update.py: Update database with new/deleted files (delta update)
    detect_mounts.py: Detect Rockbox mount notation from existing database
"""

from .generate import cmd_generate
from .load import cmd_load
from .validate import cmd_validate
from .write import cmd_write
from .inspect import cmd_inspect
from .update import cmd_update
from .detect_mounts import cmd_detect_mounts

__all__ = [
    "cmd_generate",
    "cmd_load",
    "cmd_validate",
    "cmd_write",
    "cmd_inspect",
    "cmd_update",
    "cmd_detect_mounts",
]
