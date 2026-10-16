# Chapter 2 — The CLI Layer: How `ddm` Turns Your Keystrokes Into Action

> **Who this is for:** you've read Chapter 0 (Python basics) and Chapter 1
> (project architecture), and now you want to understand, line by line, what
> happens between you typing `ddm generate --music-dir ~/Music --output ~/db`
> and seeing a progress bar and a summary table.
>
> We will not re-explain `argparse` basics, type hints, dataclasses, decorators,
> or exceptions — Chapter 0 covered those. Every time something *new* shows up
> (subparsers, Pydantic validators, `Enum`, `functools.wraps`-style patterns,
> etc.) we'll stop and explain it the first time, with real quoted code from
> this repository.

---

## 2.1 The Big Picture: One Entry Point, Many Commands

When you install this project, `pyproject.toml` registers a console script:

```toml
[project.scripts]
ddm = "dap_db_manager.cli:main"
```

This is the thing that makes typing `ddm` in your terminal actually run Python
code. It tells pip/uv: "when the user runs `ddm`, import
`dap_db_manager.cli` and call the function named `main`." That's it — there's
no magic beyond "run this one function."

So everything starts in `src/dap_db_manager/cli/__init__.py`, specifically in
`main()`:

```python
def main():
    """Main CLI entry point."""
    parser, args = parse_args()
    # Show help if no command is provided
    if not args.command:
        parser.print_help()
        sys.exit(ExitCode.SUCCESS)
    ...
    try:
        if getattr(args, "command", None) == "peaks":
            res = cmd_peaks(args)
            sys.exit(res if isinstance(res, int) else ExitCode.SUCCESS)
        args.func(args)
    except KeyboardInterrupt:
        logging.info("\nOperation cancelled by user")
        sys.exit(ExitCode.CANCELLED)
    except Exception as e:
        logging.error("Error: %s", e, exc_info=args.log_level == "debug")
        sys.exit(ExitCode.INTERNAL_ERROR)
```

Three things worth noticing immediately, even before we dig into subparsers:

1. **`parse_args()` does all argument-parsing work** and hands back both the
   `parser` object (so help text can still be printed) and `args` (a
   namespace holding whatever flags the user passed).
2. **`args.func(args)`** — this is the key trick that makes subcommands work
   without a giant `if/elif` chain. Every subcommand parser calls
   `.set_defaults(func=cmd_whatever)`, so by the time we get here, `args.func`
   *is* the right Python function for whichever subcommand the user typed.
   Calling `args.func(args)` dispatches to it.
3. **One big `try/except`** wraps the dispatch. If the user hits Ctrl+C
   (`KeyboardInterrupt`), we exit cleanly with a "cancelled" code. Any other
   uncaught exception gets logged and turned into exit code `INTERNAL_ERROR`
   rather than an ugly Python traceback — professional CLI tools shouldn't
   crash the terminal with a wall of Python internals unless you ask for
   debug logging.

---

## 2.2 Subparsers: How One Program Gets Many Commands

### The problem subparsers solve

`ddm` needs to behave completely differently depending on the first word
after it: `ddm generate ...`, `ddm load ...`, `ddm validate ...`, and so on.
Each of those has its *own* set of flags (`generate` needs `--music-dir`,
`validate` needs `--db-dir` and `-q/--quiet`, etc.). You don't want one giant
parser with every possible flag from every command all mixed together — users
would get confused about which flags apply to which command, and `--help`
text would be a mess.

**Subparsers** are argparse's built-in solution: a "parser of parsers." You
create one main parser, ask it for a *subparsers object*, and then add a
separate, independent parser for each subcommand. Here's the real code that
sets this up:

```python
# Main parser
parser = argparse.ArgumentParser(
    prog="ddm",
    usage="ddm <command> [options]",
    description="DAP DB Manager - Generate and manage Rockbox database files",
    formatter_class=RichRawHelpFormatter,
    add_help=False,
)

# Add global options to main parser
main_global_group = parser.add_argument_group("Global Options")
add_global_options(main_global_group)

# Subcommands
subparsers = parser.add_subparsers(
    title="Commands",
    dest="command",
    metavar="",
)
```

Breaking this down:

- `argparse.ArgumentParser(...)` creates the *top-level* parser — the one
  that handles things like `ddm --version` or `ddm --help` before any
  subcommand is even mentioned.
- `parser.add_subparsers(title="Commands", dest="command", metavar="")`
  returns a special "subparsers action" object. Think of it as a factory for
  creating child parsers. The important argument here is `dest="command"`:
  whatever subcommand name the user typed (`"generate"`, `"load"`, etc.) gets
  stored on the parsed result as `args.command`. That's exactly the attribute
  `main()` checks (`if not args.command:`) to decide whether to print help.

### Registering one subcommand

Each subcommand is created by calling `subparsers.add_parser(...)`, which
returns a **brand new, independent `ArgumentParser`** — you then add
arguments to *that* object exactly like you learned with top-level parsers in
Chapter 0. Here is the real `generate` subcommand being built:

```python
generate_parser = subparsers.add_parser(
    "generate",
    help="Generate Rockbox database from music folder (supports cross-compilation with --dap-root)",
    usage="ddm generate --music-dir <path/to/source/music/dir> --output <path/to/target/database/dir> [options]",
    description="Scan music folder and generate Rockbox database files. ...",
    formatter_class=RichHelpFormatter,
    add_help=False,
)
generate_required = generate_parser.add_argument_group("Required")
generate_required.add_argument(
    "--music-dir", type=Path, required=True, help="Path to music directory to scan"
)
generate_required.add_argument(
    "-o", "--output", type=Path, required=True, help="Target directory for database files",
)
```

A few details that are new or worth re-emphasizing:

