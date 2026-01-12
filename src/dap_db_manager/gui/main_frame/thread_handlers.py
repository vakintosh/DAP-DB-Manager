"""Thread event handlers for the main frame.

This module handles wxPython thread events that communicate between
background workers and the GUI thread.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from typing import Any, Optional


class EventData:
    """Container for event data passed to handlers."""

    info: Optional[Any] = None
    message: Optional[Any] = None


class ThreadHandlers:
    """Handles thread-related events for the main frame."""

    def __init__(self, frame):
        """Initialize thread handlers.

        Args:
            frame: The MyFrame instance
        """
        self.frame = frame

    def on_thread_start(self, evt):
        """Handle thread start event.

        Args:
            evt: Thread start event
        """
        if hasattr(evt, "_handler"):
            # Extract data from event to avoid using deleted event object
            handler = evt._handler
            info = evt.info if hasattr(evt, "info") else None

            event_data = EventData()
            event_data.info = info

            handler(event_data)
        wx.WakeUpIdle()

    def on_thread_message(self, evt):
        """Handle thread message/callback event.

        Args:
            evt: Thread callback event
        """
        if hasattr(evt, "_handler"):
            # Extract data from event to avoid using deleted event object
            handler = evt._handler
            info = evt.info if hasattr(evt, "info") else None
            message = evt.message if hasattr(evt, "message") else None

            event_data = EventData()
            event_data.info = info
            event_data.message = message

            handler(event_data)
        wx.WakeUpIdle()

    def on_thread_end(self, evt):
        """Handle thread end event.

        Args:
            evt: Thread end event
        """
        if hasattr(evt, "_handler"):
            # Extract data from event before CallAfter, as event object gets deleted
            handler = evt._handler
            info = evt.info if hasattr(evt, "info") else None

            # Create a simple container for the info
            event_data = EventData()
            event_data.info = info

            # Wrap the handler in CallAfter to ensure the UI thread
            # is definitely ready to process the layout change.
            wx.CallAfter(handler, event_data)

        if hasattr(evt, "info") and evt.info in self.frame.thread_info:
            self.frame.thread_info.remove(evt.info)

        wx.WakeUpIdle()
