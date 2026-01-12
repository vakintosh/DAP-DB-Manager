"""Main frame sub-package for the DAP DB Manager.

This package splits the large MyFrame class into focused, manageable modules:
- frame: Main MyFrame class with initialization
- format_manager: Format string loading, saving, and templates
- database_operations: Database operation handlers
- thread_handlers: Thread event handlers
- threading_support: Thread coordination utilities
"""

from .frame import MyFrame

__all__ = ["MyFrame"]