- `"generate"` is the literal string the user types: `ddm generate ...`.
- `subparsers.add_parser(...)` gives back a parser just like the top-level
  one, so you can call `.add_argument_group(...)` and `.add_argument(...)` on
  it exactly as you'd expect from Chapter 0's argparse primer.
- `type=Path` — `Path` comes from Python's standard `pathlib` module. Passing
  `type=Path` to `add_argument` tells argparse: "whatever string the user
  types for this flag, run it through `Path(...)` before storing it." So
  `args.music_dir` isn't a plain string like `"~/Music"` — it's already a
  `pathlib.Path` object with useful methods like `.exists()`, `.is_dir()`,
  `.resolve()`. You'll see all of those used throughout the command files.
- `required=True` means argparse will error out (with a helpful usage
  message) if the user forgets to pass `--music-dir`.
- `.add_argument_group("Required")` doesn't affect *parsing* at all — it's
  purely cosmetic, so `--help` output groups "Required" flags separately from
  "Options" and "Global Options". You'll see this pattern repeated for every
  command in the file.

Finally, the crucial wiring step:

```python
generate_parser.set_defaults(func=cmd_generate)
```

`set_defaults(func=cmd_generate)` says: "whenever this subparser is the one
that matched, set `args.func` to the Python function `cmd_generate`." This is
*exactly* the trick `main()` relies on (`args.func(args)`). Every single
subcommand in this project ends its setup block the same way — `load_parser`
→ `cmd_load`, `validate_parser` → `cmd_validate`, `write_parser` → `cmd_write`,
and so on. This means adding a brand-new command to `ddm` is a three-step
recipe: (1) write a `cmd_xxx(args)` function somewhere in `cli/commands/`,
(2) register a subparser for it with whatever flags it needs, (3) call
`.set_defaults(func=cmd_xxx)`.

### A subparser *of* a subparser: `peaks`

The `peaks` command is special — it has its own two "actions,"
`ddm peaks generate` and `ddm peaks inspect`. This is implemented by calling
`add_subparsers` *again*, on the `peaks_parser` itself:

```python
peaks_parser = subparsers.add_parser("peaks", ...)
peaks_subparsers = peaks_parser.add_subparsers(
    title="Actions",
    dest="peaks_action",
    metavar="",
)

peaks_generate_parser = peaks_subparsers.add_parser("generate", ...)
...
peaks_inspect_parser = peaks_subparsers.add_parser("inspect", ...)
```

Subparsers can nest arbitrarily deep — each one is just a normal parser that
happens to have been created via `add_parser` instead of
`argparse.ArgumentParser()` directly. Here `dest="peaks_action"` stores which
of `generate`/`inspect` was picked into `args.peaks_action`, which `cmd_peaks`
later reads with `getattr(args, "peaks_action", None)`.

Notice also that `main()` special-cases `peaks`:

```python
if getattr(args, "command", None) == "peaks":
    res = cmd_peaks(args)
    sys.exit(res if isinstance(res, int) else ExitCode.SUCCESS)
args.func(args)
```

Why the special case? Every *other* command function (`cmd_generate`,
`cmd_load`, ...) calls `sys.exit(...)` itself internally to set the final
process exit code. `cmd_peaks`, on the other hand, is written in a more
ordinary style and just **returns** an integer (`0` for success, `1` for
failure) instead of calling `sys.exit`. So `main()` has to call it, check its
return value, and exit itself. This is a good lesson: even within one
project, small stylistic differences between modules are normal — just read
carefully rather than assuming total consistency.

### A reusable helper: `add_global_options`

Every subcommand repeats `-h/--help`, `-v/--version`, `-l/--log-level`,
`--cache-size`, and `--json`. Instead of copy-pasting those five
`add_argument` calls into every subcommand block, the project factors them
into one function:

```python
def add_global_options(parser_group):
    """Add global options to an argument group."""
    parser_group.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit",
    )
    parser_group.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}",
    )
    parser_group.add_argument(
        "-l", "--log-level", default=None, help="Set logging level (disabled by default)",
    )
    parser_group.add_argument(
        "--cache-size", type=int, metavar="SIZE",
        help="Override tag cache size (default: from config, typically 50000)",
    )
    parser_group.add_argument(
        "--json", action="store_true",
        help="Output results in JSON format for machine parsing (suppresses progress indicators)",
    )
```

and then every subcommand ends its setup with something like:

```python
generate_global = generate_parser.add_argument_group("Global Options")
add_global_options(generate_global)
```

This is the **DRY principle** in action (we'll define that term properly in
§2.4) — "Don't Repeat Yourself." If tomorrow you want to add a new global
flag, say `--no-color`, you add it in exactly one place
(`add_global_options`) and every subcommand instantly gets it.

### `action="help"`, `action="version"`, `action="store_true"`, `BooleanOptionalAction`

A few argparse `action=` values appear that Chapter 0 didn't cover in depth:

