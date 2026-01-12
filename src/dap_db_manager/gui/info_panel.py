"""Progress tracking UI components for the DAP DB Manager.

This module provides widgets for displaying operation progress,
including gauges, timers, and status messages.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e


class InfoPanel(wx.ScrolledWindow):
    """Scrollable panel that displays multiple progress tracking rows."""

    def __init__(self, parent):
        wx.ScrolledWindow.__init__(self, parent, wx.ID_ANY, style=wx.BORDER_SUNKEN)
        self.SetScrollRate(10, 10)
        self.sizer = wx.FlexGridSizer(0, 4, 0, 0)
        self.sizer.AddGrowableCol(3)
        self.SetSizer(self.sizer)

    def MakeRow(self, description=""):
        """Create an Info object, add it to the sizer, and return it.

        Args:
            description: Description text for the operation

        Returns:
            Info object for progress tracking
        """
        info = Info(self, description)
        self.sizer.Add(info.time_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.sizer.Add(info.description_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.sizer.Add(info.gauge_ctrl, 1, wx.ALL, 5)
        self.sizer.Add(
            info.status_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL | wx.EXPAND, 5
        )
        self.sizer.Layout()
        self.Refresh()
        return info


class RapidlyUpdatingText(wx.Window):
    """A very simple static text control.

    wxStaticText tries to resize itself every time it is updated, which slows
    down the gui. This custom control avoids that issue.
    """

    def __init__(self, parent, id, text="", pos=(-1, -1), size=(-1, -1), style=0):
        wx.Window.__init__(self, parent, id, pos, size, style)
        self.SetValue(text)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def SetValue(self, text):
        """Update the text content and trigger a repaint.

        Args:
            text: New text to display
        """
        self.text = str(text)
        self.SetMinSize(self.GetTextExtent(text))
        self.Refresh()
        self.Update()
        # Also refresh parent to ensure changes are visible
        parent = self.GetParent()
        if parent:
            parent.Refresh()
            parent.Update()

    def GetValue(self):
        """Get the current text content.

        Returns:
            Current text string
        """
        return self.text

    def OnPaint(self, evt):
        """Handle paint events to draw the text.

        Args:
            evt: Paint event
        """
        dc = wx.PaintDC(self)
        dc.SetFont(self.GetFont())
        dc.DrawText(self.text, 0, 0)


class Info(object):
    """Progress tracking information for a single operation.

    Provides a gauge, timer, description, and status message
    for tracking background operations.
    """

    def __init__(self, parent, description=""):
        """Initialize the Info object.

        Args:
            parent: Parent window
            description: Description of the operation
        """
        self.parent = parent
        self.gauge_ctrl = wx.Gauge(parent, wx.ID_ANY, size=(-1, 15))
        self.gauge_ctrl.SetMinSize((150, 15))
        self.time_ctrl = RapidlyUpdatingText(parent, wx.ID_ANY, "00:00")
        self.description_ctrl = RapidlyUpdatingText(parent, wx.ID_ANY, description)
        self.status_ctrl = RapidlyUpdatingText(parent, wx.ID_ANY, "")

        self.elapsed_time = 0

        class MyTimer(wx.Timer):
            def Notify(dummy_self):
                self.elapsed_time += 1
                # Format the time
                minutes, seconds = divmod(self.elapsed_time, 60)
                hours, minutes = divmod(minutes, 60)
                s = ""
                if hours:
                    s = "%d:" % hours
                s += "%02d:%02d" % (minutes, seconds)
                self.time_value = s  # Use time_value property, not time

        self.timer = MyTimer()
        self.timer.Start(1000)
        self.timer.Stop()

    def SetRange(self, range):
        """Set the range of the progress gauge.

        Args:
            range: Maximum value for the gauge
        """
        self.gauge_ctrl.SetRange(range)

    # Allow access to the controls as properties
    @staticmethod
    def _make_property(name: str):
        """Create a property that delegates to the underlying control.

        Args:
            name: Base name of the control (without _ctrl suffix)

        Returns:
            Property object
        """
        ctrl_name = name + "_ctrl"

        def __get(self):
            return getattr(self, ctrl_name).GetValue()

        def __set(self, value):
            getattr(self, ctrl_name).SetValue(value)

        return property(__get, __set)

    gauge = _make_property("gauge")
    time_value = _make_property("time")  # Renamed to avoid shadowing time module
    description = _make_property("description")
    status = _make_property("status")
