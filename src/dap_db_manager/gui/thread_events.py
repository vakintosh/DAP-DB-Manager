"""Thread event handling for background operations in the GUI.

This module provides custom wxPython events for communicating between
worker threads and the GUI thread.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

try:
    import wx
    import wx.lib.newevent
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e


# wxPython Phoenix: Use wx.lib.newevent instead of deprecated wx.NewEventType/PyEventBinder
ThreadStartEvent, EVT_THREAD_START = wx.lib.newevent.NewEvent()
ThreadCallbackEvent, EVT_THREAD_CALLBACK = wx.lib.newevent.NewEvent()
ThreadEndEvent, EVT_THREAD_END = wx.lib.newevent.NewEvent()


class ThreadEvent:
    """Helper class for posting thread events."""

    @staticmethod
    def post_start(obj, handler, info):
        """Post a thread start event to the GUI thread.

        Args:
            obj: The wx object to post the event to
            handler: The event handler function
            info: Info object for progress tracking
        """
        evt = ThreadStartEvent(info=info, _handler=handler)
        wx.PostEvent(obj, evt)  # Post directly to frame
        wx.WakeUpIdle()

    @staticmethod
    def post_end(obj, handler, info):
        """Post a thread end event to the GUI thread.

        Args:
            obj: The wx object to post the event to
            handler: The event handler function
            info: Info object for progress tracking
        """
        evt = ThreadEndEvent(info=info, _handler=handler)
        wx.PostEvent(obj, evt)  # Post directly to frame
        wx.WakeUpIdle()

    @staticmethod
    def post_callback(obj, handler, info, message, *args, **kwargs):
        """Post a callback event to the GUI thread for progress updates.

        Args:
            obj: The wx object to post the event to
            handler: The event handler function
            info: Info object for progress tracking
            message: Progress message
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        evt = ThreadCallbackEvent(
            message=message, info=info, _handler=handler, args=args, **kwargs
        )
        wx.PostEvent(obj, evt)  # Post directly to frame
        wx.WakeUpIdle()
