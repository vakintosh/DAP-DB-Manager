"""Error handling utilities for the DAP DB Manager GUI.

This module provides error dialogs and validation functions for user input.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

from pathlib import Path
from typing import Optional

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e


def show_error_dialog(
    parent: Optional[wx.Window], title: str, message: str, details: Optional[str] = None
) -> None:
    """Show a user-friendly error dialog.

    Args:
        parent: Parent window (can be None)
        title: Dialog title
        message: Main error message
        details: Optional detailed error information (e.g., stack trace)
    """
    if details:
        full_message = f"{message}\n\nDetails:\n{details}"
    else:
        full_message = message

    dlg = wx.MessageDialog(parent, full_message, title, wx.OK | wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()


def show_warning_dialog(parent: Optional[wx.Window], title: str, message: str) -> None:
    """Show a warning dialog.

    Args:
        parent: Parent window (can be None)
        title: Dialog title
        message: Warning message
    """
    dlg = wx.MessageDialog(parent, message, title, wx.OK | wx.ICON_WARNING)
    dlg.ShowModal()
    dlg.Destroy()


def validate_path(path: str, must_exist: bool = True) -> tuple[bool, str]:
    """Validate a file or directory path.

    Args:
        path: Path to validate
        must_exist: Whether the path must already exist

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path or not path.strip():
        return False, "Path cannot be empty"

    path = path.strip()
    path_obj = Path(path)

    if must_exist and not path_obj.exists():
        return False, f"Path does not exist: {path}"

    # Check if parent directory exists for output paths
    if not must_exist:
        parent = path_obj.parent
        if parent and not parent.exists():
            return False, f"Parent directory does not exist: {parent}"

    return True, ""


def validate_format_string(format_str: str) -> tuple[bool, str]:
    """Validate a titleformat string.

    Args:
        format_str: Format string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not format_str or not format_str.strip():
        return False, "Format string cannot be empty"

    # Basic validation - check for balanced brackets
    stack = []
    for i, char in enumerate(format_str):
        if char in "[(":
            stack.append((char, i))
        elif char in "])":
            if not stack:
                return False, f"Unmatched closing bracket '{char}' at position {i}"
            opening, _ = stack.pop()
            if (char == "]" and opening != "[") or (char == ")" and opening != "("):
                return False, f"Mismatched bracket at position {i}"

    if stack:
        char, pos = stack[0]
        return False, f"Unclosed bracket '{char}' at position {pos}"

    return True, ""
