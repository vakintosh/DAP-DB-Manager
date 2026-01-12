###########################################################################
## Python code generated with wxFormBuilder (version Jun 11 2009)
## http://www.wxformbuilder.org/
##
## PLEASE DO "NOT" EDIT THIS FILE!
###########################################################################

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

###########################################################################
## Class Frame
###########################################################################


class Frame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(
            self,
            parent,
            id=wx.ID_ANY,
            title="Rockbox Database Builder",
            pos=wx.DefaultPosition,
            size=wx.Size(748, 410),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
        )

        self.SetSizeHints(wx.DefaultSize, wx.DefaultSize)

        bSizer1 = wx.BoxSizer(wx.VERTICAL)

        self.m_panel3 = wx.Panel(
            self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL
        )
        bSizer5 = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(
            self.m_panel3, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.mainpanel = wx.Panel(
            self.notebook,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.DefaultSize,
            wx.TAB_TRAVERSAL,
        )
        bSizer2 = wx.BoxSizer(wx.VERTICAL)

        bSizer4 = wx.BoxSizer(wx.HORIZONTAL)

        self.add_dir_button = wx.Button(
            self.mainpanel,
            wx.ID_ANY,
            "Add Directory",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        bSizer4.Add(self.add_dir_button, 0, wx.ALL, 5)

        self.m_button3 = wx.Button(
            self.mainpanel,
            wx.ID_ANY,
            "Generate Database",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        bSizer4.Add(self.m_button3, 0, wx.ALL, 5)

        self.m_button4 = wx.Button(
            self.mainpanel,
            wx.ID_ANY,
            "Write Database...",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        bSizer4.Add(self.m_button4, 0, wx.ALL, 5)

        self.m_button5 = wx.Button(
            self.mainpanel,
            wx.ID_ANY,
            "Load Database...",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        bSizer4.Add(self.m_button5, 0, wx.ALL, 5)

        self.m_button6 = wx.Button(
            self.mainpanel,
            wx.ID_ANY,
            "Save Tags...",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        bSizer4.Add(self.m_button6, 0, wx.ALL, 5)

        self.m_button61 = wx.Button(
            self.mainpanel,
            wx.ID_ANY,
            "Load Tags...",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        bSizer4.Add(self.m_button61, 0, wx.ALL, 5)

        bSizer2.Add(bSizer4, 0, wx.EXPAND, 5)

        self.mainpanel.SetSizer(bSizer2)
        self.mainpanel.Layout()
        bSizer2.Fit(self.mainpanel)
        self.notebook.AddPage(self.mainpanel, "Manage", True)
        self.m_panel5 = wx.Panel(
            self.notebook,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.DefaultSize,
            wx.TAB_TRAVERSAL,
        )
        fgSizer1 = wx.FlexGridSizer(0, 3, 0, 0)
        fgSizer1.AddGrowableCol(1)
        fgSizer1.AddGrowableCol(2)
        fgSizer1.SetFlexibleDirection(wx.BOTH)
        fgSizer1.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_ALL)

        self.m_staticText17 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Field", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText17.Wrap(-1)
        self.m_staticText17.SetFont(
            wx.Font(wx.NORMAL_FONT.GetPointSize(), 70, 90, 92, False, wx.EmptyString)
        )

        fgSizer1.Add(self.m_staticText17, 0, wx.ALL, 5)

        self.m_staticText171 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Format", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText171.Wrap(-1)
        self.m_staticText171.SetFont(
            wx.Font(wx.NORMAL_FONT.GetPointSize(), 70, 90, 92, False, wx.EmptyString)
        )

        fgSizer1.Add(self.m_staticText171, 0, wx.ALL, 5)

        self.m_staticText172 = wx.StaticText(
            self.m_panel5,
            wx.ID_ANY,
            "Sort Format",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        self.m_staticText172.Wrap(-1)
        self.m_staticText172.SetFont(
            wx.Font(wx.NORMAL_FONT.GetPointSize(), 70, 90, 92, False, wx.EmptyString)
        )

        fgSizer1.Add(self.m_staticText172, 0, wx.ALL, 5)

        self.m_staticText2 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Artist:", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText2.Wrap(-1)
        fgSizer1.Add(self.m_staticText2, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.artist = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%artist%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.artist, 1, wx.ALL | wx.EXPAND, 5)

        self.artist_sort = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "$swapprefix(%artist%)",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.artist_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_staticText21 = wx.StaticText(
            self.m_panel5,
            wx.ID_ANY,
            "Album Artist:",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        self.m_staticText21.Wrap(-1)
        fgSizer1.Add(self.m_staticText21, 0, wx.ALL, 5)

        self.albumartist = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "%album artist%",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.albumartist, 1, wx.ALL | wx.EXPAND, 5)

        self.albumartist_sort = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "$swapprefix(%album artist%)",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.albumartist_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_staticText211 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Album:", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText211.Wrap(-1)
        fgSizer1.Add(self.m_staticText211, 0, wx.ALL, 5)

        self.album = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "[(%date%) ]%album%",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.album, 1, wx.ALL | wx.EXPAND, 5)

        self.album_sort = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "[(%date%) ]%album%",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.album_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_staticText212 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Genre:", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText212.Wrap(-1)
        fgSizer1.Add(self.m_staticText212, 0, wx.ALL, 5)

        self.genre = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%genre%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.genre, 1, wx.ALL | wx.EXPAND, 5)

        self.genre_sort = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%genre%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.genre_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_staticText213 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Comment:", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText213.Wrap(-1)
        fgSizer1.Add(self.m_staticText213, 0, wx.ALL, 5)

        self.comment = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%comment%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.comment, 1, wx.ALL | wx.EXPAND, 5)

        self.comment_sort = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%comment%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.comment_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_staticText214 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Composer:", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText214.Wrap(-1)
        fgSizer1.Add(self.m_staticText214, 0, wx.ALL, 5)

        self.composer = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "%composer%",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.composer, 1, wx.ALL | wx.EXPAND, 5)

        self.composer_sort = wx.TextCtrl(
            self.m_panel5,
            wx.ID_ANY,
            "%composer%",
            wx.DefaultPosition,
            wx.DefaultSize,
            0,
        )
        fgSizer1.Add(self.composer_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_staticText215 = wx.StaticText(
            self.m_panel5, wx.ID_ANY, "Grouping:", wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.m_staticText215.Wrap(-1)
        fgSizer1.Add(self.m_staticText215, 0, wx.ALL, 5)

        self.grouping = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%title%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.grouping, 1, wx.ALL | wx.EXPAND, 5)

        self.grouping_sort = wx.TextCtrl(
            self.m_panel5, wx.ID_ANY, "%title%", wx.DefaultPosition, wx.DefaultSize, 0
        )
        fgSizer1.Add(self.grouping_sort, 1, wx.ALL | wx.EXPAND, 5)

        self.m_panel5.SetSizer(fgSizer1)
        self.m_panel5.Layout()
        fgSizer1.Fit(self.m_panel5)
        self.notebook.AddPage(self.m_panel5, "Formats", False)

        bSizer5.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        self.m_panel3.SetSizer(bSizer5)
        self.m_panel3.Layout()
        bSizer5.Fit(self.m_panel3)
        bSizer1.Add(self.m_panel3, 1, wx.EXPAND, 5)

        self.SetSizer(bSizer1)
        self.Layout()
        self.status = self.CreateStatusBar(2, wx.STB_SIZEGRIP, wx.ID_ANY)

        # Connect Events
        self.add_dir_button.Bind(wx.EVT_BUTTON, self.OnAddDirectory)
        self.m_button3.Bind(wx.EVT_BUTTON, self.OnGenerateDatabase)
        self.m_button4.Bind(wx.EVT_BUTTON, self.OnWriteDatabase)
        self.m_button5.Bind(wx.EVT_BUTTON, self.OnReadDatabase)
        self.m_button6.Bind(wx.EVT_BUTTON, self.OnSaveTags)
        self.m_button61.Bind(wx.EVT_BUTTON, self.OnLoadTags)

    def __del__(self):
        pass
        # Disconnect Events - not needed in wxPython Phoenix, causes errors
        # Events are automatically disconnected when widgets are destroyed

    # Virtual event handlers, overide them in your derived class
    def OnAddDirectory(self, event):
        event.Skip()

    def OnGenerateDatabase(self, event):
        event.Skip()

    def OnWriteDatabase(self, event):
        event.Skip()

    def OnReadDatabase(self, event):
        event.Skip()

    def OnSaveTags(self, event):
        event.Skip()

    def OnLoadTags(self, event):
        event.Skip()


###########################################################################
## Class FieldPane
###########################################################################


class FieldPane(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(
            self,
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            size=wx.Size(500, 300),
            style=wx.TAB_TRAVERSAL,
        )

        bSizer9 = wx.BoxSizer(wx.VERTICAL)

        choiceChoices = [
            "<None>",
            "Album Artist",
            "Artist",
            "Album",
            "Genre",
            "Title",
            "Path",
            "Composer",
            "Comment",
            "Grouping",
        ]
        self.choice = wx.Choice(
            self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, choiceChoices, 0
        )
        self.choice.SetSelection(0)
        bSizer9.Add(self.choice, 0, wx.ALL | wx.EXPAND, 5)

        listboxChoices: list[str] = []
        self.listbox = wx.ListBox(
            self,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.DefaultSize,
            listboxChoices,
            wx.LB_SINGLE,
        )
        bSizer9.Add(self.listbox, 1, wx.ALL | wx.EXPAND, 5)

        self.SetSizer(bSizer9)
        self.Layout()

        # Connect Events
        self.choice.Bind(wx.EVT_CHOICE, self.OnFieldChange)
        self.listbox.Bind(wx.EVT_LISTBOX, self.OnListSelect)

    def __del__(self):
        pass
        # Disconnect Events - not needed in wxPython Phoenix, causes errors
        # Events are automatically disconnected when widgets are destroyed

    # Virtual event handlers, overide them in your derived class
    def OnFieldChange(self, event):
        event.Skip()

    def OnListSelect(self, event):
        event.Skip()
