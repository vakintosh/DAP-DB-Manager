"""Format string management for the main frame.

This module handles loading, saving, validation, and template management
for titleformat strings used in database generation.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from ...constants import FORMATTED_TAGS


class FormatManager:
    """Manages format strings for database fields."""

    def __init__(self, frame):
        """Initialize the format manager.

        Args:
            frame: The MyFrame instance
        """
        self.frame = frame

    def load_format_strings(self) -> None:
        """Load saved format strings into the GUI."""
        for field in FORMATTED_TAGS:
            # Get the control name (e.g., "artist" from "artist")
            control_name = field.replace(" ", "")

            # Get the controls
            format_ctrl = getattr(self.frame, control_name, None)
            sort_ctrl = getattr(self.frame, control_name + "_sort", None)

            if format_ctrl:
                # Get saved format string, or use current value if not saved
                saved_format = self.frame.config.get_format(field)
                if saved_format is not None:
                    format_ctrl.SetValue(saved_format)

            if sort_ctrl:
                # Get saved sort format, or use current value if not saved
                saved_sort = self.frame.config.get_sort_format(field)
                if saved_sort is not None:
                    sort_ctrl.SetValue(saved_sort)

    def save_format_strings(self) -> None:
        """Save current format strings to config."""
        for field in FORMATTED_TAGS:
            # Get the control name
            control_name = field.replace(" ", "")

            # Get the controls
            format_ctrl = getattr(self.frame, control_name, None)
            sort_ctrl = getattr(self.frame, control_name + "_sort", None)

            if format_ctrl:
                # Save the format string
                format_str = format_ctrl.GetValue()
                self.frame.config.set_format(field, format_str)

            if sort_ctrl:
                # Save the sort format
                sort_str = sort_ctrl.GetValue()
                self.frame.config.set_sort_format(field, sort_str)

    def add_format_tooltips(self) -> None:
        """Add helpful tooltips to format string controls."""

        # Common tooltip text explaining format syntax
        format_help = (
            "Titleformat Syntax:\n"
            "  %field% - Insert tag value (e.g., %artist%, %album%)\n"
            "  [text] - Optional text (shown only if all tags inside exist)\n"
            "  $function(args) - Function call\n\n"
            "Common Functions:\n"
            "  $swapprefix(text) - Move 'The/A/An' to end\n"
            "  $upper(text) - Convert to uppercase\n"
            "  $lower(text) - Convert to lowercase\n"
            "  $caps(text) - Capitalize first letter\n"
            "  $replace(text,old,new) - Replace text\n\n"
            "Examples:\n"
            "  %artist% → 'The Beatles'\n"
            "  $swapprefix(%artist%) → 'Beatles, The'\n"
            "  [(%date%) ]%album% → '(1967) Sgt Pepper' or 'Album Name'\n"
            "  %album artist% → Album artist tag value"
        )

        sort_help = (
            "Sort Format:\n"
            "Defines how this field is sorted in lists.\n"
            "Usually same as display format, but often uses\n"
            "$swapprefix() to ignore 'The', 'A', 'An' prefixes.\n\n"
            "Example: $swapprefix(%artist%)\n"
            "  'The Beatles' sorts as 'Beatles, The'"
        )

        # Add tooltips to all format controls
        for field in FORMATTED_TAGS:
            control_name = field.replace(" ", "")

            format_ctrl = getattr(self.frame, control_name, None)
            if format_ctrl:
                format_ctrl.SetToolTip(format_help)

            sort_ctrl = getattr(self.frame, control_name + "_sort", None)
            if sort_ctrl:
                sort_ctrl.SetToolTip(sort_help)

    def get_format_templates(self) -> dict:
        """Return a dictionary of common format string templates.

        Returns:
            Dictionary mapping template names to field configurations
        """
        return {
            "Simple": {
                "artist": "%artist%",
                "album": "%album%",
                "genre": "%genre%",
                "composer": "%composer%",
                "comment": "%comment%",
                "albumartist": "%album artist%",
                "grouping": "%grouping%",
            },
            "With Sorting": {
                "artist": "%artist%",
                "artist_sort": "$swapprefix(%artist%)",
                "album": "%album%",
                "album_sort": "%album%",
                "genre": "%genre%",
                "genre_sort": "%genre%",
            },
            "Year + Album": {
                "album": "[(%date%) ]%album%",
                "album_sort": "[(%date%) ]%album%",
            },
            "Classical": {
                "artist": "%composer%",
                "artist_sort": "$swapprefix(%composer%)",
                "album": "%album%",
                "grouping": "%composer% - %title%",
            },
            "Compilation Friendly": {
                "artist": "$if(%album artist%,%album artist%,%artist%)",
                "artist_sort": "$if(%album artist%,$swapprefix(%album artist%),$swapprefix(%artist%))",
                "albumartist": "%album artist%",
                "albumartist_sort": "$swapprefix(%album artist%)",
            },
        }

    def add_template_menus(self) -> None:
        """Add right-click context menus with templates to format controls."""

        # Get all format controls
        format_controls = []
        for field in FORMATTED_TAGS:
            control_name = field.replace(" ", "")
            format_ctrl = getattr(self.frame, control_name, None)
            sort_ctrl = getattr(self.frame, control_name + "_sort", None)

            if format_ctrl:
                format_controls.append((format_ctrl, field, False))
            if sort_ctrl:
                format_controls.append((sort_ctrl, field, True))

        # Bind right-click event to show template menu
        for ctrl, field, is_sort in format_controls:
            ctrl.Bind(
                wx.EVT_CONTEXT_MENU,
                lambda evt, c=ctrl, f=field, s=is_sort: self._show_template_menu(
                    evt, c, f, s
                ),
            )

    def _show_template_menu(self, evt, ctrl, field, is_sort):
        """Show context menu with format templates.

        Args:
            evt: Context menu event
            ctrl: The control to apply template to
            field: Field name
            is_sort: Whether this is a sort format field
        """
        menu = wx.Menu()

        # Add "Copy" and "Paste" options
        copy_item = menu.Append(wx.ID_ANY, "Copy")
        paste_item = menu.Append(wx.ID_ANY, "Paste")
        menu.AppendSeparator()

        # Bind copy/paste
        self.frame.Bind(wx.EVT_MENU, lambda e: self._copy_format(ctrl), copy_item)
        self.frame.Bind(wx.EVT_MENU, lambda e: self._paste_format(ctrl), paste_item)

        # Add template submenu
        template_menu = wx.Menu()
        templates = self.get_format_templates()

        for template_name, template_formats in templates.items():
            # Check if this template has a value for this field
            control_name = field.replace(" ", "")
            key = control_name + "_sort" if is_sort else control_name

            if key in template_formats:
                item = template_menu.Append(wx.ID_ANY, template_name)
                template_value = template_formats[key]
                self.frame.Bind(
                    wx.EVT_MENU,
                    lambda e, v=template_value, c=ctrl: self._apply_template(c, v),
                    item,
                )

        if template_menu.GetMenuItemCount() > 0:
            menu.AppendSubMenu(template_menu, "Apply Template")

        # Show the menu
        self.frame.PopupMenu(menu)
        menu.Destroy()

    def _copy_format(self, ctrl):
        """Copy format string to clipboard.

        Args:
            ctrl: Control to copy from
        """
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(ctrl.GetValue()))
            wx.TheClipboard.Close()

    def _paste_format(self, ctrl):
        """Paste format string from clipboard.

        Args:
            ctrl: Control to paste into
        """
        if wx.TheClipboard.Open():
            data = wx.TextDataObject()
            if wx.TheClipboard.GetData(data):
                ctrl.SetValue(data.GetText())
            wx.TheClipboard.Close()

    def _apply_template(self, ctrl, template_value):
        """Apply a template value to a control.

        Args:
            ctrl: Control to apply template to
            template_value: Template value string
        """
        ctrl.SetValue(template_value)
