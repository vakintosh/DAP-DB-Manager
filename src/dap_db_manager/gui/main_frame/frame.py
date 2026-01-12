"""Main frame class for the DAP DB Manager GUI.

This module contains the MyFrame class which coordinates all components
of the main application window.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from ...database import Database
from .. import wxFB_gui
from ...config import Config
from ..thread_events import EVT_THREAD_START, EVT_THREAD_CALLBACK, EVT_THREAD_END
from ..info_panel import InfoPanel
from ..field_panes import FieldPanePanel

from .format_manager import FormatManager
from .threading_support import ThreadingSupport
from .thread_handlers import ThreadHandlers
from .database_operations import DatabaseOperations


class MyFrame(wxFB_gui.Frame):
    """Main application window frame.

    This class coordinates the various components of the GUI including
    format string management, database operations, and threading support.
    """

    def __init__(self, parent):
        """Initialize the main frame.

        Args:
            parent: Parent window (typically None for main frame)
        """
        wxFB_gui.Frame.__init__(self, parent)

        # Initialize component managers
        self.format_manager = FormatManager(self)
        self.threading_support = ThreadingSupport(self)
        self.thread_handlers = ThreadHandlers(self)
        self.db_operations = DatabaseOperations(self)

        # Bind thread events to handlers
        self.Bind(EVT_THREAD_START, self.thread_handlers.on_thread_start)
        self.Bind(EVT_THREAD_CALLBACK, self.thread_handlers.on_thread_message)
        self.Bind(EVT_THREAD_END, self.thread_handlers.on_thread_end)

        # Initialize configuration
        self.config = Config()

        # Setup field panes
        self.panes = FieldPanePanel(self.notebook)
        self.notebook.AddPage(self.panes, "View")
        self.status.SetStatusWidths([200, -1])

        # Hide Save Tags and Load Tags buttons
        self.m_button6.Hide()  # Save Tags button
        self.m_button61.Hide()  # Load Tags button

        # Insert the info panel into the sizer
        self.infopanel = InfoPanel(self.mainpanel)
        self.mainpanel.GetSizer().Insert(0, self.infopanel, 1, wx.ALL | wx.EXPAND, 5)
        self.mainpanel.Layout()

        # Initialize database
        self.database = Database()

        # List of currently running info panels
        self.thread_info = []

        # Restore window size and position from config
        width, height = self.config.get_window_size()
        x, y = self.config.get_window_position()
        self.SetSize(width, height)
        if x != -1 and y != -1:
            self.SetPosition((x, y))

        # Load saved format strings
        self.format_manager.load_format_strings()

        # Add tooltips to format string controls
        self.format_manager.add_format_tooltips()

        # Add right-click menu for templates
        self.format_manager.add_template_menus()

        # Create menu bar with Window menu
        self._create_menu_bar()

        self.Show()

        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def _create_menu_bar(self) -> None:
        """Create menu bar with Window menu and minimize functionality."""
        menubar = wx.MenuBar()

        # Window menu
        window_menu = wx.Menu()
        minimize_item = window_menu.Append(
            wx.ID_ANY, "Minimize\tCtrl+M", "Minimize window"
        )
        self.Bind(wx.EVT_MENU, lambda evt: self.Iconize(True), minimize_item)

        menubar.Append(window_menu, "&Window")
        self.SetMenuBar(menubar)

    # Event handlers - delegate to database operations
    def OnLoadTags(self, evt):
        """Handle Load Tags button click."""
        self.db_operations.on_load_tags(evt)

    def OnSaveTags(self, evt):
        """Handle Save Tags button click."""
        self.db_operations.on_save_tags(evt)

    def OnAddDirectory(self, evt):
        """Handle Add Directory button click."""
        self.db_operations.on_add_directory(evt)

    def OnGenerateDatabase(self, evt):
        """Handle Generate Database button click."""
        self.db_operations.on_generate_database(evt)

    def OnWriteDatabase(self, evt):
        """Handle Write Database button click."""
        self.db_operations.on_write_database(evt)

    def OnReadDatabase(self, evt):
        """Handle Read Database button click."""
        self.db_operations.on_read_database(evt)

    def OnClose(self, evt):
        """Handle window close event.

        Args:
            evt: Close event
        """
        # Save window size and position
        if not self.IsMaximized() and not self.IsIconized():
            size = self.GetSize()
            pos = self.GetPosition()
            self.config.set_window_size(size.width, size.height)
            self.config.set_window_position(pos.x, pos.y)

        # Save format strings
        self.format_manager.save_format_strings()

        # Save configuration
        self.config.save()

        # Stop all running threads
        for info in self.thread_info:
            info.timer.Stop()

        # Cancel all active threads
        self.threading_support.cancel_all_threads()

        # Shutdown database executor pools to free resources
        if hasattr(self, "database") and self.database is not None:
            try:
                self.database.shutdown(wait=False)
            except Exception:
                pass  # Ignore errors during cleanup

        evt.Skip()