- `action="help"` — manually triggers the same thing `-h` normally does
  automatically. The project sets `add_help=False` on every parser (so
  argparse doesn't add its own default `-h`), and instead adds its *own*
  `-h/--help` via `add_global_options`, so it can control exactly where it
  appears in the help text groups.
- `action="version"` — when the user passes `-v`/`--version`, argparse
  prints the `version=` string and exits immediately, without ever calling
  your command function. `f"%(prog)s {__version__}"` is a format string
  argparse itself fills in — `%(prog)s` becomes `"ddm"`.
- `action="store_true"` — the flag takes no value; if present, the attribute
  becomes `True` (e.g. `--json` → `args.json == True`), otherwise `False`.
- `action=argparse.BooleanOptionalAction` is a newer one (Python 3.9+) used
  for the `--peaks` flag:

  ```python
  generate_options.add_argument(
      "--peaks",
      action=argparse.BooleanOptionalAction,
      default=True,
      help="Generate waveform peak cache files (.peaks) for tracks (default: enabled)",
  )
  ```

  This automatically generates **both** `--peaks` and `--no-peaks` from one
  `add_argument` call. Pass `--peaks` → `args.peaks = True`. Pass
  `--no-peaks` → `args.peaks = False`. Pass neither → falls back to
  `default=True`. This is much nicer than manually defining two separate
  flags that both set the same destination.

### `rich_argparse`: prettier `--help` output for free

At the top of the file:

```python
from rich_argparse import RichHelpFormatter
...
class RichRawHelpFormatter(RichHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Combines Rich formatting with the ability to keep line breaks (Raw)."""
    pass
```

`rich-argparse` is a small third-party package that plugs into argparse's
`formatter_class=` hook (which Chapter 0 may not have covered: argparse lets
you swap out the class responsible for *rendering* `--help` text, without
changing how parsing itself works). `RichHelpFormatter` renders argparse's
help text with colors, bold section titles, and nicely wrapped columns using
the `rich` library under the hood — all for free, just by passing
`formatter_class=RichHelpFormatter` to `ArgumentParser(...)` / `add_parser(...)`.

`RichRawHelpFormatter` is a one-off subclass defined right here that
**combines two parent classes** — this is Python multiple inheritance,
briefly: a class can inherit behavior from more than one parent at once. Here
it mixes `RichHelpFormatter`'s coloring with
`argparse.RawDescriptionHelpFormatter`'s "don't auto-reflow my newlines"
behavior, so the long, deliberately multi-line `description=` text on the
main parser keeps its manual line breaks instead of getting crammed into one
paragraph. The `pass` statement means "this subclass adds no new code of its
own — it exists purely to combine its parents' behavior."

---

## 2.3 Worked Example: Tracing `generate` End-to-End

`generate` is the flagship command, so let's trace a full run of:

```bash
ddm generate --music-dir ~/Music --output ~/rockbox-db
```

step by step, through `cmd_generate` in
`src/dap_db_manager/cli/commands/generate.py`.

### Step 1 — argparse hands off a `Namespace`

By the time `cmd_generate(args)` is called, `args` is an
`argparse.Namespace` object (a simple container with attributes) with, among
others:

- `args.music_dir` → `Path("~/Music")` *(not yet expanded — see below)*
- `args.output` → `Path("~/rockbox-db")`
- `args.json` → `False` (since `--json` wasn't passed)
- `args.config`, `args.load_tags`, `args.save_tags`, `args.no_parallel`,
  `args.no_preserve_stats`, `args.preserve_stats_from`, `args.workers`,
  `args.dap_root`, `args.peaks` → whatever defaults/flags were set

### Step 2 — validate inputs, fail fast with exit codes

```python
music_path = Path(args.music_dir).resolve()

if not music_path.exists():
    if use_json:
        json_output(
            ErrorResponse(
                error="invalid_input",
                message=f"Music path does not exist: {music_path}",
            ),
            ExitCode.INVALID_INPUT,
        )
    logging.error("Music path does not exist: %s", music_path)
    sys.exit(ExitCode.INVALID_INPUT)
```

`.resolve()` turns a possibly-relative, possibly-`~`-containing path into an
absolute, canonical one. This pattern — "check a precondition, and if it
fails, emit either JSON or a log message depending on `--json`, then
`sys.exit` with a specific numeric code" — repeats dozens of times across
every command file in this project. `ExitCode` (from `cli/utils.py`, covered
in §2.4) gives these numbers names instead of magic numbers like `10` or `20`
scattered everywhere.

### Step 3 — load configuration and detect "cross-compilation" mode

```python
dap_root = None
if hasattr(args, "dap_root") and args.dap_root:
    dap_root = str(args.dap_root.resolve())
    ...
config = Config()
if not config.is_mount_notation_configured():
    ...
    config.auto_detect_mount_notation(device_path, callback=...)
```

`hasattr(args, "dap_root")` is a defensive check: "does this Namespace even
have a `dap_root` attribute?" It's a leftover safety net since `args` is built
dynamically by argparse and not every caller is guaranteed to populate every
attribute (useful in tests that construct a bare `argparse.Namespace` by
hand, as you saw in `tests/test_cli_commands.py`). `Config` is the project's
settings object (Chapter 1 territory) — not CLI-specific, so we won't go
deeper here.

### Step 4 — decide whether to preserve existing runtime stats

```python
stats_preserver = None
if not no_preserve:
    stats_dir = (
        str(Path(preserve_from).resolve()) if preserve_from else str(output_path)
    )
    existing_stats = read_existing_stats(stats_dir, dap_root=dap_root)
    if existing_stats:
        stats_preserver = StatsPreserver(existing_stats)
```

This is business logic (reading an *existing* database's play counts/ratings
before overwriting it) that belongs conceptually to the database engine
(Chapter 3), but notice the CLI's job here: it just orchestrates — decides
*which directory* to read stats from based on which flags were passed, and
hands the result to the `Database` object as a constructor argument, next.

### Step 5 — construct the `Database` object

```python
db = Database(
    config=config,
    dap_root=dap_root,
    stats_preserver=stats_preserver,
    max_workers=workers,
)
```

This is the CLI's one and only touchpoint with the actual database engine
for this command. Everything from here on is about (a) feeding the `Database`
object data, and (b) reporting what it did. We'll go deep into `Database`
itself in Chapter 3 — here, just notice how thin this call is: the CLI layer
does *not* know or care how scanning/writing actually works internally.

### Step 6 — scan the music directory, with a live progress bar

```python
console = Console(quiet=use_json)
...
with Progress(
    TextColumn("[cyan]Scanning music directory..."),
    TimeElapsedColumn(),
    console=console,
) as progress:
    scan_task = progress.add_task("", total=None)
    callback = ProgressCallback(progress, scan_task)

    parallel_flag = not (hasattr(args, "no_parallel") and args.no_parallel)
    db.add_dir(
        str(music_path),
        dircallback=callback,
        filecallback=callback,
        parallel=parallel_flag,
    )

    progress.update(scan_task, total=callback.count, completed=callback.count)
```

New concept: `rich.progress.Progress` is a **context manager** (the
`with ... as progress:` pattern Chapter 0 touched on for files — here it's
used for terminal UI instead). While the `with` block is active, it redraws
an animated progress indicator in your terminal; when the block exits, it
cleans the display up automatically. `progress.add_task(...)` registers one
progress "row" and returns an id (`scan_task`) you use to update it later.

`Console(quiet=use_json)` — `rich.console.Console` is the general-purpose
"smart print" object used throughout this project instead of plain `print()`.
Passing `quiet=True` makes every `console.print(...)` call on that object a
silent no-op, which is exactly how `--json` mode suppresses all the pretty
terminal output: rather than littering the code with
`if not use_json: console.print(...)` everywhere, you build one `Console`
with `quiet` set appropriately once, and every later `console.print(...)`
call automatically respects it.

`db.add_dir(..., dircallback=callback, filecallback=callback, ...)` is where
the database engine walks the filesystem. Instead of the engine printing
anything itself, it calls `callback(...)` every time it enters a new
directory or finishes a file. That callback is `ProgressCallback`, from
`cli/callbacks.py` — we'll dissect it fully in §2.4. This is the
**callback pattern**: the engine stays decoupled from *how* progress is
displayed (a progress bar? a log line? nothing at all in tests?) by just
calling a function you hand it.

### Step 7 — generate database entries, another progress bar

```python
with Progress(
    SpinnerColumn(),
    TextColumn("[cyan]Generating database entries..."),
    BarColumn(),
    TextColumn("{task.completed}/{task.total}"),
    console=console,
) as progress:
    gen_task = progress.add_task("generate", total=total_files)

    def gen_callback(current_count, total_count):
        progress.update(gen_task, completed=current_count)

    db.generate_database(callback=gen_callback, parallel=parallel_flag)
```

Here the callback is defined inline as a tiny local function instead of a
class — same pattern (pass a function, let the engine call it to report
progress), just a simpler case since this one doesn't need to track extra
state between calls the way `ProgressCallback` does.

### Step 8 — write the database files to disk

```python
output_path.mkdir(parents=True, exist_ok=True)
...
with Progress(...) as progress:
    write_task = progress.add_task("write", total=len(FILE_TAGS) + 1)

    def write_callback(msg, **kwargs):
        if "done" in str(msg):
            progress.advance(write_task, 1)
        elif logging.getLogger().level <= logging.DEBUG:
            log_callback(msg, **kwargs)

    db.write(str(output_path), callback=write_callback)
```

`Path.mkdir(parents=True, exist_ok=True)` creates the output directory
(and any missing parent directories) without erroring if it already exists —
a very common pattern whenever a CLI tool needs to guarantee a destination
folder exists before writing to it.

### Step 9 — optionally generate waveform peaks

```python
if getattr(args, "peaks", False):
    try:
        peaks_dir = resolve_peaks_dir(output_path)
        generate_peaks_for_library(
            music_dir=music_path,
            output_dir=peaks_dir,
            dap_root=getattr(args, "dap_root", None),
            jobs=workers,
        )
    except Exception as e:
        logging.warning("Waveform peaks generation encountered an error: %s", e)
```

This is a *non-fatal* side feature — note that failures here are only logged
as a `warning`, not treated as a hard error that aborts the whole command (no
`sys.exit` in the `except`). The reasoning: a successful database is more
important than waveform peaks, so a peaks-generation glitch shouldn't make an
otherwise-successful `generate` run report failure.

### Step 10 — report results (JSON *or* rich table) and exit

```python
duration_ms = int((time.time() - start_time) * 1000)

if use_json:
    tag_counts = {}
    for field in FILE_TAGS:
        tag_counts[field] = len(db.tagfiles[field].entries)

    if failed_files > total_files * 0.1:
        json_output(
            GenerateSuccessResponse(
                status="completed_with_errors",
                input_dir=str(music_path),
                output_dir=str(output_path),
                tracks=db.index.count,
                files_scanned=total_files,
                files_failed=failed_files,
                duration_ms=duration_ms,
                warning=f"High failure rate: {failed_files}/{total_files} files failed",
                **tag_counts,
            ),
            ExitCode.DATA_ERROR,
        )

    json_output(
        GenerateSuccessResponse(
            status="success",
            input_dir=str(music_path),
            output_dir=str(output_path),
            tracks=db.index.count,
            files_scanned=total_files,
            files_failed=failed_files,
            duration_ms=duration_ms,
            **tag_counts,
        ),
        ExitCode.SUCCESS,
    )

# Print summary table (normal mode)
table = Table(title="\nDatabase Summary")
table.add_column("Field", style="cyan")
table.add_column("Value", style="magenta")

table.add_row("Input", str(music_path))
table.add_row("Output", str(output_path))
table.add_row("Files", str(total_files))
table.add_row("Entries", str(db.index.count))
table.add_row("Failed", str(failed_files))
...
console.print(table)

if failed_files > total_files * 0.1:
    logging.warning("High failure rate: %s/%s files failed", failed_files, total_files)
    sys.exit(ExitCode.DATA_ERROR)

sys.exit(ExitCode.SUCCESS)
```

Two new-ish details here worth pausing on:

- **`**tag_counts`** — this is Python's "dictionary unpacking" syntax. If
  `tag_counts = {"artist": 42, "album": 10}`, then
  `GenerateSuccessResponse(..., **tag_counts)` is exactly equivalent to
  writing `GenerateSuccessResponse(..., artist=42, album=10)`. It's used here
  because `GenerateSuccessResponse` has optional fields for every tag type
  (`artist`, `album`, `genre`, ...), and `tag_counts` is built dynamically
  from `FILE_TAGS`, so unpacking it as keyword arguments avoids hand-writing
  nine separate `artist=..., album=..., genre=...` lines.
- **`rich.table.Table`** — build a table by declaring columns
  (`table.add_column(name, style=...)`) then adding rows
  (`table.add_row(val1, val2, ...)`), and print it with `console.print(table)`.
  `rich` figures out column widths and alignment automatically. This is the
  non-JSON "pretty" counterpart to the structured `GenerateSuccessResponse`
  JSON output — same underlying numbers (`total_files`, `db.index.count`,
  `failed_files`), two different presentations, chosen by the `use_json`
  flag that was read all the way back at the top of the function.

**The overall shape to internalize:** every command function follows the
same rhythm — *validate inputs → fail fast with a specific exit code → do the
actual work by delegating to the database/engine layer, reporting progress
via callbacks → build either a Pydantic response (for `--json`) or a rich
table/console output (for humans) → `sys.exit` with a meaningful code.*

---

## 2.4 `cli/schemas.py`: Pydantic Models for `--json` Output

### What problem is this solving?

Every command supports a `--json` flag so that scripts, other programs, or
automation can call `ddm` and parse structured output instead of
scraping colored terminal text. But hand-building dictionaries and calling
`json.dumps(...)` everywhere is error-prone: fields get typo'd, types drift
(is `entries` a string or an int this time?), and nothing checks that
`status="success"` is actually one of the allowed values.

**Pydantic** solves this: you declare a *model* — a class describing exactly
which fields exist, their types, and validation rules — and Pydantic (a) 
validates that data matches those rules when you construct the model, and
(b) gives you `.model_dump_json()` to serialize it correctly. The docstring
at the top of the file explains this directly:

```python
"""Pydantic schemas for JSON output validation.
...
Using Pydantic ensures consistent, validated, and well-documented JSON responses.

All --json output from CLI commands now uses these Pydantic models which provide:
- Automatic type validation (e.g., entries must be >= 0)
- Consistent JSON structure across all commands
- Clear documentation of expected fields
- Runtime validation to catch programming errors early
- Exclude None values automatically for cleaner output
"""
```

### Anatomy of one model

```python
class ErrorResponse(BaseModel):
    """Standard error response for all commands."""

    status: Literal["error"] = "error"
    error: str = Field(
        description="Machine-readable error code",
        examples=["invalid_input", "invalid_config", "data_error", "write_failed"],
    )
    message: str = Field(description="Human-readable error description")
```

- `class ErrorResponse(BaseModel):` — inheriting from Pydantic's `BaseModel`
  is what turns an ordinary-looking class (syntactically similar to the
  `@dataclass`-decorated classes from Chapter 0) into a *validated* model.
  Unlike a plain `@dataclass`, `BaseModel` subclasses actively check, at
  construction time, that every value you pass in actually matches its
  declared type — and raise a clear `ValidationError` if not.
- `status: Literal["error"] = "error"` — **`Literal`** (new concept) is a
  type hint meaning "this value isn't just *any* string, it must be exactly
  one of these specific literal values." `Literal["error"]` means the only
  legal value is the exact string `"error"`. Combined with `= "error"` as a
  default, you basically never need to set this field yourself — it's always
  there, always correct, and if you ever try to construct
  `ErrorResponse(status="oops", ...)` Pydantic will reject it immediately.
- `error: str = Field(description=..., examples=...)` — **`Field(...)`** is
  Pydantic's way of attaching metadata and extra validation rules to a field
  beyond just its type. Here it's purely documentation (`description`,
  `examples` — these even show up if you ever generate OpenAPI/JSON-Schema
  docs from the model), but `Field` can also enforce constraints, as seen
  next.

### Field validation with constraints

```python
class ValidationSuccessResponse(BaseModel):
    status: Literal["valid"] = "valid"
    db_path: str = Field(description="Path to validated database")
    entries: int = Field(ge=0, description="Number of entries in the index")
    warnings: Optional[List[str]] = Field(
        default=None, description="Optional warnings (non-fatal issues)"
    )
    tag_counts: Optional[Dict[str, int]] = Field(
        default=None, description="Counts for each tag file"
    )
```

- `Field(ge=0, ...)` — `ge` stands for "greater than or equal to." This is a
  real **validator**: if some bug in the code ever tried to construct
  `ValidationSuccessResponse(entries=-5, ...)`, Pydantic raises an error
  immediately rather than letting a nonsensical negative entry count leak
  into JSON output that some downstream script trusts. This is the
  "Runtime validation to catch programming errors early" benefit mentioned
  in the module docstring, made concrete.
- `Optional[List[str]]` — `Optional[X]` is shorthand for "either an `X`, or
  `None`." `List[str]` means "a list containing strings." So
  `warnings: Optional[List[str]] = Field(default=None, ...)` means: "this
  field is either a list of warning strings, or absent/`None` entirely,
  defaulting to `None` if not provided."
- `Optional[Dict[str, int]]` similarly means "either a dictionary mapping
  string keys to int values (e.g. `{"artist": 42}`), or `None`."

### Extra/dynamic fields: `model_config = {"extra": "allow"}`

```python
class GenerateSuccessResponse(BaseModel):
    ...
    artist: Optional[int] = Field(default=None, description="Artist tag count")
    album: Optional[int] = Field(default=None, description="Album tag count")
    ...
    model_config = {
        "extra": "allow"  # Allow additional fields for tag counts
    }
```

By default, Pydantic models are strict about unknown fields — if you try to
construct a model with a keyword argument it doesn't recognize, it errors.
`model_config = {"extra": "allow"}` relaxes that for this specific model,
because `generate`'s output has a known *core* set of fields (`status`,
`tracks`, `files_scanned`, ...) plus a *variable* set of tag-count fields
that could technically expand if more tag types are added later. Declaring
the common ones explicitly (so they're documented and type-checked) while
allowing extras gives a middle ground between full rigidity and total
freedom.

### How the model actually becomes JSON on screen

Look back at `cli/utils.py`'s `json_output`:

```python
def json_output(data: Union[BaseModel, dict], exit_code: int = 0) -> None:
    if isinstance(data, BaseModel):
        json_str = data.model_dump_json(indent=2, exclude_none=True)
        print(json_str)
    else:
        json_str = json.dumps(data, indent=2)
        ...
    sys.exit(exit_code)
```

`.model_dump_json(indent=2, exclude_none=True)` is a Pydantic method:
"serialize me to a JSON string, pretty-printed with 2-space indentation, and
leave out any field whose value is `None`." That last part is why, for
example, `ValidationSuccessResponse`'s optional `warnings`/`tag_counts`
fields don't clutter every single JSON response with `"warnings": null` —
they simply vanish from the output when unset.

### The union types at the bottom

```python
ValidateResponse = ValidationSuccessResponse | ValidationFailedResponse | ErrorResponse
LoadResponse = LoadSuccessResponse | ErrorResponse
GenerateResponse = GenerateSuccessResponse | ErrorResponse
WriteResponse = WriteSuccessResponse | ErrorResponse
UpdateResponse = UpdateSuccessResponse | ErrorResponse
```

The `X | Y` syntax is Python's modern "union type" shorthand (Python 3.10+):
`ValidateResponse` means "a value that is *either* a
`ValidationSuccessResponse`, *or* a `ValidationFailedResponse`, *or* an
`ErrorResponse`." These aliases exist purely as documentation/type-hinting
sugar — they describe, in one line, "here are all the possible shapes of
JSON this command could ever emit" — handy for anyone (including an IDE's
type checker) reading the command functions.

