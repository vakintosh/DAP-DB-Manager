# Chapter 7 — The GUI Layer: Events, Threads, and Not Freezing the Window

> **Who this is for:** you've read Chapter 0 (Python basics, including the
> threading-basics section, classes/OOP, and decorators) and Chapter 1
> (project architecture — you know the GUI is "just another front end" over
> the same `database/` engine the CLI uses). This chapter does not re-teach
> variables, classes, or what a thread *is* in general — it teaches the
> specific vocabulary and patterns of **event-driven GUI programming**, which
> Chapter 0 didn't cover at all, and shows you exactly how this project keeps
> its window responsive while a multi-minute database build runs underneath.
>
> **How to use it:** open the files as you read. This chapter quotes real
> code throughout — don't take the quotes at face value, go look at the
> surrounding lines too.

---

## 7.1 A new way of thinking: event-driven programming

Every program you've looked at so far in this project — the CLI commands —
runs **top to bottom**. You type `ddm generate ...`, the `generate` command
function runs, and when it returns, the program exits. There's a clear
beginning, middle, and end, and your code is always "in charge": it decides
what happens next.

A GUI application works completely differently. Once the window appears, a
GUI program spends almost all of its life sitting inside something called
an **event loop** — a loop, buried inside the wxPython library, that does
roughly this (pseudocode, not real code):

```
while window is open:
    wait for something to happen (a click, a keypress, a timer tick, ...)
    figure out which widget that "something" happened to
    call the function you registered for that widget + that kind of event
    go back to waiting
```

You never write that loop yourself — `app.MainLoop()` (section 7.2) runs
it for you. Your job, as the application author, is only to say: "**when**
this specific thing happens, **call** this specific function." Those
functions are called **event handlers** (sometimes "callbacks" — a term you
already saw in Chapter 1 for CLI progress reporting, and it means the same
thing here: a function you hand to someone else, that they call later, on
their own schedule, not yours).

This is the single most important mental shift for this chapter:

> **In an event-driven program, nothing happens unless something triggers
> an event.** Your code doesn't run in a predictable sequence — it runs in
> little bursts, each one triggered by the user (or a timer, or a
> background thread) poking the event loop.

The mechanism for saying "when event X happens on widget W, call function
F" is called **binding**. You'll see it everywhere in this chapter as
`widget.Bind(EVENT_TYPE, self.handler_method)`. Binding doesn't *call*
`self.handler_method` immediately — it just registers it, the same way
Chapter 0's functions-as-values idea let you pass a function around without
calling it. The event loop calls it later, whenever that event actually
occurs.

Keep this picture in your head as you read the rest of the chapter: **a
window sitting idle, waiting, and a scattering of small handler methods
that each wake up, do a little work, and return control back to the loop.**

---

## 7.2 `app.py`: the application object and `MainLoop()`

`gui/app.py` is the smallest file in this chapter, and it's where the event
loop actually gets started:

```python
import sys

try:
    import wx
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e

from .main_frame import MyFrame
from ..config import Config
from ..database.cache import TagCache


class MyApp(wx.App):
    """Main wxPython application class."""

    def OnInit(self) -> bool:
        """Initialize the application.

        Returns:
            True if initialization succeeded
        """
        self.frame = MyFrame(None)
        return True
```

New things here, beyond Chapter 0:

- **`wxPython`** is the library this entire chapter is about: a set of
  Python bindings around `wxWidgets`, a cross-platform C++ GUI toolkit.
  It gives you ready-made building blocks — windows (`wx.Frame`),
  buttons (`wx.Button`), text boxes, progress bars (`wx.Gauge`), menus,
  dialogs — plus the event loop machinery described in 7.1. It's an
  **optional dependency** (see the `try/except ImportError` at the top,
  and recall Chapter 1's note that `pyproject.toml` lists `wxpython` only
  under `[project.optional-dependencies]`) — the CLI works fine without
  it ever being installed.
- `class MyApp(wx.App):` — this class **inherits from** `wx.App`
  (Chapter 0 covered inheritance with `Dog(Animal)`). `wx.App` is the
  object that represents "the whole running application" — there's
  exactly one of these per program, and it owns the event loop.
- `def OnInit(self) -> bool:` is an example of something new: a method
  whose *name* matters to the framework, not just to your own code.
  `wx.App` calls `OnInit()` itself, at a specific point during startup,
  because that's the contract the wxPython library defines for every
  subclass of `wx.App`. You never call `OnInit()` yourself — this is the
  same "the framework calls you, not the other way around" idea from 7.1,
  just applied to application startup instead of a button click.
  Returning `True` tells wxPython "initialization succeeded, keep going."
- `self.frame = MyFrame(None)` creates the main window. We'll look inside
  `MyFrame` in section 7.3. Passing `None` as the parent means "this is a
  top-level window with no parent window" — standard for a main frame.

```python
def main():
    """Main entry point for the DAP DB Manager GUI."""
    # Initialize cache configuration from user settings
    config = Config()
    TagCache.set_max_cache_memory(config.get_tag_cache_memory())

    app = MyApp(redirect=False)
    app.MainLoop()
    # Kill any remaining threads before we're done.
    sys.exit()
```

This is the function that actually runs when you type `dap-db-manager` at
a terminal (it's registered as that command's entry point). Three things
worth calling out:

