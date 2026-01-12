"""Database operation handlers for the main frame.

This module contains all the event handlers for database operations
like loading, saving, generating, reading, and writing databases.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

from pathlib import Path

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from ..error_handling import show_error_dialog, validate_path
from ..field_panes import DatabaseEvent
from ...constants import FORMATTED_TAGS
from ...database import Database


class DatabaseOperations:
    """Handles database operations for the main frame."""

    def __init__(self, frame):
        """Initialize database operations.

        Args:
            frame: The MyFrame instance
        """
        self.frame = frame

    def on_load_tags(self, evt):
        """Handle Load Tags button click.

        Args:
            evt: Button click event
        """
        default_dir = self.frame.config.get_last_tags_file()
        if default_dir:
            default_dir = str(Path(default_dir).parent)

        filename = wx.FileSelector(
            "Load Tags", default_path=default_dir or "", default_extension=".pkl"
        )
        if not filename:
            return

        # Validate file path
        is_valid, error_msg = validate_path(filename, must_exist=True)
        if not is_valid:
            show_error_dialog(self.frame, "Invalid File Path", error_msg)
            return

        # Save to config
        self.frame.config.set_last_tags_file(filename)
        self.frame.config.save()

        def OnStart(evt):
            evt.info.timer.Start()

        def OnMessage(evt):
            if isinstance(evt.message, int):
                evt.info.SetRange(evt.message)
                evt.info.gauge = 0
            else:
                evt.info.gauge += 1
                evt.info.status = evt.message

        def OnEnd(evt):
            evt.info.timer.Stop()
            evt.info.gauge = evt.info.gauge_ctrl.GetRange()  # Set to maximum
            evt.info.status = "Done"
            # Force the InfoPanel to re-layout and repaint immediately
            evt.info.parent.Layout()
            evt.info.parent.Refresh()

        self.frame.threading_support.start_thread(
            self.frame.database.load_tags,
            filename,
            callback=None,
            _start=OnStart,
            _message=OnMessage,
            _end=OnEnd,
            _info=self.frame.infopanel.MakeRow("Loading saved tags"),
        )

    def on_save_tags(self, evt):
        """Handle Save Tags button click.

        Args:
            evt: Button click event
        """
        filename = wx.FileSelector("Save Tags", default_extension=".pkl")
        if not filename:
            return

        def OnStart(evt):
            evt.info.timer.Start()

        def OnMessage(evt):
            if isinstance(evt.message, int):
                evt.info.SetRange(evt.message)
                evt.info.gauge = 0
            else:
                evt.info.gauge += 1
                evt.info.status = evt.message

        def OnEnd(evt):
            evt.info.timer.Stop()
            evt.info.gauge = evt.info.gauge_ctrl.GetRange()  # Set to maximum
            evt.info.status = "Done"
            # Force the InfoPanel to re-layout and repaint immediately
            evt.info.parent.Layout()
            evt.info.parent.Refresh()

        self.frame.threading_support.start_thread(
            self.frame.database.save_tags,
            filename,
            callback=None,
            _start=OnStart,
            _message=OnMessage,
            _end=OnEnd,
            _info=self.frame.infopanel.MakeRow("Saving tags"),
        )

    def on_add_directory(self, evt):
        """Handle Add Directory button click.

        Args:
            evt: Button click event
        """
        default_dir = self.frame.config.get_last_music_dir()
        dir = wx.DirSelector("Music Directory", default_path=default_dir or "")
        if not dir:
            return

        # Validate directory path
        is_valid, error_msg = validate_path(dir, must_exist=True)
        if not is_valid:
            show_error_dialog(self.frame, "Invalid Directory Path", error_msg)
            return

        # Save to config
        self.frame.config.set_last_music_dir(dir)
        self.frame.config.save()

        def OnStart(evt):
            evt.info.timer.Start()

        def OnMessage(evt):
            if isinstance(evt.message, int):
                evt.info.SetRange(evt.message)
            else:
                evt.info.status = evt.message
                evt.info.gauge += 1

        def OnEnd(evt):
            evt.info.timer.Stop()
            evt.info.gauge = evt.info.gauge_ctrl.GetRange()  # Set to maximum
            evt.info.status = "Done"
            # Force the InfoPanel to re-layout and repaint immediately
            evt.info.parent.Layout()
            evt.info.parent.Refresh()

        self.frame.threading_support.start_thread(
            self.frame.database.add_dir,
            dir,
            dircallback=None,
            filecallback=None,
            estimatecallback=None,
            _start=OnStart,
            _message=OnMessage,
            _end=OnEnd,
            _info=self.frame.infopanel.MakeRow("Adding %s" % dir),
        )

    def on_generate_database(self, evt):
        """Handle Generate Database button click.

        Args:
            evt: Button click event
        """
        # Collect format strings from GUI (fast operation)
        format_strings = {}
        for field in FORMATTED_TAGS:
            format_str = self.frame.__dict__[field.replace(" ", "")].GetValue()
            sort_str = self.frame.__dict__[field.replace(" ", "") + "_sort"].GetValue()
            format_strings[field] = (format_str, sort_str)

        # Create info panel and show immediate status
        info = self.frame.infopanel.MakeRow("Generating database")
        info.status = "Starting..."
        info.timer.Start()

        # Force GUI to update immediately
        wx.Yield()

        def OnStart(evt):
            evt.info.status = "Compiling format strings..."

        def OnMessage(evt):
            if isinstance(evt.message, str) and evt.message.startswith("READY:"):
                # Format strings compiled, now set the range for file processing
                count = int(evt.message.split(":")[1])
                evt.info.SetRange(count)
                evt.info.gauge = 0
                evt.info.status = "Processing files..."
            elif isinstance(evt.message, int):
                # Integer message - set range or update gauge
                evt.info.SetRange(evt.message)
                evt.info.gauge = 0
            else:
                # String message - update status
                evt.info.status = str(evt.message)
                evt.info.gauge += 1

        def OnEnd(evt):
            evt.info.timer.Stop()
            evt.info.gauge = evt.info.gauge_ctrl.GetRange()  # Set to maximum
            evt.info.status = "Done"
            # Force the InfoPanel to re-layout and repaint immediately
            evt.info.parent.Layout()
            evt.info.parent.Refresh()
            DatabaseEvent.post_updated(self.frame.panes, self.frame.database)

        def worker_generate_database(format_strings, callback=None):
            # Compile format strings in worker thread (may be slow)
            for field, (format_str, sort_str) in format_strings.items():
                self.frame.database.set_format(field, format_str, sort_str)

            # Signal that we're ready to process files
            if callback:
                callback(f"READY:{len(self.frame.database.paths)}")

            # Now generate the database
            self.frame.database.generate_database(callback=callback)

        self.frame.threading_support.start_thread(
            worker_generate_database,
            format_strings,
            callback=None,
            _start=OnStart,
            _message=OnMessage,
            _end=OnEnd,
            _info=info,
        )

    def on_write_database(self, evt):
        """Handle Write Database button click.

        Args:
            evt: Button click event
        """
        default_dir = self.frame.config.get_last_output_dir()
        write_dir = wx.DirSelector(
            "Database Output Directory", default_path=default_dir or ""
        )
        if not write_dir:
            return

        # Validate directory path
        is_valid, error_msg = validate_path(write_dir, must_exist=False)
        if not is_valid:
            show_error_dialog(self.frame, "Invalid Directory Path", error_msg)
            return

        # Create directory if it doesn't exist
        try:
            Path(write_dir).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            show_error_dialog(
                self.frame,
                "Directory Creation Failed",
                f"Could not create directory: {e}",
            )
            return

        # Save to config
        self.frame.config.set_last_output_dir(write_dir)
        self.frame.config.save()

        def OnStart(evt):
            evt.info.timer.Start()
            evt.info.SetRange(9)

        def OnMessage(evt):
            if evt.message == "done":
                evt.info.gauge += 1
            else:
                evt.info.status = evt.message

        def OnEnd(evt):
            evt.info.timer.Stop()
            evt.info.gauge = evt.info.gauge_ctrl.GetRange()  # Set to maximum
            evt.info.status = "Done"
            # Force the InfoPanel to re-layout and repaint immediately
            evt.info.parent.Layout()
            evt.info.parent.Refresh()
            DatabaseEvent.post_updated(self.frame.panes, self.frame.database)

        self.frame.threading_support.start_thread(
            self.frame.database.write,
            write_dir,
            callback=None,
            _start=OnStart,
            _message=OnMessage,
            _end=OnEnd,
            _info=self.frame.infopanel.MakeRow("Writing database"),
        )

    def on_read_database(self, evt):
        """Handle Read Database button click.

        Args:
            evt: Button click event
        """
        default_dir = self.frame.config.get_last_output_dir()
        read_dir = wx.DirSelector("Database Directory", default_path=default_dir or "")
        if not read_dir:
            return

        # Validate directory path
        is_valid, error_msg = validate_path(read_dir, must_exist=True)
        if not is_valid:
            show_error_dialog(self.frame, "Invalid Directory Path", error_msg)
            return

        # Save to config
        self.frame.config.set_last_output_dir(read_dir)
        self.frame.config.save()

        def OnStart(evt):
            evt.info.timer.Start()
            evt.info.SetRange(9)

        def OnMessage(evt):
            if evt.message == "done":
                evt.info.gauge += 1
            else:
                evt.info.status = evt.message

        def OnEnd(evt):
            evt.info.timer.Stop()
            evt.info.gauge = evt.info.gauge_ctrl.GetRange()  # Set to maximum
            evt.info.status = "Done"
            # Force the InfoPanel to re-layout and repaint immediately
            evt.info.parent.Layout()
            evt.info.parent.Refresh()
            DatabaseEvent.post_updated(self.frame.panes, self.frame.database)

        def read_database(directory, callback=None):
            self.frame.database = Database.read(directory, callback)

        self.frame.threading_support.start_thread(
            read_database,
            read_dir,
            callback=None,
            _start=OnStart,
            _message=OnMessage,
            _end=OnEnd,
            _info=self.frame.infopanel.MakeRow("Reading database"),
        )