---

## 2.5 `cli/callbacks.py` and `cli/utils.py`: Shared Plumbing

### Why factor this code out at all? (the DRY principle)

**DRY** stands for **"Don't Repeat Yourself."** It's a core software
engineering principle: if the same logic (or structurally similar logic)
appears in multiple places, you're one bug-fix away from fixing it in one
spot and forgetting the others — which is how inconsistent, hard-to-maintain
code happens. The fix is to write that logic *once*, in a shared module, and
have every place that needs it simply call/import it.

In this project, nearly every one of the eight commands needs to:

1. turn progress updates from the database engine into either a rich
   progress bar, a plain log line, or silence (`callbacks.py`), and
2. configure logging, define exit codes, and emit `--json` output
   consistently (`utils.py`).

Rather than reimplementing those per command, they live in two small shared
modules that every `cmd_xxx` function imports from.

### `cli/callbacks.py`: three ways to react to engine progress

The database engine (Chapter 3) doesn't know or care about terminals — it
just calls a `callback(message)` function whenever something noteworthy
happens (entered a new directory, finished processing a file, has a total
count to report, etc.), passing either a string (a path) or an integer (a
count) as `message`. The CLI layer provides three different *implementations*
of "what to do when called":

```python
def log_callback(message, **kwargs):
    """Callback function for database operations that logs instead of printing."""
    if isinstance(message, int):
        logging.info("Processing %s items...", message)
    else:
        logging.debug("%s", message)
```

