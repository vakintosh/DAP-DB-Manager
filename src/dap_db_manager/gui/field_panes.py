"""Field pane components for browsing database entries.

This module provides UI components for filtering and browsing
through the database by genre, artist, album, and title.

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

from typing import Any

from . import wxFB_gui


# wxPython Phoenix: Use wx.lib.newevent
# The NewEvent() function returns an event class that can be instantiated with keyword arguments
FieldPaneEvent, EVT_FIELD_PANE = wx.lib.newevent.NewEvent()

# wxPython Phoenix: Use wx.lib.newevent
_DatabaseEvent, EVT_DATABASE = wx.lib.newevent.NewEvent()


class DatabaseEvent:
    """Helper class for posting database events."""

    @staticmethod
    def post_updated(obj, database):
        """Post a database updated event.

        Args:
            obj: Object to post event to
            database: Updated database instance
        """
        evt = _DatabaseEvent(database=database)
        wx.PostEvent(obj.GetEventHandler(), evt)


class FieldPane(wxFB_gui.FieldPane):
    """Single pane for displaying and selecting field values."""

    def __init__(self, parent):
        """Initialize the field pane.

        Args:
            parent: Parent window
        """
        wxFB_gui.FieldPane.__init__(self, parent)
        self.entries = []
        self.field = self.choice.GetStringSelection().lower()

    def UpdateListBox(self):
        """Update the listbox with current field values."""
        if self.field == "<none>":
            self.listbox.Set(["<All>"])
            self.PostEvent("<All>")
            return

        values: dict[str, Any] = {}
        for entry in self.entries:
            value = entry[self.field]
            if value not in values:
                values[value.data] = value.sort_value()

        # Sort with mixed type handling (strings vs integers)
        def sort_key(k):
            v = values[k]
            # Return tuple: (type_priority, value) to sort by type first, then value
            # Strings (including <Invalid Reference>) sort before numbers
            if isinstance(v, str):
                return (0, v.lower())
            else:
                return (1, v)

        sorted_values = sorted(values.keys(), key=sort_key)
        self.listbox.Set(["<All>"] + sorted_values)
        self.listbox.SetSelection(0)
        self.PostEvent("<All>")

    def PostEvent(self, selection):
        """Post a field pane selection event.

        Args:
            selection: Selected value
        """
        evt = FieldPaneEvent(selection=selection, pane=self)
        wx.PostEvent(self.GetEventHandler(), evt)

    def SetEntries(self, entries):
        """Set the entries to display.

        Args:
            entries: List of database entries
        """
        self.entries = entries
        self.UpdateListBox()

    def SetField(self, field):
        """Set the field to display.

        Args:
            field: Field name
        """
        self.field = field.lower()
        self.choice.SetStringSelection(field)
        self.UpdateListBox()

    def OnFieldChange(self, evt):
        """Handle field selection change.

        Args:
            evt: Choice selection event
        """
        self.SetField(evt.GetString())
        evt.Skip()

    def OnListSelect(self, evt):
        """Handle list selection change.

        Args:
            evt: List selection event
        """
        self.PostEvent(evt.GetString())


class FieldPanePanel(wx.Panel):
    """Panel containing multiple field panes for browsing the database."""

    def __init__(self, parent):
        """Initialize the field pane panel.

        Args:
            parent: Parent window
        """
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.panes = []
        for i, field in enumerate(["Genre", "Artist", "Album"]):
            pane = FieldPane(self)
            self.panes.append(pane)
            pane.SetField(field)
            pane.Bind(EVT_FIELD_PANE, self.OnPaneSelect(i))
            sizer.Add(pane, 1, wx.ALL | wx.EXPAND, 5)

        choice = wx.Choice(self, wx.ID_ANY, choices=["Title"])
        choice.SetSelection(0)
        self.titlepane = wx.ListBox(self, wx.ID_ANY, style=wx.LB_SINGLE | wx.LB_SORT)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(choice, 0, wx.ALL | wx.EXPAND, 5)
        s.Add(self.titlepane, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(s, 1, wx.ALL | wx.EXPAND, 5)

        self.tagnavi = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_READONLY)
        tagnavisizer = wx.BoxSizer(wx.HORIZONTAL)
        tagnavisizer.Add(
            wx.StaticText(self, wx.ID_ANY, "Tagnavi line:"),
            0,
            wx.ALL | wx.ALIGN_CENTER,
            5,
        )
        tagnavisizer.Add(self.tagnavi, 1, wx.ALL | wx.EXPAND, 5)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(sizer, 1, wx.EXPAND, 0)
        mainsizer.Add(tagnavisizer, 0, wx.EXPAND, 0)

        self.SetSizerAndFit(mainsizer)
        self.database = None

        self.OnFieldChange(None)
        self.Bind(EVT_DATABASE, self.OnDatabaseUpdate)
        self.Bind(wx.EVT_CHOICE, self.OnFieldChange)

    def OnFieldChange(self, evt):
        """Handle field selection change to update tagnavi line.

        Args:
            evt: Choice selection event (can be None)
        """
        field_names = [pane.choice.GetStringSelection() for pane in self.panes]
        field_names = [name for name in field_names if name != "<None>"]

        fields = [f.lower().replace(" ", "") for f in field_names]

        tagnavi = '"%s" -> %s ' % (field_names[0], fields[0])
        if self.database is not None:
            tagnavi += "? "
            for multiple_field in self.database.multiple_fields:
                if multiple_field in fields:
                    tagnavi += '%s != "<BLANK>" ' % multiple_field
                else:
                    tagnavi += '%s == "<BLANK>" ' % multiple_field

        for field in fields[1:]:
            tagnavi += "-> %s " % field

        tagnavi += '-> title = "fmt_title"'

        self.tagnavi.ChangeValue(tagnavi)

    def OnDatabaseUpdate(self, evt):
        """Handle database update event.

        Args:
            evt: Database update event
        """
        self.SetDatabase(evt.database)
        self.OnFieldChange(None)

    def SetDatabase(self, database):
        """Set the database to browse.

        Args:
            database: Database instance
        """
        self.database = database
        self.panes[0].SetEntries(database.index.entries)

    def OnPaneSelect(self, pane_number):
        """Create event handler for pane selection.

        Args:
            pane_number: Index of the pane

        Returns:
            Event handler function
        """

        def func(evt):
            field = evt.pane.field
            entries = evt.pane.entries
            if evt.selection != "<All>":
                entries = [
                    entry for entry in entries if entry[field].matches(evt.selection)
                ]

            if pane_number == len(self.panes) - 1:
                # Special formatting for the title pane
                formatted = []
                for entry in entries:
                    format = ""
                    if entry["discnumber"]:
                        format = "%d." % entry["discnumber"]
                    format += "%02d - %s" % (entry["tracknumber"], entry["title"].data)
                    formatted.append(format)
                self.titlepane.Set(formatted)
                return

            self.panes[pane_number + 1].SetEntries(entries)

        return func
