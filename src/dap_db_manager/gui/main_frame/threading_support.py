"""Threading support for background operations in the main frame.

This module provides the infrastructure for running database operations
in background threads while keeping the GUI responsive.

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

import sys
import threading
import traceback
from typing import Callable, Optional, Any, Dict

from ..error_handling import show_error_dialog
from ..thread_events import ThreadEvent

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e


class CancellableThread(threading.Thread):
    """A thread that can be cancelled."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        """Request the thread to stop."""
        self._stop_event.set()

    def is_stopped(self) -> bool:
        """Check if thread was requested to stop."""
        return self._stop_event.is_set()


class ThreadingSupport:
    """Handles threading operations for the main frame."""

    def __init__(self, frame):
        """Initialize threading support.

        Args:
            frame: The MyFrame instance
        """
        self.frame = frame
        self._active_threads: Dict[str, CancellableThread] = {}
        self._thread_lock = threading.Lock()

    def cancel_thread(self, thread_id: str) -> bool:
        """Cancel a running thread by its ID.

        Args:
            thread_id: The ID of the thread to cancel

        Returns:
            True if thread was found and cancelled, False otherwise
        """
        with self._thread_lock:
            thread = self._active_threads.get(thread_id)
            if thread:
                thread.stop()
                return True
            return False

    def cancel_all_threads(self) -> None:
        """Cancel all running threads."""
        with self._thread_lock:
            for thread in self._active_threads.values():
                thread.stop()

    def cleanup(self, wait: bool = True, timeout: float = 2.0) -> None:
        """Cleanup all threads and wait for them to finish.

        Args:
            wait: If True, wait for threads to complete
            timeout: Maximum time to wait for each thread in seconds
        """
        self.cancel_all_threads()

        if wait:
            with self._thread_lock:
                threads_to_join = list(self._active_threads.values())

            # Join threads outside the lock to avoid deadlock
            for thread in threads_to_join:
                if thread.is_alive():
                    thread.join(timeout=timeout)

            # Clear the dictionary
            with self._thread_lock:
                self._active_threads.clear()

    def start_thread(
        self, func: Callable, *args: Any, thread_id: Optional[str] = None, **kwargs: Any
    ) -> str:
        """Execute a func with *args and **kwargs in a new thread.

        Event handlers can be bound as kwargs using the keys:
            _start: Called when thread starts
            _message: Called for progress updates
            _end: Called when thread completes

        An Info object that will be passed to the event handlers can be
        specified with the kwarg '_info'

        Args:
            func: The function to execute in the thread
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func (special keys prefixed with _ are intercepted)
        """
        # Extract the event handler functions from kwargs, and remove them,
        # so they aren't passed to func
        end_handler: Callable = kwargs.pop("_end", lambda evt: None)
        start_handler: Optional[Callable] = kwargs.pop("_start", None)
        msg_handler: Optional[Callable] = kwargs.pop("_message", None)
        info = kwargs.pop("_info", None)

        if info is not None:
            self.frame.thread_info.append(info)

        # Worker function that will be called in the thread
        def worker(thread_obj: CancellableThread) -> None:
            try:
                # Post start event if handler provided
                if start_handler:
                    ThreadEvent.post_start(self.frame, start_handler, info)

                # Replace the callback with one that knows its handler and can check cancellation
                if msg_handler:

                    def thread_callback(*args, **kwargs):
                        # Check if thread should stop
                        if thread_obj.is_stopped():
                            raise InterruptedError("Operation cancelled by user")
                        # Handle both single message and multiple arguments
                        if len(args) == 1:
                            ThreadEvent.post_callback(
                                self.frame, msg_handler, info, args[0]
                            )
                        else:
                            # Multiple arguments - just use first one as message
                            ThreadEvent.post_callback(
                                self.frame, msg_handler, info, args[0] if args else None
                            )

                    # Update all callback types in kwargs if present
                    if "callback" in kwargs:
                        kwargs["callback"] = thread_callback
                    if "dircallback" in kwargs:
                        kwargs["dircallback"] = thread_callback
                    if "filecallback" in kwargs:
                        kwargs["filecallback"] = thread_callback
                    if "estimatecallback" in kwargs:
                        kwargs["estimatecallback"] = thread_callback

                # Execute the actual function
                func(*args, **kwargs)

                # Post end event
                ThreadEvent.post_end(self.frame, end_handler, info)

            except InterruptedError:
                # Operation was cancelled
                if info:
                    wx.CallAfter(lambda: setattr(info, "status", "Cancelled"))
            except SystemExit:
                # Allow clean thread termination
                pass
            except Exception as e:
                # Catch any unexpected errors
                error_details = traceback.format_exc()
                print(f"Thread error: {e}", file=sys.stderr)
                print(error_details, file=sys.stderr)
                # Show error dialog to user
                wx.CallAfter(
                    show_error_dialog, self.frame, "Thread Error", str(e), error_details
                )
            finally:
                # Remove from active threads
                with self._thread_lock:
                    if thread_id in self._active_threads:
                        del self._active_threads[thread_id]

        # Create and start the cancellable thread
        thread: CancellableThread = CancellableThread(
            target=lambda: worker(thread), daemon=True
        )

        # Register thread
        with self._thread_lock:
            if thread_id is not None:
                self._active_threads[thread_id] = thread

        thread.start()
        return thread_id if thread_id is not None else ""