The simplest one: route everything through Python's standard `logging`
module instead of printing directly. `isinstance(message, int)` is how it
tells the two kinds of messages apart — no special "message type" class is
used, just plain duck-typing on whatever Python type was passed.

```python
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
            self.progress.update(self.task_id, total=message)
```

New concept: **`__call__`**. Defining a `__call__(self, ...)` method on a
class makes *instances* of that class callable, just like a function. So
after `callback = ProgressCallback(progress, scan_task)`, you can write
`callback("/some/path")` or `callback(42)` directly — Python translates that
into `callback.__call__("/some/path")` automatically. This is why
`cmd_generate` can pass `callback` (an *object*) into `db.add_dir(dircallback=callback, filecallback=callback, ...)`, even though the engine code just
calls it like a plain function (`callback(message)`): to the engine, an
object with `__call__` and a plain function are indistinguishable. The
benefit here, compared to `log_callback` being a bare function, is that
`ProgressCallback` needs to **remember state between calls** — the current
file count, which directory it's scanning — and a class with `__init__` to
set up instance attributes (`self.count`, `self.last_dir`, ...) is the
natural way to carry state like that across many calls, whereas a plain
function would need some external mutable variable to track it.

```python
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
                    logging.info("Processed %s files from %s", self.count, self.last_dir)
```

