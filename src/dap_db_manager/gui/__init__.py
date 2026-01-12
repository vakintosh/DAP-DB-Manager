"""GUI sub-package for DAP DB Manager.

This package provides a modular wxPython GUI implementation with clear
separation of concerns. The original large gui.py file has been refactored
into focused modules:

Modules:
    app.py: Application entry point and main app class
    main_frame/: Main window (further split into sub-modules)
        - frame.py: MyFrame class and initialization
        - format_manager.py: Format string management
        - database_operations.py: Database operation handlers
        - thread_handlers.py: Thread event handlers
        - threading_support.py: Thread coordination utilities
    field_panes.py: Database field browsing panels
    info_panel.py: Progress tracking UI components
    error_handling.py: Error dialogs and validation
    thread_events.py: Custom threading events for wxPython

Note: wxPython is an optional dependency. Install with: pip install dap-db-manager[gui]
"""

# Check if wxPython is available
import importlib.util

_WXPYTHON_AVAILABLE = importlib.util.find_spec("wx") is not None


def is_wxpython_available() -> bool:
    """Check if wxPython is available.

    Returns:
        True if wxPython can be imported, False otherwise.
    """
    return _WXPYTHON_AVAILABLE


# Only import GUI components if wxPython is available
if _WXPYTHON_AVAILABLE:
    from .app import MyApp, main
    from .main_frame import MyFrame
    from .field_panes import FieldPane, FieldPanePanel
    from .error_handling import (
        show_error_dialog,
        show_warning_dialog,
        validate_path,
        validate_format_string,
    )
    from .thread_events import (
        ThreadEvent,
        EVT_THREAD_START,
        EVT_THREAD_CALLBACK,
        EVT_THREAD_END,
    )
    from .info_panel import InfoPanel, Info
    from .async_operations import (
        AsyncIOSupport,
        AsyncDatabaseOperations,
        create_progress_callback,
    )
    from .cancellable_progress import CancellableProgressDialog, NonModalProgressDialog

    __all__ = [
        "MyApp",
        "main",
        "MyFrame",
        "FieldPane",
        "FieldPanePanel",
        "show_error_dialog",
        "show_warning_dialog",
        "validate_path",
        "validate_format_string",
        "ThreadEvent",
        "EVT_THREAD_START",
        "EVT_THREAD_CALLBACK",
        "EVT_THREAD_END",
        "InfoPanel",
        "Info",
        "AsyncIOSupport",
        "AsyncDatabaseOperations",
        "create_progress_callback",
        "CancellableProgressDialog",
        "NonModalProgressDialog",
        "is_wxpython_available",
    ]
else:
    # Provide a stub main function that gives a helpful error message
    def main():
        """GUI entry point that requires wxPython."""
        import sys

        print(
            "Error: wxPython is not installed.\n"
            "The GUI requires wxPython, which is an optional dependency.\n\n"
            "To install it, run:\n"
            "  pip install dap-db-manager[gui]\n\n"
            "Or use the CLI tool 'ddm' instead, which works without wxPython.",
            file=sys.stderr,
        )
        sys.exit(1)

    __all__ = ["main", "is_wxpython_available"]
