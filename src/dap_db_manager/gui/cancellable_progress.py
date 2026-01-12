"""Progress dialog with cancellation support for long-running operations.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from typing import Optional, Callable


class CancellableProgressDialog(wx.Dialog):
    """A progress dialog that can be cancelled by the user."""

    def __init__(
        self,
        parent,
        title: str,
        message: str,
        maximum: int = 100,
        style: int = wx.PD_APP_MODAL | wx.PD_AUTO_HIDE,
    ):
        """Initialize the cancellable progress dialog.

        Args:
            parent: Parent window
            title: Dialog title
            message: Initial message to display
            maximum: Maximum value for progress
            style: Dialog style flags
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)

        self.maximum = maximum
        self._cancelled = False
        self._cancel_callback: Optional[Callable] = None

        # Create UI
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Message
        self.message_text = wx.StaticText(self, label=message)
        main_sizer.Add(self.message_text, 0, wx.ALL | wx.EXPAND, 10)

        # Progress bar
        self.gauge = wx.Gauge(self, range=maximum, style=wx.GA_HORIZONTAL)
        main_sizer.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 10)

        # Status text
        self.status_text = wx.StaticText(self, label="")
        main_sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(main_sizer)
        main_sizer.Fit(self)

        # Center on parent
        self.CenterOnParent()

    def set_cancel_callback(self, callback: Callable) -> None:
        """Set the callback to call when cancelled.

        Args:
            callback: Function to call when user clicks Cancel
        """
        self._cancel_callback = callback

    def on_cancel(self, evt):
        """Handle cancel button click."""
        self._cancelled = True
        self.status_text.SetLabel("Cancelling...")
        self.cancel_button.Enable(False)

        if self._cancel_callback:
            self._cancel_callback()

    def update(self, value: int, message: Optional[str] = None) -> bool:
        """Update the progress dialog.

        Args:
            value: New progress value
            message: Optional new message to display

        Returns:
            True if should continue, False if cancelled
        """
        if self._cancelled:
            return False

        self.gauge.SetValue(min(value, self.maximum))

        if message:
            self.status_text.SetLabel(message)

        # Process pending events to keep UI responsive
        wx.GetApp().Yield(True)

        return not self._cancelled

    def set_range(self, maximum: int) -> None:
        """Update the maximum value of the progress bar.

        Args:
            maximum: New maximum value
        """
        self.maximum = maximum
        self.gauge.SetRange(maximum)

    def pulse(self, message: Optional[str] = None) -> bool:
        """Pulse the progress bar (indeterminate mode).

        Args:
            message: Optional new message to display

        Returns:
            True if should continue, False if cancelled
        """
        if self._cancelled:
            return False

        self.gauge.Pulse()

        if message:
            self.status_text.SetLabel(message)

        wx.GetApp().Yield(True)

        return not self._cancelled

    def is_cancelled(self) -> bool:
        """Check if the operation was cancelled.

        Returns:
            True if cancelled, False otherwise
        """
        return self._cancelled


class NonModalProgressDialog:
    """A non-modal progress indicator that doesn't block the UI."""

    def __init__(self, parent, title: str, message: str):
        """Initialize non-modal progress dialog.

        Args:
            parent: Parent window
            title: Dialog title
            message: Initial message
        """
        self.frame = wx.Frame(
            parent,
            title=title,
            style=wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT | wx.FRAME_NO_TASKBAR,
        )

        self._cancelled = False
        self._cancel_callback: Optional[Callable] = None

        # Create UI
        panel = wx.Panel(self.frame)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Message
        self.message_text = wx.StaticText(panel, label=message)
        sizer.Add(self.message_text, 0, wx.ALL | wx.EXPAND, 10)

        # Progress bar
        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        sizer.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 10)

        # Status
        self.status_text = wx.StaticText(panel, label="")
        sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 10)

        # Cancel button
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        sizer.Add(self.cancel_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)
        sizer.Fit(self.frame)

        # Center on parent
        self.frame.CenterOnParent()

    def show(self) -> None:
        """Show the progress dialog."""
        self.frame.Show()

    def hide(self) -> None:
        """Hide the progress dialog."""
        self.frame.Hide()

    def destroy(self) -> None:
        """Destroy the progress dialog."""
        self.frame.Destroy()

    def set_cancel_callback(self, callback: Callable) -> None:
        """Set the cancellation callback."""
        self._cancel_callback = callback

    def on_cancel(self, evt):
        """Handle cancel button."""
        self._cancelled = True
        self.status_text.SetLabel("Cancelling...")
        self.cancel_button.Enable(False)

        if self._cancel_callback:
            self._cancel_callback()

    def update(self, value: int, message: Optional[str] = None) -> bool:
        """Update progress."""
        if self._cancelled:
            return False

        self.gauge.SetValue(min(value, 100))

        if message:
            self.status_text.SetLabel(message)

        return not self._cancelled

    def set_range(self, maximum: int) -> None:
        """Set the progress range."""
        self.gauge.SetRange(maximum)

    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self._cancelled