A third variant: count progress quietly, only logging a line every 100
files (`self.count % 100 == 0` — the `%` modulo operator, "is this a
multiple of 100?"). Used where a progress bar would be inappropriate (e.g.
scripted/non-interactive contexts) but you still want *some* visibility
without flooding the terminal with one line per file.

The lesson from `callbacks.py`: the engine is written once, against a single
generic "call this function with progress info" contract, and the CLI layer
swaps in whichever *presentation* makes sense per command and per mode
(interactive progress bar vs. quiet logging vs. silent counting) — without
touching the engine code at all.

### `cli/utils.py`: exit codes, logging setup, and JSON output

```python
class ExitCode(IntEnum):
    """Exit codes for CLI commands."""

    SUCCESS = 0

    INVALID_INPUT = 10
    INVALID_CONFIG = 11

    DATA_ERROR = 20
    MISSING_TAGS = 21

    GENERATION_FAILED = 30
    VALIDATION_FAILED = 31
    WRITE_FAILED = 32

    INTERNAL_ERROR = 40
    CANCELLED = 41
```

New concept: **`Enum`** (here, specifically `IntEnum`, from Python's standard
`enum` module). An `Enum` lets you give meaningful *names* to a fixed set of
related constant values, instead of scattering bare numbers (`10`, `20`,
`30`...) throughout the codebase where nobody can remember what `20` means
without checking a comment. `IntEnum` is a flavor of `Enum` whose members
*also* behave like plain integers wherever an integer is expected — which
matters here because `sys.exit(code)` and shell exit codes are fundamentally
just small integers. So `sys.exit(ExitCode.INVALID_INPUT)` behaves
identically to `sys.exit(10)`, but reads far more clearly at the call site,
and if two different pieces of code need "the invalid input code," they're
guaranteed to agree because they both reference the same named member.