- `app = MyApp(redirect=False)` constructs the application object. Since
  `MyApp` doesn't define its own `__init__`, this calls `wx.App.__init__`
  (Chapter 0's inheritance rules: a subclass without its own `__init__`
  uses the parent's), which under the hood calls `OnInit()` for you.
  `redirect=False` tells wxPython *not* to redirect `print()` output into
  a pop-up window (its old default behavior on some platforms) — print
  statements go to your normal terminal instead, which is much friendlier
  for debugging.
- **`app.MainLoop()` is the event loop from section 7.1, made real.**
  This single call doesn't return until the user closes the window. Every
  button click, every keystroke, every timer tick you'll see handled in
  this chapter happens *during* this one line of code, dispatched out to
  your handler methods and back.
- `sys.exit()` after `MainLoop()` returns forces the process to actually
  terminate, cleaning up any background threads that might otherwise keep
  the Python process alive (more on why background threads exist at all
  in section 7.4).

---

## 7.3 `main_frame/frame.py`: building the main window

`gui/main_frame/frame.py` defines `MyFrame`, the main window class that
`app.py` instantiates. Before reading the handwritten part, notice the
import:

```python
from .. import wxFB_gui
...
class MyFrame(wxFB_gui.Frame):
```

**A brief note on `wxFB_gui.py`:** this file is machine-generated by
**wxFormBuilder**, a drag-and-drop GUI design tool — its header literally
says `"PLEASE DO NOT EDIT THIS FILE!"`. It defines a `Frame` base class
containing nothing but widget *construction* — creating every button, text
box, notebook tab, and sizer (a wxPython layout-management object that
arranges widgets automatically) and giving them attribute names like
`self.m_button6` or `self.notebook`. You don't need to read it
line-by-line; think of it as the "blueprint" for what the window *looks
like*, generated visually rather than typed by hand. `MyFrame` inherits
from it and adds all the *behavior* — what happens when you click those
buttons — which is the handwritten part this chapter actually teaches.

Now, `MyFrame.__init__`:

```python
class MyFrame(wxFB_gui.Frame):
    def __init__(self, parent):
        wxFB_gui.Frame.__init__(self, parent)

        # Initialize component managers
        self.format_manager = FormatManager(self)
        self.threading_support = ThreadingSupport(self)
        self.thread_handlers = ThreadHandlers(self)
        self.db_operations = DatabaseOperations(self)

        # Bind thread events to handlers
        self.Bind(EVT_THREAD_START, self.thread_handlers.on_thread_start)
        self.Bind(EVT_THREAD_CALLBACK, self.thread_handlers.on_thread_message)
        self.Bind(EVT_THREAD_END, self.thread_handlers.on_thread_end)
```

- `wxFB_gui.Frame.__init__(self, parent)` explicitly calls the generated
  base class's constructor first — this is what actually builds every
  widget (buttons, text fields, the notebook) before any of the custom
  code below touches them. (Chapter 0 covered calling a parent's method
  explicitly like this as an alternative to `super()`.)
- The four `self.X_manager = SomeClass(self)` lines are an example of
  **composition over inheritance**: rather than cramming every
  responsibility (format strings, threading, database button clicks) into
  one giant `MyFrame` class, the authors split it into four small
  collaborator objects, each holding a reference back to `self` (the
  frame) so it can reach widgets and shared state. This is why the file
  list for this chapter has a `main_frame/` *folder*, not one big file —
  it's the GUI's version of the "keep core logic separate from how it's
  triggered" principle from Chapter 1, applied *within* the GUI itself:
  format-string logic doesn't need to know about threads, and thread
  coordination doesn't need to know about format strings.
- The three `self.Bind(EVT_THREAD_..., ...)` calls are the binding
  mechanism from section 7.1, but note something new: `EVT_THREAD_START`
  etc. are not built-in wxPython events like a button click — they are
  **custom events this project defines itself**, for passing information
  from a background thread back to the GUI. That's the whole subject of
  section 7.4 — hold that thought.

Further down `__init__`, you can see ordinary window setup, all still
inside `__init__` so it happens once, before the window is shown:

```python
        # Setup field panes
        self.panes = FieldPanePanel(self.notebook)
        self.notebook.AddPage(self.panes, "View")
        self.status.SetStatusWidths([200, -1])

        # Hide Save Tags and Load Tags buttons
        self.m_button6.Hide()  # Save Tags button
        self.m_button61.Hide()  # Load Tags button

        # Insert the info panel into the sizer
        self.infopanel = InfoPanel(self.mainpanel)
        self.mainpanel.GetSizer().Insert(0, self.infopanel, 1, wx.ALL | wx.EXPAND, 5)
        self.mainpanel.Layout()

        # Initialize database
        self.database = Database()

        # List of currently running info panels
        self.thread_info = []
```

`self.m_button6` and `self.m_button61` are exactly the kind of
auto-generated attribute names `wxFB_gui.py` creates — not very readable,
but that's the cost of a visually-designed form; the comments
(`# Save Tags button`) exist specifically to compensate for that.
`self.database = Database()` is the single `Database` object (from
`database/`, Chapter 1's engine) that every button handler in this window
will operate on — this is the concrete "Model" in a loose
Model-View-ish split: `self.database` is the data/engine (the Model),
`MyFrame` and its widgets are the View, and the various `*_operations`
/ `*_handlers` helper classes act as a thin Controller layer translating
GUI events into Model calls and Model results back into View updates.

Near the end of `__init__`:

```python
        self.Show()

        self.Bind(wx.EVT_CLOSE, self.OnClose)
```

`self.Show()` makes the window actually visible — before this, it exists
in memory but nothing is drawn on screen. `wx.EVT_CLOSE` is a built-in
wxPython event fired when the user tries to close the window (clicking
the X, Alt+F4, Cmd+Q, etc.); binding it to `self.OnClose` lets the app
clean up before actually exiting — we'll look at what it cleans up in
7.4, after you understand *why* there's cleanup to do.

Finally, notice the thin delegating handlers near the bottom of the class:

```python
    def OnGenerateDatabase(self, evt):
        """Handle Generate Database button click."""
        self.db_operations.on_generate_database(evt)
```

`evt` here is the **event object** wxPython passes into every handler —
it carries details about what happened (which button, mouse position,
etc., depending on the event type). `OnGenerateDatabase` is bound
(somewhere in the generated `wxFB_gui.Frame.__init__`) to the "Generate
Database" button's click event; when clicked, wxPython calls this method
with the click event, and it immediately hands off to
`self.db_operations.on_generate_database(evt)` — the real logic lives in
`database_operations.py` (section 7.5), keeping `frame.py` itself focused
on window *structure*, not business logic. This is the same composition
pattern as the four manager objects above, just visible at the
handler-method level too.

---

## 7.4 Why you can't just do slow work in a button handler

Here's the problem this whole chapter exists to solve. Imagine
`OnGenerateDatabase` looked like this instead (it doesn't — this is a
"bad version" for illustration):

```python
def OnGenerateDatabase(self, evt):
    self.database.generate_database()   # could take minutes!
```

Remember section 7.1: **the event loop is a single loop**, and your
handler runs *inside* one iteration of it. While `generate_database()` is
running — reading thousands of audio files' tags, which the README says
can take minutes even on a fast PC — the event loop is stuck waiting for
your handler to return. It can't process the next event. That means:

- The window can't repaint itself (drag another window over it, and
  you'll see a gray rectangle where it used to be).
- Clicking Cancel, moving the window, or clicking anything else does
  nothing — the OS calls this "Application Not Responding" / "spinning
  beachball," and users reasonably assume the program crashed.

This is what people mean by **"blocking the GUI thread" (or "main
thread")** — and it's a direct consequence of event-driven programming:
if your handler never returns, the loop that's supposed to call the
*next* handler never gets to run.

Chapter 0 already introduced **threads** in the abstract: multiple
independent sequences of execution inside one process. The GUI's fix for
the freeze is exactly that idea, applied concretely: **run the slow work
on a separate (background) thread, and let the main thread keep running
the event loop** so the window stays responsive. "**Async operations in a
GUI**" is the general name for this pattern — "async" here just means
"happening independently of, and not blocking, the main sequence of
events," not necessarily Python's `asyncio` specifically (though, as
you'll see, this codebase actually uses *both*: real OS threads for most
operations, and an `asyncio` event loop running inside one dedicated
background thread for a more advanced async layer).

But moving the work to a background thread creates a brand-new problem,
and it's the second half of this chapter's real teaching value:

> **wxPython (like almost every GUI toolkit) is not thread-safe: you must
> only touch widgets from the main/GUI thread.** Calling
> `some_button.SetLabel("Done")` directly from a background thread is
> undefined behavior — it might work by luck, or it might corrupt the
> widget, crash, or silently do nothing, depending on timing and
> platform.

So the real design challenge isn't just "run this on a thread" — it's
**how does a background thread safely tell the GUI thread "update this
progress bar" or "I'm done" without ever touching a widget itself?** The
rest of this chapter (`threading_support.py`, `thread_events.py`,
`thread_handlers.py`, `async_operations.py`) is this project's answer to
exactly that question.

### `main_frame/threading_support.py`: starting and tracking background work

```python
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
```

`class CancellableThread(threading.Thread):` subclasses Python's built-in
`threading.Thread` (Chapter 0 introduced `threading.Thread` and
`threading.Event`) to add cancellation support. `threading.Event` is a
simple thread-safe flag with two states — `set()` and `clear()` — that any
thread can read (`is_set()`) or write (`set()`) safely, without the race
conditions you'd get doing the same thing with a plain `bool` variable
shared between threads. `stop()` just flips the flag; `is_stopped()`
reads it. Crucially, **this doesn't forcibly kill anything** — Python
gives you no safe way to force-terminate a running thread mid-instruction
(doing so could leave shared data half-updated). This is a
**cooperative** cancellation flag: the running code has to periodically
check `is_stopped()` itself and *choose* to stop. You'll see exactly where
that check happens below.

```python
class ThreadingSupport:
    """Handles threading operations for the main frame."""

    def __init__(self, frame):
        self.frame = frame
        self._active_threads: Dict[str, CancellableThread] = {}
        self._thread_lock = threading.Lock()
```

`self._thread_lock = threading.Lock()` is Chapter 0's mutual-exclusion
lock: since multiple threads (the GUI thread calling `cancel_thread`, a
worker thread finishing and removing itself) can touch
`self._active_threads` at the same time, every read/modify of that
dictionary below is wrapped in `with self._thread_lock:` to make sure only
one thread touches it at once.

Now the important method, `start_thread`, shown here with the parts that
matter most for the teaching point, read top to bottom:

```python
    def start_thread(
        self, func: Callable, *args: Any, thread_id: Optional[str] = None, **kwargs: Any
    ) -> str:
        """Execute a func with *args and **kwargs in a new thread.

        Event handlers can be bound as kwargs using the keys:
            _start: Called when thread starts
            _message: Called for progress updates
            _end: Called when thread completes
        ...
        """
        end_handler: Callable = kwargs.pop("_end", lambda evt: None)
        start_handler: Optional[Callable] = kwargs.pop("_start", None)
        msg_handler: Optional[Callable] = kwargs.pop("_message", None)
        info = kwargs.pop("_info", None)
```

`*args` and `**kwargs` (Chapter 0's variadic-argument syntax) let
`start_thread` accept **any** function and **any** arguments for it —
it's a generic "run this in the background" helper, reused for loading
tags, saving tags, scanning a directory, generating a database, and more
(you'll see all of these calls in section 7.5). `kwargs.pop("_end", ...)`
pulls specific *special* keyword arguments (prefixed with `_` by
convention, to visually separate "instructions to `start_thread` itself"
from "arguments meant for `func`") out of the general `**kwargs` bag
before the remaining ones get forwarded to `func` — notice the default
`lambda evt: None` for `_end`, a one-line do-nothing function (Chapter 0's
lambda syntax) used when the caller doesn't care about the "finished"
event.

```python
        def worker(thread_obj: CancellableThread) -> None:
            try:
                if start_handler:
                    ThreadEvent.post_start(self.frame, start_handler, info)

                if msg_handler:
                    def thread_callback(*args, **kwargs):
                        if thread_obj.is_stopped():
                            raise InterruptedError("Operation cancelled by user")
                        if len(args) == 1:
                            ThreadEvent.post_callback(
                                self.frame, msg_handler, info, args[0]
                            )
                        else:
                            ThreadEvent.post_callback(
                                self.frame, msg_handler, info, args[0] if args else None
                            )

                    if "callback" in kwargs:
                        kwargs["callback"] = thread_callback
                    if "dircallback" in kwargs:
                        kwargs["dircallback"] = thread_callback
                    if "filecallback" in kwargs:
                        kwargs["filecallback"] = thread_callback
                    if "estimatecallback" in kwargs:
                        kwargs["estimatecallback"] = thread_callback

                func(*args, **kwargs)

                ThreadEvent.post_end(self.frame, end_handler, info)
            ...
```

This inner function `worker` is a **closure** (Chapter 0: a nested
function that "remembers" variables from the function that defined it —
here, `end_handler`, `start_handler`, `msg_handler`, `info`, `func`,
`args`, `kwargs` are all still reachable inside `worker` even though
`start_thread` has already returned by the time `worker` actually runs).
This is what actually executes *on the background thread*. Walk through
what it does:

1. `ThreadEvent.post_start(...)` — tells the GUI "a background job has
   begun" (so it can, for example, start a timer — see section 7.6).
2. It builds `thread_callback`, a **replacement** progress-callback
   function, and swaps it into `kwargs` under whatever name the real
   database function expects (`callback`, `dircallback`, etc. — recall
   from Chapter 1 that `database/generator.py` and friends accept
   callback functions to report progress). This is the single most
   important line in the whole file for the cooperative-cancellation
   story: **`if thread_obj.is_stopped(): raise InterruptedError(...)`**.
   Every single progress callback the database engine calls (potentially
   thousands of times, once per file scanned) passes back through here
   first, which means every single one is also a checkpoint where
   cancellation can take effect — within one callback interval of the
   user clicking Cancel, not instantly, but close to it, and always
   *between* safe, well-defined steps of the engine's own work rather than
   in the middle of one.
3. `func(*args, **kwargs)` — this is where the actual slow work
   (`database.generate_database()`, `database.write()`, etc.) finally
   runs, on this background thread, with the swapped-in
   cancellation-aware callback.
4. `ThreadEvent.post_end(...)` — tells the GUI "the job finished."

```python
            except InterruptedError:
                if info:
                    wx.CallAfter(lambda: setattr(info, "status", "Cancelled"))
            except SystemExit:
                pass
            except Exception as e:
                error_details = traceback.format_exc()
                print(f"Thread error: {e}", file=sys.stderr)
                print(error_details, file=sys.stderr)
                wx.CallAfter(
                    show_error_dialog, self.frame, "Thread Error", str(e), error_details
                )
            finally:
                with self._thread_lock:
                    if thread_id in self._active_threads:
                        del self._active_threads[thread_id]
```

Three outcomes are handled explicitly: a deliberate cancellation
(`InterruptedError`, raised by `thread_callback` above), a clean process
exit (`SystemExit`, just passed through), and — this is the important
one — **any other exception at all**. We'll come back to
`wx.CallAfter(show_error_dialog, ...)` in section 7.5, since that's the
"safely surface an error from a background thread" answer the task asks
about directly.

```python
        thread: CancellableThread = CancellableThread(
            target=lambda: worker(thread), daemon=True
        )
        with self._thread_lock:
            if thread_id is not None:
                self._active_threads[thread_id] = thread
        thread.start()
        return thread_id if thread_id is not None else ""
```

`target=lambda: worker(thread)` — this is the **thread's entry point**: a
tiny lambda whose only job is to call `worker`, passing in the very
`CancellableThread` object being constructed, so `worker` (and the
`thread_callback` closure inside it) can call `thread_obj.is_stopped()`
on *itself*. `daemon=True` (Chapter 0's threading-basics section covered
daemon threads) means this thread won't prevent the whole Python process
from exiting if it's still running when the main thread ends — important
because, as you saw in `app.py`, cooperative cancellation can take a
moment, and the app shouldn't hang on exit waiting for it. `thread.start()`
is what actually launches the OS thread and begins running `worker` —
everything up to this line ran on the GUI thread; everything from
`worker` onward runs on the new background thread.

---

### `gui/thread_events.py`: the safe hand-off mechanism

You've now seen `ThreadEvent.post_start/post_callback/post_end` called
from the background thread. Here's the whole file:

```python
try:
    import wx
    import wx.lib.newevent
except ImportError as e:
    raise ImportError(
        "This module requires wxPython. Install with: pip install dap-db-manager[gui]"
    ) from e


ThreadStartEvent, EVT_THREAD_START = wx.lib.newevent.NewEvent()
ThreadCallbackEvent, EVT_THREAD_CALLBACK = wx.lib.newevent.NewEvent()
ThreadEndEvent, EVT_THREAD_END = wx.lib.newevent.NewEvent()
```

`wx.lib.newevent.NewEvent()` is a wxPython helper that manufactures a
**brand new custom event type** on demand — this project isn't limited
to built-in events like button clicks; it can invent its own vocabulary
of events (`ThreadStartEvent`, etc.) for its own purposes. Each call
returns a *pair*: a class you instantiate to create an event
(`ThreadStartEvent`), and a matching "event type tag" you use when
binding a handler to it (`EVT_THREAD_START` — this is exactly what you
saw bound in `frame.py`'s `__init__` in section 7.3:
`self.Bind(EVT_THREAD_START, self.thread_handlers.on_thread_start)`).

```python
class ThreadEvent:
    """Helper class for posting thread events."""

    @staticmethod
    def post_start(obj, handler, info):
        evt = ThreadStartEvent(info=info, _handler=handler)
        wx.PostEvent(obj, evt)  # Post directly to frame
        wx.WakeUpIdle()
```

Two things do the actual safe hand-off here:

- `evt = ThreadStartEvent(info=info, _handler=handler)` — you can pass
  **arbitrary keyword arguments** to a `wx.lib.newevent`-created event,
  and they become attributes on the resulting object (`evt.info`,
  `evt._handler`). This is how data crosses from the background thread to
  the GUI thread: not by writing to a shared variable (which would be
  unsafe and racy), but by packaging it inside a brand-new, immutable-ish
  event object.
- **`wx.PostEvent(obj, evt)` is the actual thread-safe bridge.** Unlike
  calling a GUI method directly, `wx.PostEvent` is specifically documented
  and designed to be safe to call from *any* thread — it hands the event
  off to wxPython's internal event queue, and the event loop (running on
  the main/GUI thread, per section 7.1) picks it up and dispatches it to
  whatever's bound to that event type, at its own next opportunity. This
  is the single mechanism that makes everything in this chapter safe:
  **the background thread never touches a widget — it only ever posts an
  event describing what happened, and the GUI thread decides when and how
  to react.**
- `wx.WakeUpIdle()` nudges the event loop awake in case it was sitting
  completely idle, so the posted event gets processed promptly rather
  than waiting for some unrelated future event.

This pattern — "background thread posts an event instead of touching
widgets directly" — is this project's hand-built version of a very common
wxPython idiom you may see named elsewhere as **`wx.CallAfter`**, which
does something conceptually identical (schedule a function call to run
later, on the GUI thread) but for a single function call rather than a
full custom event with its own data. You'll actually see `wx.CallAfter`
used directly, too — look back at the `except Exception` block in
`threading_support.py`'s `worker()`: `wx.CallAfter(show_error_dialog,
self.frame, "Thread Error", str(e), error_details)`. Both tools solve the
exact same problem (get code to run on the GUI thread, safely, from a
background thread) — this project just built the richer custom-event
version (`thread_events.py`) for the common start/progress/end lifecycle
of a long operation, and reaches for the simpler `wx.CallAfter` for
one-off hand-offs like showing an error dialog.

### `main_frame/thread_handlers.py`: receiving the events

The events posted above eventually trigger these bound handlers (recall
section 7.3's three `self.Bind(EVT_THREAD_..., ...)` lines):

```python
class EventData:
    """Container for event data passed to handlers."""

    info: Optional[Any] = None
    message: Optional[Any] = None


class ThreadHandlers:
    def __init__(self, frame):
        self.frame = frame

    def on_thread_start(self, evt):
        if hasattr(evt, "_handler"):
            handler = evt._handler
            info = evt.info if hasattr(evt, "info") else None

            event_data = EventData()
            event_data.info = info

            handler(event_data)
        wx.WakeUpIdle()
```

Notice the indirection: `evt._handler` is itself *another* function — the
one passed in as `_start=OnStart` back when `start_thread(...)` was
originally called (you'll see concrete `OnStart`/`OnMessage`/`OnEnd`
functions in section 7.5). So the call chain for a single progress update
is: database engine calls its `callback` → `thread_callback` (in
`threading_support.py`) wraps it and posts a `ThreadCallbackEvent` →
wxPython's event loop (on the main thread) dispatches it to
`on_thread_message` below → which pulls out the handler the *caller*
originally supplied and finally calls it, now safely on the GUI thread.

```python
    def on_thread_end(self, evt):
        if hasattr(evt, "_handler"):
            handler = evt._handler
            info = evt.info if hasattr(evt, "info") else None

            event_data = EventData()
            event_data.info = info

            # Wrap the handler in CallAfter to ensure the UI thread
            # is definitely ready to process the layout change.
            wx.CallAfter(handler, event_data)

        if hasattr(evt, "info") and evt.info in self.frame.thread_info:
            self.frame.thread_info.remove(evt.info)

        wx.WakeUpIdle()
```

Here's a subtlety worth sitting with: `on_thread_end` is *already*
running on the GUI thread (it's a bound event handler, dispatched by the
event loop) — yet it *still* wraps the final handler call in
`wx.CallAfter`. The comment explains why: some GUI operations (here,
layout changes after the progress bar reaches 100%) are safest done on
the *next* trip through the event loop rather than synchronously inside
the current event's processing, to make sure the UI is in a fully settled
state first. This is a good example of "thread-safety" and "UI-ordering
safety" being related but not identical concerns — `wx.CallAfter` is
useful for both.

---

## 7.5 Tracing one real button: Generate Database

Let's tie sections 7.3 and 7.4 together by following one concrete, real
button click all the way through, from `main_frame/database_operations.py`:

```python
def on_generate_database(self, evt):
    """Handle Generate Database button click."""
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
```

This first part runs **synchronously, on the GUI thread, inside the
click handler** — and that's fine, because reading text-box values
(`.GetValue()`) is effectively instant; it's not the slow part. It reads
every format string the user typed into the "View" tab's text controls
(`self.frame.__dict__[...]` is just a more dynamic way of writing
`self.frame.some_attribute`, useful here because the attribute name is
built from a loop variable). It then creates a new progress row
(`InfoPanel.MakeRow`, from `info_panel.py`, section 7.6) and calls
`wx.Yield()` — a method that tells wxPython "process any pending repaint
events *right now*, before continuing," so the freshly-created progress
row actually appears on screen immediately instead of only showing up
whenever the event loop next got around to repainting.

```python
    def OnStart(evt):
        evt.info.status = "Compiling format strings..."

    def OnMessage(evt):
        if isinstance(evt.message, str) and evt.message.startswith("READY:"):
            count = int(evt.message.split(":")[1])
            evt.info.SetRange(count)
            evt.info.gauge = 0
            evt.info.status = "Processing files..."
        elif isinstance(evt.message, int):
            evt.info.SetRange(evt.message)
            evt.info.gauge = 0
        else:
            evt.info.status = str(evt.message)
            evt.info.gauge += 1

    def OnEnd(evt):
        evt.info.timer.Stop()
        evt.info.gauge = evt.info.gauge_ctrl.GetRange()
        evt.info.status = "Done"
        evt.info.parent.Layout()
        evt.info.parent.Refresh()
        DatabaseEvent.post_updated(self.frame.panes, self.frame.database)
```

These three nested functions are exactly the `_start` / `_message` /
`_end` handlers `start_thread` expects (section 7.4). **They are the only
code in this whole flow allowed to touch widgets** (`evt.info.status =
...`, `evt.info.gauge += 1`), and that's safe precisely because — as you
traced in section 7.4 — `thread_handlers.py` always calls them from the
GUI thread (either directly as an event handler, or via `wx.CallAfter`),
never from the background thread itself. `evt` here is the small
`EventData` container from `thread_handlers.py`, not a raw wxPython
event — another small, deliberate layer of indirection to keep this
function simple.

```python
    def worker_generate_database(format_strings, callback=None):
        for field, (format_str, sort_str) in format_strings.items():
            self.frame.database.set_format(field, format_str, sort_str)

        if callback:
            callback(f"READY:{len(self.frame.database.paths)}")

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
```

And here's the handoff into the background thread: `worker_generate_database`
is the function that will actually run there. It calls
`self.frame.database.set_format(...)` for each field (recall
`tagging/titleformat/` from Chapter 1 — compiling those format strings),
then calls the real engine entry point,
`self.frame.database.generate_database(callback=callback)` — this is the
exact same `Database.generate_database()` the CLI's `generate` command
calls (Chapter 1's "both front-ends call the same engine" point, made
concrete). The `callback=None` passed into `start_thread` here gets
intercepted and replaced with the cancellation-aware `thread_callback`
wrapper you read in section 7.4, before `worker_generate_database` ever
runs — which is why `worker_generate_database` can accept a `callback`
parameter and just pass it straight through without knowing anything
about threads, events, or cancellation itself.

**The full chain, end to end:** button click → `MyFrame.OnGenerateDatabase`
→ `DatabaseOperations.on_generate_database` → reads format strings on the
GUI thread → `ThreadingSupport.start_thread(...)` spawns a
`CancellableThread` → on that new thread, `worker_generate_database` runs
→ calls `Database.generate_database()` (the real engine) → which calls its
`callback` for every progress update → which is actually
`thread_callback` → which checks `is_stopped()` then calls
`ThreadEvent.post_callback(...)` → which does `wx.PostEvent(...)` →
wxPython's event loop (main thread) dispatches an `EVT_THREAD_CALLBACK`
event → `ThreadHandlers.on_thread_message` → calls the original `OnMessage`
→ which finally updates `evt.info.status` and the progress gauge, safely,
on the GUI thread.

---

## 7.6 Progress bars and cooperative cancellation

### `gui/info_panel.py`: what a progress row actually is

`InfoPanel` (a `wx.ScrolledWindow` — a panel that can scroll if its
contents don't fit) holds one `Info` object per running operation:

```python
class InfoPanel(wx.ScrolledWindow):
    def MakeRow(self, description=""):
        info = Info(self, description)
        self.sizer.Add(info.time_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.sizer.Add(info.description_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.sizer.Add(info.gauge_ctrl, 1, wx.ALL, 5)
        self.sizer.Add(info.status_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL | wx.EXPAND, 5)
        self.sizer.Layout()
        self.Refresh()
        return info
```

Every operation you traced in 7.5 (`Load Tags`, `Add Directory`,
`Generate Database`, `Write`, `Read`) calls `self.frame.infopanel.MakeRow(...)`
to get its own `info` object — this is why the GUI can show multiple
progress bars stacked up if you start more than one operation (though
most buttons in practice are disabled or queued to avoid truly concurrent
database mutation — note that nothing stops you from poking around and
confirming this for yourself per the exercises below).

`Info` itself wires up a `wx.Gauge` (the progress bar widget) and a timer,
and exposes them through **properties** (Chapter 0's `@property`) so
calling code can write the friendly `info.status = "Done"` instead of
`info.status_ctrl.SetValue("Done")`:

```python
@staticmethod
def _make_property(name: str):
    ctrl_name = name + "_ctrl"

    def __get(self):
        return getattr(self, ctrl_name).GetValue()

    def __set(self, value):
        getattr(self, ctrl_name).SetValue(value)

    return property(__get, __set)

gauge = _make_property("gauge")
time_value = _make_property("time")
description = _make_property("description")
status = _make_property("status")
```

This is a slightly more advanced use of `@property`'s underlying building
block, `property(getter, setter)`, than Chapter 0's `@dataclass` examples:
instead of writing four nearly-identical property definitions by hand, the
code writes one **property factory function**, `_make_property`, and
calls it four times. Each call captures its own `ctrl_name` inside the
`__get`/`__set` closures (the same closure idea from section 7.4), so
`info.gauge` reads/writes `self.gauge_ctrl`, `info.status` reads/writes
`self.status_ctrl`, and so on, all from one small reusable piece of code.

### `gui/cancellable_progress.py`: dialogs that can say "stop"

This file provides an alternative, *modal* progress UI (a dialog box that
blocks interaction with the rest of the window until closed) with a
built-in Cancel button:

```python
class CancellableProgressDialog(wx.Dialog):
    def __init__(self, parent, title, message, maximum=100, style=...):
        ...
        self._cancelled = False
        self._cancel_callback: Optional[Callable] = None
        ...
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        ...

    def on_cancel(self, evt):
        """Handle cancel button click."""
        self._cancelled = True
        self.status_text.SetLabel("Cancelling...")
        self.cancel_button.Enable(False)

        if self._cancel_callback:
            self._cancel_callback()
```

`self._cancelled = True` is the same cooperative-flag idea you saw in
`CancellableThread` — clicking Cancel doesn't forcibly stop anything, it
just records "the user wants to stop" and disables the button so they
don't click it twice. The actual stopping only happens because *other*
code chooses to check the flag:

```python
    def update(self, value: int, message: Optional[str] = None) -> bool:
        if self._cancelled:
            return False

        self.gauge.SetValue(min(value, self.maximum))
        if message:
            self.status_text.SetLabel(message)

        # Process pending events to keep UI responsive
        wx.GetApp().Yield(True)

        return not self._cancelled
```

The calling convention here is: whoever is doing the long-running work
calls `dialog.update(progress, message)` periodically and checks the
**return value** — `False` means "the user cancelled, stop now." This
mirrors the `is_stopped()` check inside `thread_callback` from section
7.4; both are the same cooperative-cancellation pattern, just expressed
through a boolean return value here instead of a raised exception. Also
notice `wx.GetApp().Yield(True)` — a second appearance of the "manually
pump the event loop" idea from `wx.Yield()` in section 7.5, here needed
because a modal dialog's own internal loop can otherwise make the rest of
the app feel stuck if events aren't processed along the way.

`NonModalProgressDialog`, further down the same file, is a variant built
from a plain `wx.Frame` instead of `wx.Dialog` — "non-modal" means it
*doesn't* block interaction with the rest of the app, useful when you want
a visible progress indicator the user can still work around.

### `gui/progress.py`: throttling progress updates

One more problem worth naming: if a background operation calls its
progress callback once per file, and you're scanning 50,000 files, posting
50,000 wx events (each one bouncing through `wx.PostEvent` and the event
loop, per section 7.4) can itself become slow enough to matter. `progress.py`'s
`ProgressThrottle` exists purely to fix that — not a threading-safety tool,
but a *performance* one:

```python
class ProgressThrottle:
    def __call__(self, message: Any, **kwargs) -> None:
        self.count += 1
        self.last_message = (message, kwargs)

        should_update = False
        ...
        if self.count - self.last_update >= self.update_interval:
            should_update = True
            self.last_update = self.count

        if should_update:
            self.callback(message, **kwargs)
```

`def __call__(self, ...)` makes instances of `ProgressThrottle` themselves
**callable**, like a function (`throttled("some message")` works, because
Python calls `__call__` whenever you use `()` on an object — another
dunder method, like the `__getattr__`/`__setattr__` pair Chapter 1 showed
you in `IndexEntry`). It wraps a real callback and only actually calls it
every `update_interval` calls, batching away the rest — the GUI still
*looks* responsive to the user because `.flush()` (not shown above) is
called once at the end to guarantee the final 100%-complete state is
always shown, even if it fell on a skipped update.

---

## 7.7 Surfacing errors from a background thread safely

You already saw the key line back in section 7.4's `worker()`:

```python
except Exception as e:
    error_details = traceback.format_exc()
    print(f"Thread error: {e}", file=sys.stderr)
    print(error_details, file=sys.stderr)
    # Show error dialog to user
    wx.CallAfter(
        show_error_dialog, self.frame, "Thread Error", str(e), error_details
    )
```

Walk through *why* this specific shape is necessary. An uncaught
exception raised inside `database.generate_database()` (say, a corrupted
file, a permissions error, disk full) propagates up through
`worker_generate_database` and is caught here, on the background thread.
At this point, you might reach for the obvious thing:

```python
show_error_dialog(self.frame, "Thread Error", str(e), error_details)   # WRONG, on this thread
```

But `show_error_dialog` (from `gui/error_handling.py`) ultimately calls
`wx.MessageDialog(...).ShowModal()` — and `wx.MessageDialog` is a widget.
Calling it here would be exactly the thread-safety violation section 7.4
warned about: a GUI widget being created and shown from a thread that
isn't the one running the event loop. Depending on platform and timing,
this can silently fail, corrupt internal wxPython state, or crash the
whole process — and crucially, it's **not reliably reproducible**, which
is exactly the kind of bug that's miserable to debug later if it's
allowed to sneak in.

`wx.CallAfter(show_error_dialog, self.frame, "Thread Error", str(e), error_details)`
is the fix: instead of calling `show_error_dialog` immediately (on the
wrong thread), it schedules a call to `show_error_dialog` with those exact
arguments to happen later, on the GUI thread, the next time the event loop
gets a turn — the same safe-handoff idea as `wx.PostEvent` in section 7.4,
just for a single function call instead of a full custom event class. The
`print(..., file=sys.stderr)` calls just before it are a second,
independent safety net: printing to `stderr` is thread-safe and doesn't
touch any GUI object at all, so even in the worst case (say,
`wx.CallAfter` itself somehow failing, or the window already being
destroyed), the error is still visible somewhere — in the terminal you
launched `dap-db-manager` from — instead of vanishing silently.

Looking at `gui/error_handling.py` itself:

```python
def show_error_dialog(
    parent: Optional[wx.Window], title: str, message: str, details: Optional[str] = None
) -> None:
    if details:
        full_message = f"{message}\n\nDetails:\n{details}"
    else:
        full_message = message

    dlg = wx.MessageDialog(parent, full_message, title, wx.OK | wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()
```

This function itself has no idea threads exist — it's plain, ordinary
GUI code: build a message dialog, show it modally (blocking until the
user clicks OK — this is fine here, because unlike the long-running
database work, showing a dialog is instant and expected to briefly pause
interaction), then explicitly `Destroy()` it (wxPython widgets need
explicit cleanup in many cases, unlike regular Python objects which
Chapter 0's garbage collector would eventually clean up on its own). The
*entire* thread-safety responsibility lives at the call site
(`wx.CallAfter(...)`), not inside this function — a useful lesson in
itself: keep thread-safety concerns at the boundary where a background
thread hands off to the GUI, not scattered through every widget-touching
function.

`error_handling.py` also has two small, pure validation helpers worth
noting briefly — `validate_path()` (checks a path is non-empty and
exists/has an existing parent) and `validate_format_string()` (checks
titleformat brackets are balanced using a stack, the same bracket-matching
technique you may have seen in other parsers). Neither touches threads at
all — they run synchronously on the GUI thread, right after the user picks
a file/folder and before any background work is even started, rejecting
bad input early with `show_error_dialog` called directly (safe here,
specifically *because* it's already running on the GUI thread, inside an
ordinary button-click handler).

---

## 7.8 A look at the more advanced `async_operations.py`

Everything so far uses plain `threading.Thread` plus custom wx events.
`gui/async_operations.py` layers Python's `asyncio` (briefly mentioned in
Chapter 0 as an alternative concurrency model) on top of that same
foundation, for callers that want `await`-style async code instead of
callback-style:

```python
class AsyncIOSupport:
    def __init__(self, frame):
        self.frame = frame
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._operations: dict[str, AsyncOperation] = {}
        self._start_event_loop()

    def _start_event_loop(self) -> None:
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        while self._loop is None:
            threading.Event().wait(0.01)
```

This creates a **second event loop** — not the wxPython one from section
7.1, a separate `asyncio` event loop — and runs it `.run_forever()` inside
its own dedicated background thread. This is a standard pattern for
mixing `asyncio` with a GUI toolkit that has its own, different, built-in
event loop: the two loops can't just be merged, so `asyncio`'s loop gets
parked on a thread of its own, and work is explicitly shuttled across the
thread boundary:

```python
def run_async(self, coro, operation_id=None, on_complete=None, on_error=None, ...):
    ...
    async def wrapper():
        try:
            result = await coro
            if not operation.is_cancelled() and on_complete:
                wx.CallAfter(on_complete, result)
            return result
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not operation.is_cancelled() and on_error:
                wx.CallAfter(on_error, e)
            raise
        ...

    future = asyncio.run_coroutine_threadsafe(wrapper(), self._loop)
```

Same lesson as everywhere else in this chapter, just with different
vocabulary: `asyncio.run_coroutine_threadsafe(...)` is how you safely
schedule a coroutine onto an `asyncio` loop running on a different thread,
and — once again — `wx.CallAfter(on_complete, result)` /
`wx.CallAfter(on_error, e)` is how results and errors get handed back to
the GUI thread safely, exactly as in section 7.7. `AsyncOperation.cancel()`
is yet another instance of the cooperative-cancellation flag pattern:
`self._cancelled = True` plus `self._task.cancel()`, which asks (but
cannot force) the coroutine to stop at its next `await` point.

As of this writing, `AsyncIOSupport`/`AsyncDatabaseOperations` are a
self-contained, independently usable layer — a good exercise (see 7.9) is
to check for yourself whether `main_frame/frame.py` actually instantiates
and uses one, or whether this is infrastructure ready for a caller that
hasn't been wired in yet.

---

## 7.9 The rest of the UI, briefly

A few remaining files round out the GUI, each owning one clear
responsibility:

- **`gui/field_panes.py`** — the "View" tab: lets you browse the in-memory
  `Database` by filtering on genre/artist/album/title. `FieldPane` wraps a
  dropdown + listbox pair; `FieldPanePanel` (further down the file)
  coordinates several `FieldPane`s together, so picking an artist narrows
  the album list, and so on. It also defines its own custom events
  (`FieldPaneEvent`/`EVT_FIELD_PANE`, `DatabaseEvent`/`EVT_DATABASE`),
  the same `wx.lib.newevent.NewEvent()` pattern from section 7.4's
  `thread_events.py` — here used not for thread-safety, but simply to
  decouple "a filter selection changed" from "the UI needs to react,"
  which is good event-driven design even entirely within the GUI thread.
  You already saw `DatabaseEvent.post_updated(...)` called at the end of
  `on_generate_database`/`on_write_database`/`on_read_database` in
  section 7.5 — that's this file's event, used to tell the "View" tab
  "the database object changed out from under you, refresh yourself."
- **`main_frame/database_operations.py`** — covered in depth in 7.5: one
  method per database-affecting button (Load Tags, Save Tags, Add
  Directory, Generate Database, Write Database, Read Database), each
  gathering GUI input synchronously, then handing the real work to
  `threading_support.start_thread(...)`.
- **`main_frame/format_manager.py`** — owns loading/saving the per-field
  titleformat strings (Chapter 1's `tagging/titleformat/`) between the
  GUI's text controls and the on-disk `Config` (Chapter 1's `config.py`),
  plus adding tooltips and a right-click "insert template" menu to those
  same text controls. It never touches threads at all — reading/writing
  small strings to a config file is fast enough to do directly on the GUI
  thread.
- **`gui/wxFB_gui.py`** — as noted in 7.3, purely generated layout code
  from wxFormBuilder. Treat it as read-only scaffolding, not something to
  study line-by-line.

---

## 7.10 Try It Yourself

1. **Trace a button to the engine, end to end.** Pick a *different* button
   than "Generate Database" — try "Write Database". Starting from
   `MyFrame.OnWriteDatabase` in `frame.py`, follow the call chain exactly
   like section 7.5 did, writing down each function name and which
   thread it runs on (GUI thread or background thread) at each step.
   Where does it finally call into `database/` or `indexfile.py`
   (Chapter 1)?

2. **Find every `wx.CallAfter` and every `wx.PostEvent` in `gui/`.**
   `grep -rn "CallAfter\|PostEvent" src/dap_db_manager/gui/`. For each
   result, answer: what thread is this line running on when it executes,
   and what thread does the thing it schedules actually run on?

3. **Make the freeze happen on purpose (then undo it).** In a scratch
   copy of `database_operations.py`, temporarily change
   `on_add_directory` to call `self.frame.database.add_dir(dir)` directly
   instead of going through `threading_support.start_thread(...)`. Run the
   GUI against a folder with a few thousand files and try to drag the
   window while it's scanning. Confirm it's unresponsive. Revert the
   change and confirm dragging works fine again — you've now directly
   experienced the exact failure section 7.4 describes in the abstract.

4. **Pull the cooperative-cancellation thread.** In
   `threading_support.py`, find the line
   `if thread_obj.is_stopped(): raise InterruptedError(...)`. Then find
   every place `CancellableThread.stop()` gets called
   (`grep -rn "\.stop()" src/dap_db_manager/gui/`). What user action
   leads to `stop()` being called? How many progress-callback invocations
   (roughly) might happen between the user triggering that and the
   `InterruptedError` actually being raised — and why can't this project
   make that gap exactly zero?

5. **Find a place a widget is touched from the wrong thread, if one
   exists.** Scan `main_frame/database_operations.py`'s `OnStart`,
   `OnMessage`, `OnEnd` nested functions for every one of the six button
   handlers. For each, confirm (by tracing how it gets called, as in
   7.4/7.5) that it's always invoked via `thread_handlers.py`, never
   called directly from inside a `worker`/`CancellableThread`. If you
   genuinely can't find a violation, that's the correct answer — write
   down *why* you're confident, citing the specific call sites.

6. **Compare the two cancellation patterns.** `threading_support.py`'s
   worker raises `InterruptedError` to stop; `cancellable_progress.py`'s
   `CancellableProgressDialog.update()` instead *returns* `False`. Write
   one sentence each on why a raised exception makes sense in one context
   and a return value makes sense in the other (hint: look at *who* is
   calling `update()` versus who is calling the progress callback inside
   `worker`).

7. **Run the GUI and watch `stderr`.** `uv run dap-db-manager`, launched
   from a terminal. Trigger an error on purpose (e.g. point "Add
   Directory" at a folder you then delete out from under it, or revoke
   read permission on a file inside it mid-scan) and confirm you see both
   the error dialog *and* the traceback printed to your terminal — tying
   back to the two independent error-reporting paths described in 7.7.

---

**Previous:** [Chapter 6 — The Peaks Subsystem](06-peaks-subsystem.md)
**Next:** [Chapter 8 — Testing and Tooling](08-testing-and-tooling.md)
