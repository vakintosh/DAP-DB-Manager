"""Application entry point for the DAP DB Manager GUI.

This module provides the wxPython application class and main entry point.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

import sys

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from .main_frame import MyFrame
from ..config import Config
from ..database.cache import TagCache


class MyApp(wx.App):
    """Main wxPython application class."""

    def OnInit(self) -> bool:
        """Initialize the application.

        Returns:
            True if initialization succeeded
        """
        self.frame = MyFrame(None)
        return True


def main():
    """Main entry point for the DAP DB Manager GUI."""
    # Initialize cache configuration from user settings
    config = Config()
    TagCache.set_max_cache_memory(config.get_tag_cache_memory())

    app = MyApp(redirect=False)
    app.MainLoop()
    # Kill any remaining threads before we're done.
    sys.exit()


if __name__ == "__main__":
    main()
