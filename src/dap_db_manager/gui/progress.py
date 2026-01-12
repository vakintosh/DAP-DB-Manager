"""Progress callback optimization utilities.

This module provides helpers to throttle progress callbacks, reducing GUI
overhead and improving performance when processing large numbers of files.
"""

import time
from typing import Callable, Optional, Any


class ProgressThrottle:
    """Throttle progress callbacks to reduce overhead.

    Batches progress updates to avoid calling the callback too frequently,
    which can cause GUI slowdowns when processing thousands of files.

    Example:
        >>> def my_callback(msg):
        ...     print(msg)
        >>> throttled = ProgressThrottle(my_callback, update_interval=10)
        >>> for i in range(100):
        ...     throttled(f"Processing file {i}")  # Only updates every 10 calls
        >>> throttled.flush()  # Force final update
    """

    def __init__(
        self,
        callback: Callable,
        update_interval: int = 10,
        time_interval: Optional[float] = None,
    ):
        """Initialize progress throttle.

        Args:
            callback: The actual callback function to call
            update_interval: Update every N calls (default: 10)
            time_interval: Optional minimum time in seconds between updates.
                         If provided, uses time-based throttling instead.
        """
        self.callback = callback
        self.update_interval = update_interval
        self.time_interval = time_interval
        self.count = 0
        self.last_update = 0
        self.last_update_time = 0.0
        self.last_message: tuple[Any, dict[str, Any]] | None = None

    def __call__(self, message: Any, **kwargs) -> None:
        """Call with a progress message.

        Args:
            message: The message to pass to the callback
            **kwargs: Additional keyword arguments for the callback
        """
        self.count += 1
        self.last_message = (message, kwargs)

        should_update = False

        if self.time_interval is not None:
            # Time-based throttling
            current_time = time.time()
            if current_time - self.last_update_time >= self.time_interval:
                should_update = True
                self.last_update_time = current_time
        else:
            # Count-based throttling
            if self.count - self.last_update >= self.update_interval:
                should_update = True
                self.last_update = self.count

        if should_update:
            self.callback(message, **kwargs)

    def flush(self) -> None:
        """Force an update with the last message received.

        Call this at the end of processing to ensure the final state is shown.
        """
        if self.last_message is not None:
            message, kwargs = self.last_message
            self.callback(message, **kwargs)
            self.last_message = None


class BatchProgressCallback:
    """Batch multiple progress updates into a single callback.

    Useful for operations that process many small items quickly.
    Instead of calling the callback for each item, accumulates a count
    and calls the callback with batch information.

    Example:
        >>> def my_callback(msg):
        ...     print(msg)
        >>> batch = BatchProgressCallback(my_callback, batch_size=100)
        >>> for i in range(1000):
        ...     batch.increment()
        >>> batch.finish()
        Processed 100 items...
        Processed 200 items...
        ...
        Processed 1000 items (complete)
    """

    def __init__(
        self,
        callback: Callable,
        batch_size: int = 100,
        message_template: str = "Processed {count} items...",
    ):
        """Initialize batch progress callback.

        Args:
            callback: The callback function to call
            batch_size: Number of items to accumulate before calling callback
            message_template: Template string with {count} placeholder
        """
        self.callback = callback
        self.batch_size = batch_size
        self.message_template = message_template
        self.count = 0

    def increment(self, amount: int = 1) -> None:
        """Increment the count and possibly call the callback.

        Args:
            amount: Amount to increment by (default: 1)
        """
        self.count += amount
        if self.count % self.batch_size == 0:
            self.callback(self.message_template.format(count=self.count))

    def finish(self) -> None:
        """Call the callback with final count."""
        if self.count % self.batch_size != 0:
            self.callback(
                self.message_template.format(count=self.count) + " (complete)"
            )


def create_throttled_callback(
    callback: Optional[Callable],
    throttle_interval: int = 10,
    use_time: bool = False,
    time_interval: float = 0.1,
) -> Callable:
    """Create a throttled version of a callback function.

    Convenience function to create a ProgressThrottle instance.

    Args:
        callback: The callback to throttle. If None, returns a no-op function.
        throttle_interval: Update every N calls (default: 10)
        use_time: Use time-based throttling instead of count-based
        time_interval: Time interval in seconds if use_time is True (default: 0.1)

    Returns:
        A throttled callback function with a flush() method

    Example:
        >>> def my_callback(msg):
        ...     print(msg)
        >>> throttled = create_throttled_callback(my_callback, throttle_interval=50)
        >>> for i in range(1000):
        ...     throttled(f"File {i}")
        >>> throttled.flush()
    """
    if callback is None:

        class NoOp:
            def __call__(self, *args, **kwargs):
                pass

            def flush(self):
                pass

        return NoOp()

    return ProgressThrottle(
        callback,
        update_interval=throttle_interval,
        time_interval=time_interval if use_time else None,
    )
