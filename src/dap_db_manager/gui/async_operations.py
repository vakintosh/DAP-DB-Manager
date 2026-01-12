"""Async I/O operations for GUI to prevent blocking.

This module provides async wrappers for database operations with support for:
- Non-blocking execution
- Progress reporting
- Cancellation
- Error handling

Note: This module requires wxPython. It should only be imported when
wxPython is available (checked via gui.__init__.is_wxpython_available()).
"""

import asyncio
import threading
from typing import Callable, Optional, Any, Coroutine
from concurrent.futures import ThreadPoolExecutor
import functools

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e


class AsyncOperation:
    """Represents an async operation with cancellation support."""

    def __init__(self, name: str):
        """Initialize async operation.

        Args:
            name: Human-readable name for this operation
        """
        self.name = name
        self._cancelled = False
        self._task: Optional[asyncio.Task] = None

    def cancel(self) -> None:
        """Cancel the operation."""
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()

    def is_cancelled(self) -> bool:
        """Check if operation was cancelled."""
        return self._cancelled

    def set_task(self, task: asyncio.Task) -> None:
        """Set the asyncio task for this operation."""
        self._task = task


class AsyncIOSupport:
    """Provides async I/O support for GUI operations."""

    def __init__(self, frame):
        """Initialize async I/O support.

        Args:
            frame: The wxPython frame
        """
        self.frame = frame
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._operations: dict[str, AsyncOperation] = {}
        self._start_event_loop()

    def _start_event_loop(self) -> None:
        """Start the asyncio event loop in a background thread."""

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            threading.Event().wait(0.01)

    def shutdown(self) -> None:
        """Shutdown the async support and cleanup resources."""
        # Cancel all pending operations
        for operation in list(self._operations.values()):
            operation.cancel()
        self._operations.clear()

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=False)

        # Stop event loop
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
            # Give loop time to stop gracefully
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=1.0)

    async def run_in_executor(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run a blocking function in the thread pool executor.

        Args:
            func: The blocking function to run
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            The result of func
        """
        loop = asyncio.get_event_loop()
        bound_func = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(self._executor, bound_func)

    def run_async(
        self,
        coro: Coroutine,
        operation_id: Optional[str] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
    ) -> AsyncOperation:
        """Run an async coroutine and integrate with wxPython.

        Args:
            coro: The coroutine to run
            operation_id: Optional unique ID for this operation
            on_complete: Callback when operation completes successfully
            on_error: Callback when operation raises an exception
            on_progress: Callback for progress updates

        Returns:
            AsyncOperation object that can be used to cancel
        """
        if operation_id is None:
            operation_id = f"op_{id(coro)}"

        operation = AsyncOperation(operation_id)
        self._operations[operation_id] = operation

        async def wrapper():
            try:
                result = await coro
                if not operation.is_cancelled() and on_complete:
                    wx.CallAfter(on_complete, result)
                return result
            except asyncio.CancelledError:
                # Operation was cancelled
                pass
            except Exception as e:
                if not operation.is_cancelled() and on_error:
                    wx.CallAfter(on_error, e)
                raise
            finally:
                # Cleanup
                if operation_id in self._operations:
                    del self._operations[operation_id]

        # Schedule in the event loop
        if self._loop is None:
            raise RuntimeError("Event loop is not running")
        future = asyncio.run_coroutine_threadsafe(wrapper(), self._loop)
        task = asyncio.wrap_future(future, loop=self._loop)
        operation.set_task(task)  # type: ignore[arg-type]

        return operation

    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel an operation by its ID.

        Args:
            operation_id: The ID of the operation to cancel

        Returns:
            True if operation was found and cancelled, False otherwise
        """
        operation = self._operations.get(operation_id)
        if operation:
            operation.cancel()
            return True
        return False

    def cancel_all(self) -> None:
        """Cancel all running operations."""
        for operation in list(self._operations.values()):
            operation.cancel()


class AsyncDatabaseOperations:
    """Async wrappers for database operations."""

    def __init__(self, database, async_support: AsyncIOSupport):
        """Initialize async database operations.

        Args:
            database: The Database instance
            async_support: AsyncIOSupport instance
        """
        self.database = database
        self.async_support = async_support

    async def add_directory_async(
        self,
        path: str,
        recursive: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> tuple[set, list]:
        """Add a directory of music files asynchronously.

        Args:
            path: Directory path to scan
            recursive: Whether to scan recursively
            progress_callback: Callback for progress updates

        Returns:
            Tuple of (paths_set, failed_list)
        """

        def wrapper():
            return self.database.add_dir(
                path,
                recursive=recursive,
                dircallback=progress_callback,
                filecallback=progress_callback,
                estimatecallback=progress_callback,
            )

        return await self.async_support.run_in_executor(wrapper)  # type: ignore[no-any-return]

    async def generate_database_async(
        self, progress_callback: Optional[Callable] = None
    ) -> None:
        """Generate database asynchronously.

        Args:
            progress_callback: Callback for progress updates
        """

        def wrapper():
            return self.database.generate_database(callback=progress_callback)

        return await self.async_support.run_in_executor(wrapper)  # type: ignore[no-any-return]

    async def write_database_async(
        self, out_dir: str, progress_callback: Optional[Callable] = None
    ) -> None:
        """Write database to disk asynchronously.

        Args:
            out_dir: Output directory path
            progress_callback: Callback for progress updates
        """

        def wrapper():
            return self.database.write(out_dir, callback=progress_callback)

        return await self.async_support.run_in_executor(wrapper)  # type: ignore[no-any-return]

    async def read_database_async(
        self, in_dir: str, progress_callback: Optional[Callable] = None
    ) -> Any:
        """Read database from disk asynchronously.

        Args:
            in_dir: Input directory path
            progress_callback: Callback for progress updates

        Returns:
            The loaded Database instance
        """
        from ..database import Database

        def wrapper():
            if progress_callback is None:
                return Database.read(in_dir)
            return Database.read(in_dir, callback=progress_callback)

        return await self.async_support.run_in_executor(wrapper)

    async def load_tags_async(
        self, path: str, progress_callback: Optional[Callable] = None
    ) -> None:
        """Load tags from cache file asynchronously.

        Args:
            path: Path to cache file
            progress_callback: Callback for progress updates
        """

        def wrapper():
            return self.database.load_tags(path, callback=progress_callback)

        return await self.async_support.run_in_executor(wrapper)  # type: ignore[no-any-return]

    async def save_tags_async(
        self, path: str, progress_callback: Optional[Callable] = None
    ) -> tuple:
        """Save tags to cache file asynchronously.

        Args:
            path: Path to cache file
            progress_callback: Callback for progress updates

        Returns:
            Tuple of (paths, failed)
        """

        def wrapper():
            return self.database.save_tags(path, callback=progress_callback)

        return await self.async_support.run_in_executor(wrapper)  # type: ignore[no-any-return]


def create_progress_callback(info_panel_row, update_status: bool = True) -> Callable:
    """Create a thread-safe progress callback for async operations.

    Args:
        info_panel_row: The info panel row to update
        update_status: Whether to update status text

    Returns:
        A callback function that can be used with async operations
    """

    def callback(message):
        def update():
            if isinstance(message, int):
                info_panel_row.SetRange(message)
                info_panel_row.gauge = 0
            elif isinstance(message, str):
                if update_status:
                    info_panel_row.status = message
                info_panel_row.gauge += 1

        wx.CallAfter(update)

    return callback
