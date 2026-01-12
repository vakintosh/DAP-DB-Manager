"""Callback classes and functions for database operations."""

import logging
from pathlib import Path


def log_callback(message, **kwargs):
    """Callback function for database operations that logs instead of printing."""
    if isinstance(message, int):
        # Progress indicator (number of items)
        logging.info("Processing %s items...", message)
    else:
        # Ignore 'end' parameter - logging handles line endings
        logging.debug("%s", message)


class ProgressCallback:
    """Callback that updates a rich progress bar."""

    def __init__(self, progress, task_id):
        self.progress = progress
        self.task_id = task_id
        self.count = 0
        self.last_dir = None

    def __call__(self, message):
        if isinstance(message, str):
            path_obj = Path(message)
            if path_obj.is_dir():
                self.last_dir = path_obj.name
                self.count = 0
                self.progress.update(
                    self.task_id, description=f"[cyan]Scanning: {self.last_dir}..."
                )
            else:
                self.count += 1
                self.progress.advance(self.task_id, 1)
        elif isinstance(message, int):
            # Update total for progress bar
            self.progress.update(self.task_id, total=message)


class SilentCallback:
    """Callback that counts operations without printing."""

    def __init__(self):
        self.count = 0
        self.last_dir = None

    def __call__(self, message):
        if isinstance(message, str):
            if Path(message).is_dir():
                self.last_dir = message
                self.count = 0
            else:
                self.count += 1
                if self.count % 100 == 0:
                    logging.info(
                        "Processed %s files from %s", self.count, self.last_dir
                    )
