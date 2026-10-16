# Chapter 1 — Project Overview: What Is DAP DB Manager?

> **Who this is for:** you've finished Chapter 0 (the Python primer) and know
> what variables, functions, classes, type hints, dataclasses, decorators,
> exceptions, context managers, generators, argparse, and basic
> multiprocessing/threading *are*. This chapter does not re-teach any of that —
> it shows you where those concepts show up in a real, working project.
>
> **How to use it:** keep a terminal open in the project root
> (`DAP-DB-Manager/`) and actually run the commands as you read. Reading
> about a CLI tool is not the same as running it.

---

## 1.1 What problem does this project solve?

Rockbox is a free, open-source alternative firmware that runs on devices like
the iPod Classic, turning an old piece of hardware into what people call a
**DAP** — a **D**igital **A**udio **P**layer. Rockbox keeps a searchable
"database" of every song on the device so you can browse by artist, album,
genre, etc. without rescanning your whole music library every time you plug
it in. That database is a handful of binary files it calls the **tag cache**
(`database_0.tcd`, `database_1.tcd`, ... `database_idx.tcd`), usually stored
in a hidden `.rockbox` folder on the device.

The problem: **building that tag cache on the device itself is slow.** An
iPod Classic from 2009 has a mechanical hard drive and a USB 2.0 connection.
Scanning tens of thousands of music files and writing the database directly
on the device can take a long time — README.md quotes speeds as low as
~14-21 MB/s read over USB for that hardware.