Why specific numeric ranges (`10-19` for input errors, `20-29` for data
errors, `30-39` for operation failures, `40-49` for internal errors)? This is
a deliberate convention so that automation calling `ddm` can distinguish
*categories* of failure just from the exit code's range, without parsing any
text at all — e.g. "anything in the 10s means the user needs to fix their
command-line arguments," "anything in the 20s means the input data itself
was bad."

```python
def setup_logging(level: str) -> None:
    """Configure logging based on user-specified level."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
```

`getattr(logging, level.upper(), None)` is a neat trick: the standard
`logging` module defines module-level constants named `DEBUG`, `INFO`,
`WARNING`, `ERROR`, `CRITICAL` (all plain integers). If the user passes
`--log-level debug`, `level.upper()` becomes `"DEBUG"`, and
`getattr(logging, "DEBUG", None)` looks up `logging.DEBUG` by *name* — i.e.
it converts a user-typed string into the matching module constant
dynamically, without a manual `if/elif` chain mapping strings to levels. If
the user typos something like `--log-level dbeug`, `getattr` returns the
fallback `None` instead of crashing, and the explicit
`if not isinstance(numeric_level, int): raise ValueError(...)` check turns
that into a clear, specific error.

Note also `stream=sys.stderr` — log messages are deliberately sent to
*stderr*, not stdout. This is important: when `--json` mode is active and
something still needs to print plain JSON to *stdout* for a script to parse,
any log noise going to stderr instead keeps stdout perfectly clean JSON with
nothing else mixed in.

```python
def json_output(data: Union[BaseModel, dict], exit_code: int = 0) -> None:
    """Output JSON to stdout and exit with specified code."""
    if isinstance(data, BaseModel):
        json_str = data.model_dump_json(indent=2, exclude_none=True)
        print(json_str)
    else:
        print(json.dumps(data, indent=2))
    sys.exit(exit_code)
```

We already looked at this above in the schemas discussion — worth repeating
here that it's the *single* function every command calls whenever it needs
to emit `--json` output and stop. Because it's centralized, if the project
ever wants to change the JSON format (say, switch to compact single-line
JSON), there's exactly one function to edit, and every command's `--json`
mode updates simultaneously — DRY again.

---

## 2.6 The Other Commands, at a Glance

| Command | One-line purpose | Key file |
|---|---|---|
| `generate` | Scan a music folder from scratch and build a brand-new Rockbox database (with optional cross-compilation via `--dap-root` and waveform peaks). | `cli/commands/generate.py` |
| `update` | Incrementally re-scan a music folder against an *existing* database: add new files, mark missing ones deleted, detect renames/retags — while preserving play counts and ratings. Faster than a full `generate`. | `cli/commands/update.py` |
| `load` | Read an existing database directory and print summary info (entry count, per-tag-file counts) without modifying anything. | `cli/commands/load.py` |
| `write` | Load a database from one directory and copy/rewrite it to a different destination directory. | `cli/commands/write.py` |
| `validate` | Check a database directory for structural corruption/consistency issues (missing files, bad counts, etc.) and report errors/warnings. | `cli/commands/validate.py` |
| `inspect` | Low-level debugging tool: parse and dump the raw binary structure of one specific `.tcd` database file (index or a tag file), including header fields and sample entries. | `cli/commands/inspect.py` |
| `detect-mounts` | Analyze an existing database's stored paths to figure out (or manually set) the device's Rockbox "mount notation" (e.g. `/<HDD0>`), saving it to config for future `generate`/`update` runs. | `cli/commands/detect_mounts.py` |
| `peaks` | Sub-grouped command (`peaks generate` / `peaks inspect`) for batch-generating or inspecting the small `.peaks` waveform-cache sidecar files used for fast UI waveform rendering. | `cli/commands/peaks.py` |

Each of these follows the same overall shape you already traced in detail
for `generate`: validate → delegate to the engine → report via rich output
or Pydantic/`--json`. Once you understand `generate`, reading any of the
others is mostly a matter of recognizing the same pattern with different
specifics.

---

## 2.7 `rich` and `rich-argparse`: Why the Terminal Looks Nice

We've already seen the two main building blocks in action, but let's name
them explicitly:

- **`rich.console.Console`** — a smarter `print()`. Supports inline markup
  like `console.print("[green]✓[/green] Scanned 120 files")`, where
  `[green]...[/green]` colors that segment of text green in supporting
  terminals, and is silently ignored (or stripped) in non-interactive
  contexts. Constructing it with `Console(quiet=use_json)` is the project's
  go-to trick for making an entire command's "pretty" output vanish under
  `--json` without sprinkling `if not use_json:` checks everywhere.

- **`rich.progress.Progress`** — animated progress bars/spinners, built from
  composable "columns" like `SpinnerColumn()`, `TextColumn(...)`,
  `BarColumn()`, `TimeElapsedColumn()`. You've already seen several real
  examples in `cmd_generate` — each `Progress(...)` call picks whichever
  combination of columns makes sense (a plain scanning spinner doesn't need
  a percentage bar; a "generating N/total" step does).

- **`rich.table.Table`** — declarative table building:
  `table.add_column(name, style=color)` then `table.add_row(val, val, ...)`,
  finally `console.print(table)`. Used for the `generate` summary table, the
  `detect-mounts` mount list, and the `peaks` generation/inspection
  summaries.

- **`rich.panel.Panel`** — a bordered box around a block of text, used in
  `detect_mounts.py` for calling out warnings or "no database found" guidance
  with extra visual emphasis:

  ```python
  console.print(
      Panel(
          f"[yellow]No database found in {db_path}[/yellow]\n\n"
          f"Cannot auto-detect mount notation without an existing database.\n\n"
          f"[bold]Suggested mount notation:[/bold] [cyan]{suggested}[/cyan]\n\n"
          ...,
          title="Database Not Found",
          border_style="yellow",
      )
  )
  ```

- **`rich_argparse.RichHelpFormatter`** — as covered in §2.2, this plugs
  straight into argparse's existing `formatter_class=` extension point, so
  `--help` output for every command gets the same colored, nicely-wrapped
  treatment with zero extra code per command — you only had to subclass it
  once (`RichRawHelpFormatter`) to add the "keep my manual line breaks"
  behavior for the top-level parser's description.

The underlying theme: `rich` is used *consistently* as the one "pretty
output" library across the whole CLI, while `--json` mode routes around it
entirely via the Pydantic schemas in §2.4. Two parallel, deliberately
separate output paths, chosen at the very top of each command function by
one boolean (`use_json`).

---

## 2.8 Try It Yourself

Work through these in order. You don't need real music files for most of
them — an empty or near-empty folder is enough to see the flow, even if the
command ultimately reports "no files found."

1. **Run the real help text.**
   ```bash
   ddm --help
   ddm generate --help
   ddm peaks --help
   ddm peaks generate --help
   ```
   For each, find the exact `add_argument(...)` call in
   `cli/__init__.py` that produced each line you see, and note which
   `add_argument_group(...)` ("Required" / "Options" / "Global Options") it
   came from.

2. **Trace the dispatch by adding a print statement.** Open
   `src/dap_db_manager/cli/__init__.py`, and right before
   `args.func(args)` inside `main()`, temporarily add:
   ```python
   print(f"DEBUG: about to call {args.func.__name__} for command={args.command}")
   ```
   Run `ddm load --db-dir /tmp/doesnotexist` and watch the line appear before
   the real error message. Remove it afterward — but you've now *seen*, not
   just read about, the `set_defaults(func=...)` → `args.func(args)` wiring
   actually firing.

3. **Trigger a validation error on purpose.** Open a Python REPL (as covered
   in Chapter 0) and try:
   ```python
   from dap_db_manager.cli.schemas import ValidationSuccessResponse
   ValidationSuccessResponse(status="valid", db_path="/tmp/db", entries=-1)
   ```
   Read the `pydantic.ValidationError` Python raises. Which `Field(...)`
   constraint did you just violate? Now fix `entries` to `0` and confirm it
   succeeds, then call `.model_dump_json(indent=2)` on the resulting object
   and look at the output.

4. **Run `generate` against an empty folder and compare both output modes.**
   ```bash
   mkdir -p /tmp/empty-music /tmp/out-db
   ddm generate --music-dir /tmp/empty-music --output /tmp/out-db
   ddm generate --music-dir /tmp/empty-music --output /tmp/out-db --json
   ```
   Find the exact `if total_files == 0:` block in `generate.py` responsible
   for the error you see, and note how the *same* underlying condition
   produces either a `logging.error(...)` + plain exit, or a structured
   `ErrorResponse` JSON object, depending on `--json`.

5. **Design (don't necessarily fully implement) a new `--dry-run` flag for
   `generate`.** Sketch out, in a scratch file or comment, every place in the
   codebase that flag would need to be threaded through to actually work:
   - Where in `cli/__init__.py` would you add
     `generate_options.add_argument("--dry-run", action="store_true", ...)`?
   - In `cmd_generate`, where would you read `getattr(args, "dry_run", False)`,
     and which steps (scanning? writing to disk? peaks generation?) should be
     *skipped* when it's `True`, versus which ones (like scanning, to still
     report what *would* happen) should still run?
   - Would you need a new field on `GenerateSuccessResponse` in `schemas.py`
     to report `"dry_run": true` in JSON mode? What type would it be, and
     what would its default need to be so existing JSON consumers aren't
     broken by a new required field?
   - If you're feeling ambitious, actually implement it: add the flag, skip
     the `db.write(...)` call under `--dry-run`, and print a rich-formatted
     message like `"[yellow]Dry run — no files written[/yellow]"` instead.

6. **Follow one callback all the way through.** Put a `print(message)`
   inside `ProgressCallback.__call__` in `cli/callbacks.py` (right at the top
   of the method), run `ddm generate --music-dir /tmp/empty-music --output /tmp/out-db --no-parallel`,
   and watch what actually gets passed in — paths as strings, counts as
   ints — confirming for yourself exactly how the engine and the CLI
   communicate without either one needing to know about the other's
   internals.

---

**Previous:** [01-project-overview.md](01-project-overview.md)
**Next:** [03-database-engine.md](03-database-engine.md)