**DAP DB Manager (`ddm`)** solves this by doing the expensive part — reading
every audio file's tags, building the database structure, and writing the
`.tcd` files — **on your PC**, which is dramatically faster (the README
claims up to 180x, by avoiding the device's slow I/O entirely). Once built,
you copy (or the tool writes directly onto) the device's `.rockbox` folder,
and Rockbox just loads the finished database instead of building it.

So in plain English: **this project is a database compiler.** You give it a
folder of music files, and it produces the exact binary files Rockbox
expects, with correct paths for *that specific device*, while also being
careful not to throw away things the device itself tracked over time — like
how many times you've played a song, your star ratings, and where you left
off listening (the "resume position"). The README calls this
**non-destructive rebuilds**: `generate` reads the *old* database before
replacing it, and carries those statistics onto the new one by matching
file paths.

It ships three ways to use it:

- A **CLI** (`ddm ...`) — the primary, most-maintained interface.
- A **GUI** (`dap-db-manager`) built with wxPython, for people who prefer
  clicking buttons to typing commands (optional install).
- A **library** — all of the above is just a thin interface over Python
  modules you could import and use yourself.

---

## 1.2 The big picture: how a request flows through the system

Here's the shape of the whole project as an ASCII diagram. Don't worry about
every box yet — we'll walk through each one.

```
                          ┌───────────────────────────┐
                          │   You, at a terminal       │
                          │   $ ddm generate ...        │
                          └──────────────┬──────────────┘
                                         │
                                         ▼
                        ┌─────────────────────────────────┐
                        │  CLI layer  (cli/)                │
                        │  argparse subcommands:             │
                        │  generate, update, validate,        │
                        │  inspect, load, write,               │
                        │  detect-mounts, peaks                │
                        └──────────────┬──────────────────────┘
                                         │ calls into
                                         ▼
                        ┌─────────────────────────────────┐
                        │  Database engine (database/)       │
                        │  - file_scanner: walk music dir      │
                        │  - generator: orchestrate the build   │
                        │  - cache: speed up repeated scans       │
                        │  - rename_detector / stats_preserver   │
                        │  - io: read/write the .tcd files         │
                        │  - mount_detector: find DAP mount point   │
                        └──────────────┬──────────────────────────┘
                                         │ uses
                      ┌──────────────────┼───────────────────────┐
                      ▼                                          ▼
        ┌─────────────────────────────┐          ┌─────────────────────────────┐
        │  Tagging subsystem (tagging/)  │          │  Peaks subsystem (peaks/)      │
        │  - tag/: read ID3/FLAC/etc tags │          │  - waveform peak extraction      │
        │  - titleformat/: foobar2000-style│          │    for Rockbox's "peak" display   │
        │    format-string mini language    │          │  - hasher + writer for peak files  │
        └─────────────────────────────────┘          └─────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Shared core modules            │
        │  config.py, constants.py,         │
        │  indexfile.py, utils.py             │
        │  (used by everything above)           │
        └─────────────────────────────────┘

                                         ▲
                                         │ optional alternative front-end
                        ┌─────────────────────────────────┐
                        │  GUI (gui/, needs wxPython)        │
                        │  Same database engine underneath,   │
                        │  just a window instead of a terminal │
                        └─────────────────────────────────┘
```

The key idea: **the CLI and GUI are both thin front-ends.** Neither one
contains the "real" logic for reading tags or writing database files — they
both call into `database/`, which in turn calls into `tagging/` and
`peaks/`. This is a common and good pattern: keep your core logic
independent of *how* a human triggers it, so you can add a new front end
(say, a web API) later without rewriting the engine.

---

## 1.3 A guided tour of `src/dap_db_manager/`

Run this yourself to see the layout:

```bash
find src/dap_db_manager -type f -name '*.py' | sort
```

The package is organized into **subpackages** (folders with an
`__init__.py`, as covered in Chapter 0) plus a handful of **top-level
modules** that everything else depends on. Here's what each one does.

### `cli/` — the command-line interface

This is what runs when you type `ddm` in your terminal. `cli/__init__.py`
builds an `argparse` parser (see Chapter 0's argparse section) with one
subcommand per file in `cli/commands/`:

| File | Subcommand | Purpose |
|---|---|---|
| `commands/generate.py` | `ddm generate` | Build a brand-new database from a music folder |
| `commands/update.py` | `ddm update` | Apply a fast, incremental delta update to an existing database |
| `commands/validate.py` | `ddm validate` | Check an existing database file for integrity problems |
| `commands/inspect.py` | `ddm inspect` | Low-level dump of a database file's internal structure |
| `commands/load.py` | `ddm load` | Load and print the contents of an existing database |
| `commands/write.py` | `ddm write` | Lower-level write operation used by other commands |
| `commands/detect_mounts.py` | `ddm detect-mounts` | Figure out how Rockbox refers to your DAP's storage (e.g. `/<HDD0>`) |
| `commands/peaks.py` | `ddm peaks` | Generate waveform "peak" files used by Rockbox's UI |

`cli/callbacks.py` holds small reusable functions passed around as
callbacks (functions passed as arguments — Chapter 0 covered functions as
first-class values), typically for progress reporting. `cli/schemas.py`
defines data shapes (built with pydantic, which you'll recognize as a
stricter cousin of Chapter 0's dataclasses) used to validate command
arguments. `cli/utils.py` has shared helpers like `setup_logging()` and an
`ExitCode` type for consistent process exit codes.

### `database/` — the engine that actually builds the `.tcd` files

This is the heart of the project. If `cli/` is the steering wheel,
`database/` is the engine:

- **`file_scanner.py`** walks a music directory tree and finds audio files
  to include (this is where you'd expect to see something like
  `os.walk` or `pathlib.Path.rglob`, both generator-based — recall
  generators from Chapter 0).
- **`generator.py`** is the orchestrator: it ties together the scanner,
  the tagging subsystem, and the index file writer to perform a full
  `ddm generate` run. This is also where multiprocessing comes in — README
  mentions "Multiprocessing bypasses Python GIL (4-15x faster)", meaning
  multiple files get their tags read in parallel worker processes instead
  of one at a time in a single process (Chapter 0 covered the GIL and why
  multiprocessing, not just threading, is used for CPU-bound work).
- **`cache.py`** implements `TagCache`, a persistent cache so that
  re-running `generate` on a mostly-unchanged library doesn't have to
  re-read every file's tags from scratch.
- **`rename_detector.py`** figures out when a file was moved/renamed rather
  than deleted-and-re-added, so `ddm update` can keep your play stats
  attached to it.
- **`stats_preserver.py`** implements the "non-destructive rebuild" feature
  from the README: it reads the old database's play counts, ratings, and
  resume positions, and carries them onto matching entries in the new one.
- **`io.py`** handles the low-level reading/writing of the actual `.tcd`
  files on disk (building on `indexfile.py`, described below).
- **`mount_detector.py`** backs `ddm detect-mounts`: it looks at a
  connected device and works out what Rockbox calls it internally (e.g.
  `/<HDD0>` for the main hard drive), which is needed so paths stored in
  the database match what Rockbox expects.

### `tagging/` — reading metadata out of music files, and formatting it

Before you can put a song's artist/title/album into the database, you have
to read that information out of the audio file (an MP3, FLAC, etc.) and
decide what text actually goes in the database for a given field. This
subpackage has two halves:

- **`tagging/tag/`** reads raw tags from audio files using the `mutagen`
  library (a dependency declared in `pyproject.toml`). `tag/core.py` and
  `tag/tagfile.py` hold the core reading logic and the `TagEntry` type you
  saw imported in `indexfile.py`; `tag/mappings/` normalizes the many
  different tagging conventions (ID3 for MP3, Vorbis comments for FLAC,
  etc.) into one consistent set of fields — see `mappings/id3.py`,
  `mappings/default.py`, and `mappings/format_specific.py`.
- **`tagging/titleformat/`** implements a small format-string language
  (inspired by foobar2000's "titleformat" syntax) that lets you configure
  *how* a field is displayed, e.g. `%artist% - %title%`. Look at
  `config.py`'s `DEFAULT_CONFIG["formats"]` dictionary — those `%artist%`
  style strings are titleformat expressions. The files `field.py`,
  `function.py`, `conditional.py`, `statement.py`, `string.py`, and
  `tagbool.py` each implement one grammatical piece of that mini-language
  (fields, functions, if/else-style conditionals, boolean logic, etc.) —
  this is a small parser/interpreter, a good example of the
  "building a mini language out of classes" pattern.

### `peaks/` — waveform peak data

Some Rockbox UI themes display a little waveform graphic for the currently
playing track. That graphic isn't computed on the device — it is
precomputed and stored alongside the music. `peaks/extractor.py` pulls
audio samples out of a file, `peaks/hasher.py` makes sure peak data isn't
regenerated unnecessarily for a file that hasn't changed, `peaks/writer.py`
writes the resulting peak file in the format Rockbox expects, and
`peaks/manager.py` coordinates the three. `ddm peaks` (in
`cli/commands/peaks.py`) is the command-line entry point for this feature.

### `gui/` — the optional visual interface

Everything in `gui/` is about presenting the same database engine inside a
window instead of a terminal, using the `wxpython` library (an *optional*
dependency — see `pyproject.toml`'s `[project.optional-dependencies]` `gui`
extra). `gui/app.py` and `gui/main_frame/` build the window and its
controls; `gui/async_operations.py` and `gui/main_frame/threading_support.py`
run long operations (like a full `generate`) on a background thread so the
window doesn't freeze while it works (recall Chapter 0's threading
section — this is exactly the "don't block the UI thread" use case
threads are good for); `gui/progress.py` and `gui/cancellable_progress.py`
show progress bars and let you cancel a running job.

### The core modules living directly in `src/dap_db_manager/`

Four files sit at the top level, outside any subpackage, because every
other part of the project depends on them:

| File | Role |
|---|---|
| `__init__.py` | Package entry point; exposes `__version__` and documents the subpackages |
| `constants.py` | Fixed values that never change at runtime (tag orders, binary format magic numbers, flag bits) |
| `config.py` | User-editable settings, loaded from/saved to a TOML file on disk |
| `utils.py` | Small, generic helper functions used across the codebase |
| `indexfile.py` | Reads and writes the actual binary index file Rockbox uses |

We'll look at two of these in detail in section 1.6.

---

## 1.4 Running the project yourself

### Install it

The project uses [`uv`](https://docs.astral.sh/uv/), a fast Python package
manager, as its primary workflow (`pyproject.toml` even sets
`build-backend = "uv_build"`). From the project root:

```bash
uv sync
```

`uv sync` reads `pyproject.toml`, creates (or reuses) a virtual environment,
and installs exactly the dependencies listed there — `mutagen`, `rich`,
`pydantic`, etc. (all declared in `pyproject.toml`'s `dependencies` list).
If you also want the GUI:

```bash
uv sync --extra gui
```

That installs the extra `wxpython` dependency defined under
`[project.optional-dependencies]` in `pyproject.toml`.

Pip works too, if you don't have `uv`:

```bash
pip install -e .
pip install -e ".[gui]"   # with GUI support
```

### See what the tool can do

```bash
ddm --help
```

(If you used `uv sync`, run `uv run ddm --help` instead, so it runs inside
the environment `uv` created.) This prints the list of subcommands from
`cli/__init__.py` — `generate`, `update`, `detect-mounts`, `validate`,
`inspect`, `load`, `write`, `peaks` — formatted nicely thanks to the
`rich-argparse` dependency.

### The real Quick Start, straight from `README.md`

```bash
# 1. Install Only CLI
pip install -e .
# Or install with GUI support
pip install -e ".[gui]"

# 2. Detect mount point (first run only)
# Connect your DAP and point to its .rockbox folder
ddm detect-mounts --db-dir /Volumes/IPOD/.rockbox

# 3. Generate database (Cross-Compiled)
# --dap-root maps your local path to the DAP's root
ddm generate \
  --music-dir /Path/To/Music/Folder \
  --output /Volumes/IPOD/.rockbox \
  --dap-root /Path/To
```

Reading that with everything from section 1.1–1.3 in mind: step 2 runs
`mount_detector.py` logic to work out your device's Rockbox mount notation
(like `/<HDD0>`) and save it via `config.py`. Step 3 runs the full pipeline
from the diagram in 1.2 — scan `--music-dir` with `file_scanner.py`, read
tags with `tagging/`, optionally compute waveform peaks, and write the
`.tcd` files into `--output` via `indexfile.py` and `database/io.py`. The
`--dap-root` flag is used by `utils.normalize_dap_path()` (section 1.6) to
turn your local path (`/Path/To/Music/Folder/Song.mp3`) into the path
Rockbox expects on the device (`/<HDD0>/Music/Folder/Song.mp3`).

### Run the GUI

```bash
dap-db-manager
# or, inside the uv-managed environment:
uv run dap-db-manager
```

### Run the test suite

```bash
pytest
```

Look at `find tests -maxdepth 1 -name '*.py' | sort` — there are dozens of
test files, each targeting one module (e.g. `test_indexfile.py` tests
`indexfile.py`, `test_generator.py` tests `database/generator.py`,
`test_titleformat_parser.py` tests `tagging/titleformat/`). This is a
healthy sign: production code paired 1-to-1 with a test file is much
easier to change safely than code with no tests. You can run a single
file's tests while you're learning a specific module, e.g.:

```bash
pytest tests/test_indexfile.py -v
```

---

## 1.5 `config.py` vs `constants.py`: two very different kinds of "fixed data"

Both files hold data the rest of the program reads, but they hold
*fundamentally different kinds* of data, and the distinction matters.

### `constants.py` — things that are true about the Rockbox file format itself

```python
FILE_TAGS = [
    "artist",  # 0: tag_artist -> database_0.tcd
    "album",  # 1: tag_album -> database_1.tcd
    ...
]
MAGIC = 1413695504  # Version 16
SUPPORTED_VERSIONS = [1413695504]  # Version 16 only
```

These values aren't a matter of user preference — they describe the actual
on-disk binary format Rockbox's C code expects, down to the byte order of
fields. `MAGIC` is literally the first 4 bytes of every valid database
file; if you change it, you've described a different file format, not
changed a setting. This is why it lives in plain module-level variables
(no classes, no config objects) — in Chapter 0 terms, these are just names
bound to literal values, imported wherever needed with
`from .constants import MAGIC, TAGS, ...` (see the top of
`indexfile.py`). Centralizing them in one file means that if Rockbox ever
changes its format (a new tag, a new version number), there is exactly
*one* place to update it, instead of a magic number like `1413695504`
copy-pasted across a dozen files where someone would eventually get one of
the copies wrong.

### `config.py` — things the *user* or *this machine* can legitimately change

```python
DEFAULT_CONFIG: Dict[str, Any] = {
    "window": {"width": 800, "height": 600, "x": -1, "y": -1},
    "paths": {"last_music_dir": "", "last_output_dir": "", "last_tags_file": ""},
    "database": {"version": 16, "mount_notation": "", "mount_notation_configured": False},
    "performance": {"tag_cache_memory_mb": None},
    "formats": {"artist": "%artist%", "album": "%album%", ...},
    "sort_formats": {...},
}
```

Unlike `constants.py`, these values are *expected* to differ from user to
user and from run to run: how big you like the GUI window, which directory
you last browsed to, how much RAM to use for caching, and what titleformat
string you want for each field. That's why this isn't a flat module-level
dictionary — it's wrapped in a `Config` class (`class Config:` further
down in `config.py`) with `load()` and `save()` methods that read/write a
real file on disk (`~/.ddm/.rdbm_config.toml`, computed by
`get_config_path()`).

Tie this back to Chapter 0: `Config` behaves similarly to a dataclass in
spirit (it bundles related data with the methods that operate on it), but
it's a hand-written class rather than a `@dataclass`, because it needs
custom behavior beyond "just hold some fields" — merging loaded TOML data
over defaults (`_merge_config`), tracking whether something changed since
the last save (`self._dirty`), and filtering out `None` values before
writing TOML, since TOML (unlike Python) has no concept of `None`/`null`
(`_filter_none_values`). The project's CLI argument *validation*, by
contrast, does use pydantic models (see `cli/schemas.py`) — pydantic is
effectively "dataclasses with runtime validation baked in," which you'll
recognize from Chapter 0's type-hints discussion as a natural next step
once you want your type hints to actually be *checked*, not just
documented.

**The general lesson**: constants that describe an external fixed format
belong in one module as plain values; settings that a user or machine can
reasonably want to change belong in a small config object with explicit
load/save behavior. Mixing the two — e.g. letting a user "configure" the
database magic number — would produce broken files, because that number
isn't actually a preference.

---

## 1.6 Annotated walkthrough: `__init__.py` and `indexfile.py`

### `src/dap_db_manager/__init__.py`

```python
"""DAP DB Manager.
...
"""

try:
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:
        from importlib_metadata import version, PackageNotFoundError  # type: ignore

    __version__ = version("dap-db-manager")
except (PackageNotFoundError, ImportError):
    try:
        from pathlib import Path
        import tomllib

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
            __version__ = pyproject_data["project"]["version"]
    except Exception:
        __version__ = "unknown"

__all__ = [
    "cli", "database", "gui", "tagging",
    "config", "constants", "indexfile", "utils",
]
```

Line by line, for anything beyond Chapter 0 basics:

- The whole top-level string in triple quotes is a **module docstring** —
  it documents the package itself (not a function or class), and is what
  `help(dap_db_manager)` would show.
- `try: ... except ImportError:` nested inside another `try/except` is an
  unusual-looking but deliberate pattern: it tries the modern standard
  library location for `importlib.metadata` first, and falls back to an
  older third-party backport (`importlib_metadata`) if the import fails —
  a defensive compatibility shim for older Python versions. `# type: ignore`
  is a comment type checkers (like `mypy`, listed in `pyproject.toml`'s
  dev dependencies) understand as "don't flag the next line even though
  the types look wrong here" — useful exactly in fallback-import code like
  this, where the two modules aren't *quite* type-identical.
- `version("dap-db-manager")` asks Python's packaging metadata (written
  when you `pip install` or `uv sync` the project) what version string was
  recorded — this is how `ddm --version` can report `0.9.2` without that
  number being hardcoded twice.
- If that metadata lookup fails (e.g. you're running the source directly
  without installing it), the `except` block falls back to reading
  `pyproject.toml` manually with `tomllib` (part of the standard library
  since Python 3.11 — note `pyproject.toml`'s `requires-python = ">=3.11"`,
  which is exactly why the project can rely on `tomllib` being built in).
  `Path(__file__).parent.parent.parent` walks up three directory levels
  from this file (`src/dap_db_manager/__init__.py` →
  `src/dap_db_manager/` → `src/` → project root) to find
  `pyproject.toml`.
- `__all__ = [...]` is a list of names this module considers its public
  API. It controls what `from dap_db_manager import *` would import, and
  signals to readers (and tools) "these are the supported entry points,"
  even though here it's mostly documentation — these subpackage/module
  names are already accessible by just importing them directly
  (`from dap_db_manager import config`).

### `src/dap_db_manager/indexfile.py`

This module is where the Rockbox binary index file format
(`database_idx.tcd`) gets turned into — and back from — Python objects.

```python
import struct
import bisect

from .utils import fat_to_mtime, mtime_to_fat
from .constants import (
    MAGIC, TAGS, FILE_TAGS, EMBEDDED_TAGS, SUPPORTED_VERSIONS,
    FLAG_DELETED, FLAG_DIRCACHE, FLAG_DIRTYNUM, FLAG_TRKNUMGEN, FLAG_RESURRECTED,
)
from .tagging.tag.tagfile import TagEntry
import logging
```

- `struct` is the standard-library module for converting between Python
  values and raw bytes laid out exactly as a C struct would — essential
  here because Rockbox's database format *is* a C struct on disk.
- `bisect` is the standard-library binary-search module, used below for
  `O(log n)` sorted insertion.
- The `from .constants import (...)` with parentheses is just a
  multi-line import — Chapter 0 covered single-name imports; this is the
  same mechanism spread across several lines for readability, importing
  several names from `constants.py` at once.

```python
class IndexFile:
    def __init__(self, entries=None, tagfiles=None):
        self.magic = MAGIC
        self.serial = 0
        self.commitid = 0
        self.dirty = 0
        self.entries = entries if entries is not None else []
        self._is_sorted = False
        self.tagfiles = tagfiles if tagfiles is not None else {}
```

Notice `entries=None` as a default, then `entries if entries is not None
else []` inside the body, instead of `entries=[]` directly in the
signature. This sidesteps a classic Python gotcha covered conceptually in
Chapter 0's functions section but worth repeating here in context: a
*mutable* default argument (like a list) is created **once**, when the
function is defined, and shared across every call that doesn't pass its
own value — so two different `IndexFile()` instances would otherwise
silently share and corrupt the *same* list. Using `None` as the default
and building a fresh `[]` inside the function body avoids that entirely.

```python
    def append(self, entry):
        """Append entry to end (marks as unsorted)."""
        self.entries.append(entry)
        self._is_sorted = False

    def append_sorted(self, entry):
        """Insert entry maintaining sort order for incremental updates."""
        if not self.entries or not self._is_sorted:
            self.entries.append(entry)
            self._is_sorted = len(self.entries) == 1
        else:
            idx = bisect.bisect_left(self.entries, entry.sort, key=lambda e: e.sort)
            self.entries.insert(idx, entry)
            self._is_sorted = True
```

`append_sorted` uses `bisect.bisect_left(..., key=lambda e: e.sort)` to
find *where* a new entry belongs in an already-sorted list without
scanning the whole thing — this is how `ddm update` can add new songs to a
huge, already-sorted database quickly (binary search is `O(log n)` instead
of `O(n)`), which matters when "incremental updates" need to stay fast
even on a database with tens of thousands of entries.

```python
    @property
    def size(self):
        """..."""
        return (
            sum(f.size for k, f in self.tagfiles.items() if k != "path")
            + self.header_size
            + self.data_size
        )
```

`@property` (from Chapter 0's decorators section) turns a method into
something you read like an attribute: `index.size` instead of
`index.size()`. Here it's used because `size` isn't stored data — it's
*computed* on demand from the current entries and tag files, so it can
never go stale the way a stored field could if you forgot to update it
after changing `entries`.

```python
    def to_file(self, f):
        self.commitid += 1
        self.dirty = 0
        f.write(
            struct.pack(
                "IIIIII",
                self.magic, self.size, self.count,
                self.serial, self.commitid, self.dirty,
            )
        )
        for entry in self.entries:
            entry.to_file(f)
```

`struct.pack("IIIIII", ...)` packs six values as six unsigned 32-bit
integers (`"I"` repeated six times) in exactly the byte layout Rockbox's C
code reads with its own struct definition. `f` here is a writable binary
file object — note it's passed in rather than opened inside `to_file`,
which is what lets `write()` below decide *how* to open the file
(buffered or not) while `to_file` just focuses on the byte layout:

```python
    def write(self, filename, buffer_size=None):
        if buffer_size is not None:
            with open(filename, "wb", buffering=buffer_size) as f:
                self.to_file(f)
        else:
            with open(filename, "wb") as f:
                self.to_file(f)
```

`with open(filename, "wb") as f:` is a **context manager** (Chapter 0) —
it guarantees the file gets closed (and flushed to disk) even if
`to_file` raises an exception partway through writing.

```python
    @staticmethod
    def from_file(f, tagfiles):
        index = IndexFile(tagfiles=tagfiles)
        index.magic, size, count, index.serial, index.commitid, index.dirty = (
            struct.unpack("IIIIII", f.read(4 * 6))
        )

        if index.magic not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported database version: got {index.magic} (0x{index.magic:08x}). "
                f"Supported versions: {[f'{v} (0x{v:08x})' for v in SUPPORTED_VERSIONS]}. "
                f"File may be corrupted or from a newer Rockbox version."
            )
        ...
```

`@staticmethod` (Chapter 0 decorators again) marks a method that doesn't
need `self` — it's called as `IndexFile.from_file(...)`, not on an
existing instance, because its whole job is to *construct* a new
`IndexFile` from a file, so there's no existing instance to operate on
yet. `struct.unpack("IIIIII", f.read(4 * 6))` is the mirror image of
`struct.pack` above: it reads 24 raw bytes and reinterprets them as six
integers, which is exactly the header this class writes out in `to_file`.
Note the explicit `raise ValueError(...)` with a long, informative
f-string (Chapter 0 covered f-strings and exceptions) — this is
defensive validation: rather than silently misreading a database from an
incompatible Rockbox version, the code fails loudly with a message that
tells you *which* version it found and which versions it actually
supports.

```python
class IndexEntry(dict):
    def __init__(self):
        for field in FILE_TAGS:
            self[field] = None
        for field in EMBEDDED_TAGS:
            self[field] = 0

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value
```

This is the most Chapter-0-adjacent-but-not-quite-covered trick in the
file: `class IndexEntry(dict):` means an `IndexEntry` *is a* `dict` (it
inherits from the built-in dictionary type), so it already supports
`entry["artist"]`. But `__getattr__` and `__setattr__` are **dunder
methods** (double-underscore "magic methods," briefly touched on in
Chapter 0 as the mechanism behind operator overloading) that Python calls
automatically whenever you access or set an attribute that isn't found
normally. By overriding them to read/write `self[name]` instead, every
`entry.artist` attribute access transparently becomes `entry["artist"]`
dictionary access. That's why later in the same file you see both styles
used interchangeably, e.g. `index_entry.mtime = fat_to_mtime(index_entry.mtime)`
reads and writes what is, underneath, just a dictionary key.

```python
    def set_flag(self, flag_bit):
        """Set a flag bit (OR operation)."""
        self["flag"] |= flag_bit

    def clear_flag(self, flag_bit):
        """Clear a flag bit (AND NOT operation)."""
        self["flag"] &= ~flag_bit

    def has_flag(self, flag_bit):
        """Check if a flag bit is set."""
        return bool(self["flag"] & flag_bit)
```

This is classic **bitwise flag** handling, each bit of a single integer
representing one true/false piece of status (`FLAG_DELETED`,
`FLAG_DIRCACHE`, etc. from `constants.py`). `|=` (bitwise OR-assign) turns
a bit on, `&= ~flag_bit` (AND with the bitwise-NOT of the flag) turns a
bit off without touching any other bit, and `&` (AND) checks whether a bit
is currently on. This is how Rockbox packs five independent booleans
(deleted? dircache pointer? numerically dirty? track-number
auto-generated? resurrected stats?) into a single 32-bit integer instead
of five separate fields — a space-saving trick common in binary file
formats and embedded firmware, which is exactly the audience Rockbox is
written for.

```python
    def to_file(self, f):
        for field in FILE_TAGS:
            tagentry = self[field]
            assert isinstance(tagentry, TagEntry) and tagentry.offset is not None
            f.write(struct.pack("I", tagentry.offset))

        for field in EMBEDDED_TAGS:
            value = self[field]
            if field == "mtime":
                value = mtime_to_fat(value)
            f.write(struct.pack("I", value))
```

`assert isinstance(tagentry, TagEntry) and tagentry.offset is not None` is
a cheap runtime sanity check (Chapter 0 covered `assert` and exceptions):
if some code path produced an entry where a file-tag field isn't actually
a proper `TagEntry` with a known file offset, this fails loudly right
here with a traceback pointing at the bad field, instead of silently
writing garbage bytes into the database and failing mysteriously later
when Rockbox tries to load it. The `mtime` special case — converting with
`mtime_to_fat()` only for that one field — is why `utils.py` exists:
Rockbox stores modification times in the old DOS/FAT timestamp format (a
packed date+time integer, explained with bit-shift comments in
`mtime_to_fat`/`fat_to_mtime`), not a Unix timestamp, so every read/write
of that one field needs a conversion the rest of the fields don't.

---

## 1.7 Try It Yourself

Work through these in order. Each one points you at a real file or a real
command — don't skip the "open the file" ones, reading code you've just
been told about is how the folder tour in 1.3 actually sticks.

1. **Run the help text.** `uv run ddm --help`, then `uv run ddm generate
   --help`. Match every subcommand name you see against the table in
   section 1.3 and the corresponding file under `cli/commands/`.

2. **Read the Quick Start again, slowly.** Open `README.md` yourself and
   find the `Quick Start` section. For each of the three numbered steps,
   say out loud which box in the section 1.2 diagram it touches.

3. **Find the default config path.** Open `src/dap_db_manager/config.py`
   and locate `get_config_path()`. What function does it call, and what
   file name does it return? Then check: does that file exist yet on your
   machine (`ls ~/.ddm/` )? If not, why do you think that is (hint: look
   at when `Config.save()` is actually called)?

4. **Trace a constant.** Open `constants.py`, find `MAGIC = 1413695504`.
   Then use `grep -rn "MAGIC" src/dap_db_manager/` (or your editor's
   "find in files") to find every place it's used. What would happen, in
   plain English, if this number were wrong?

5. **Spot the dunder trick.** Open `indexfile.py` and find
   `class IndexEntry(dict):`. In a Python REPL, run:

   ```python
   from dap_db_manager.indexfile import IndexEntry
   e = IndexEntry()
   e.artist = "Test"
   print(e["artist"])   # does this print "Test"?
   print(e)             # what does the whole dict look like?
   ```

   Confirm for yourself that attribute access and dictionary access are
   really hitting the same underlying storage.

6. **Run a single test file.** `pytest tests/test_indexfile.py -v` and
   read a couple of the test function names. What behavior of
   `IndexFile`/`IndexEntry` is each one checking? (You don't need to
   understand every assertion yet — just map test names to the methods
   you just read about.)

7. **Run the whole suite.** `pytest` from the project root. It should
   pass. If any test is skipped, read why (pytest prints a reason for
   skips) — it's often a dependency like `wxpython` not being installed.

8. **Compare `constants.py` and `config.py` side by side.** For each of
   the following, decide which file it *should* live in and why:
   a value that changes Rockbox's binary format vs. a value that changes
   which folder `ddm` remembers you last picked in the GUI vs. a value
   that depends on how much RAM your computer has.

---

**Next:** [Chapter 2 — The CLI Layer](02-cli-layer.md)
