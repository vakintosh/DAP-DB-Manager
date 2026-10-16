# Chapter 8 — Testing and Tooling: How the Project Protects Itself

> **Who this is for:** you've finished Chapter 0 (Python basics) and Chapter 1
> (project architecture). This chapter does not re-teach variables, functions,
> classes, or decorators — it teaches a new vocabulary layered on top of them:
> *fixtures*, *mocks*, *parametrization*, *coverage*, *linting*, *static type
> checking*, and *pre-commit hooks*. Every concept is explained the first time
> it appears, using real code from this project's `tests/` folder and config
> files.
>
> **How to use it:** keep a terminal open in the project root
> (`DAP-DB-Manager/`). Every command shown here is something you can actually
> run. Testing is a *practice*, not a reading exercise — type the commands.

---

## 8.1 Why does this project have tests at all?

Chapter 1 pointed out one of this project's core selling points, quoted
directly from `README.md`:

> - **Non-destructive rebuilds**: A full `generate` preserves the device's
>   play counts, ratings and resume positions.

Think about what that promise actually requires. Every time someone runs
`ddm generate` on their real iPod's real music library, the tool reads an
existing database, rebuilds it from scratch, and then has to correctly carry
forward play counts, ratings, and resume positions by matching old entries to
new ones by path. If that matching logic has a bug, the user doesn't get an
error message — they get **silently incorrect data**: a song that shows 0
plays after years of listening, or a resume position that's suddenly wrong.
There's no "undo" for a corrupted database that's already been copied onto a
device and had new plays recorded against it.

This is exactly the situation automated tests exist for. A human can
carefully check "does this rebuild preserve stats?" once, by hand, after
writing the preservation code. But that same human (or a different
contributor, months later) is going to touch that code again — to fix a bug,
add a feature, or refactor for clarity — and at that point, *re-checking by
hand every single time* doesn't scale and doesn't happen. Automated tests are
how a codebase remembers "this behavior must never break" and checks it in
seconds, every time, without anyone having to remember to check manually.

Two concrete benefits fall out of this:

1. **Catching regressions.** A "regression" is old, working behavior that
   breaks because of a *new* change. If `tests/test_integration.py` has a
   test that generates a database and asserts stats were preserved, and a
   future change to the rename-detection code accidentally breaks that, the
   test fails the moment it's run — not months later when a user reports
   lost play counts.
2. **Enabling confident refactoring.** "Refactoring" means restructuring code
   without changing its behavior (Chapter 1 and later chapters will show you
   plenty of refactor-friendly structure, like the tagging system's mapping
   tables). Refactoring is terrifying without tests, because you have no way
   to know if your restructuring accidentally changed behavior. With a good
   test suite, you refactor, run `pytest`, and get an immediate yes/no answer.

For a tool whose entire purpose is to touch people's real, irreplaceable
listening history, this isn't optional polish — it's the thing that makes
"non-destructive" a testable claim instead of a hope.

---

## 8.2 `conftest.py`: shared setup for every test

Open `tests/conftest.py`. Pytest treats this filename specially: without
anyone importing it, pytest automatically loads `conftest.py` and makes
everything defined in it available to every test file in the same directory
(and subdirectories). It's the place for code that many different test files
need.

### What is a fixture?

A **fixture** is a function that provides setup (and optionally teardown)
code that test functions can reuse, instead of every test re-writing the same
"create a temp folder" or "build a sample object" boilerplate. You mark a
function as a fixture with the `@pytest.fixture` decorator (decorators were
covered in Chapter 0), and then any test function that wants it just adds the
fixture's name as a parameter — pytest sees the name, finds the matching
fixture function, runs it, and hands the result to your test.

Here's a real, simple fixture from `conftest.py`:

```python
@pytest.fixture
def temp_music_dir(tmp_path):
    """Create a temporary directory with sample music files."""
    music_dir = tmp_path / "music"
    music_dir.mkdir()

    # Create subdirectories
    (music_dir / "Artist1" / "Album1").mkdir(parents=True)
    (music_dir / "Artist2" / "Album2").mkdir(parents=True)

    return music_dir
```

Two things to notice:

- `tmp_path` is itself a fixture — it's **built into pytest** and gives you a
  fresh, empty temporary directory (as a `pathlib.Path`, from Chapter 0) that
  pytest automatically deletes after the test session. `temp_music_dir`
  **depends on** `tmp_path` simply by listing it as a parameter; pytest
  resolves that dependency chain for you.
- Any test that writes `def test_something(self, temp_music_dir):` gets a
  ready-made directory tree with two artist/album folders, without
  re-writing the `mkdir(parents=True)` calls itself.

Here's a second fixture, even simpler, that builds a ready-to-use object
instead of a folder:

```python
@pytest.fixture
def sample_tagfile():
    """Create a sample TagFile for testing."""

    tagfile = TagFile()
    tagfile.append(TagEntry("Artist 1"))
    tagfile.append(TagEntry("Artist 2"))
    tagfile.append(TagEntry("Artist 3"))

    return tagfile
```

Any test that needs "a `TagFile` with some entries already in it" just asks
for `sample_tagfile` as a parameter instead of constructing one inline.

### The `yield`-based fixture pattern: setup *and* teardown

So far both fixtures just `return` a value — that's "setup only." But some
fixtures need to run cleanup code *after* the test finishes, whether the test
passed or failed. For that, a fixture uses `yield` instead of `return`.
Recall from Chapter 0 that `yield` pauses a function and hands a value back
to the caller, resumable later. In a fixture, pytest resumes the fixture
function (running whatever comes *after* the `yield`) once the test using it
has finished. Code before `yield` is setup; code after `yield` is teardown.

This project's most important fixture uses exactly this pattern, and the
docstring explains *why* it exists — read it carefully, because it's a great
real-world lesson in why test isolation matters:

```python
@pytest.fixture(autouse=True)
def _no_global_state_leaks():
    """Stop any test from leaking global interpreter state into the next one.
    ...
    """
    cache_limit = TagCache.get_max_cache_memory()

    yield

    if tracemalloc.is_tracing():
        tracemalloc.stop()

    if TagCache.get_max_cache_memory() != cache_limit:
        TagCache.set_max_cache_memory(cache_limit)
```

Walking through it:

- **Before `yield`:** it records the current `TagCache` memory limit into
  `cache_limit`. This is the "setup" — snapshotting the state *before* the
  test runs, so it has something to restore afterward.
- **`yield`** (with nothing after the keyword, meaning it hands back `None`):
  this is where the actual test body runs. Pytest pauses this fixture right
  here, runs the test function that asked for it, and only resumes the
  fixture once that test is completely finished — pass, fail, or error.
- **After `yield`:** this is the teardown. It checks `tracemalloc.is_tracing()`
  (a built-in Python module for memory profiling) and force-stops it if some
  earlier test left it running. Then it checks whether `TagCache`'s memory
  limit drifted from what it was before the test, and restores it if so.

The docstring explains the real bug this prevents: a test that starts
`tracemalloc` to measure memory, then exits early (via a failed assertion or
an exception) *before* calling `tracemalloc.stop()`, leaves memory tracing
switched on process-wide. Every subsequent test in the same run then
pays roughly a 2x speed tax from that tracing — which previously showed up
as two *unrelated* performance tests reporting mysterious "slowdowns" that
had nothing to do with the code being measured and everything to do with
test pollution. This fixture is a safety net, not a guarantee — the docstring
is explicit that "individual tests should still clean up after themselves,"
but this net catches what they miss.

### `autouse=True`: a fixture nobody has to ask for

Notice the decorator on that fixture: `@pytest.fixture(autouse=True)`. A
normal fixture only runs for a test that explicitly lists it as a parameter.
`autouse=True` means pytest runs this fixture **automatically for every
single test** in this file's scope, with no test needing to mention it by
name. That's the right choice here, because *every* test should have its
tracing/cache state restored — making every test author remember to opt in
would defeat the purpose.

### Fixture scope

None of the fixtures above specify a `scope=` argument, which means they
default to **function scope** — pytest tears down and re-creates the fixture
fresh for *every single test function* that uses it. That's the safest
default: tests don't accidentally share mutable state through a fixture.
Pytest also supports `scope="session"` (run once for the entire test run) and
others, for expensive setup that's safe to share — this project doesn't use
that here, keeping each test's `temp_music_dir`/`sample_tagfile` fully
isolated from every other test.

### A fixture-adjacent helper: `music_test_folder()`

The bottom of `conftest.py` defines a plain function (not a fixture — it's
called directly, not requested as a test parameter):

```python
def music_test_folder() -> Path:
    """Locate the shared music fixture directory.
    ...
    """
    env = os.environ.get("DDM_TEST_DATA")
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent / "test-fixtures" / "music_test_folder"
```

Its docstring tells an honest story worth remembering as a lesson: the suite
used to hardcode an absolute path into a sibling checkout on one specific
machine, so integration tests silently worked for one developer and silently
*skipped* for everyone else. The fix: check an environment variable override
first (`DDM_TEST_DATA`, useful for CI), then fall back to a predictable path
relative to the repo. Tests that use this (you'll see it in
`test_integration.py` and `test_tag_core.py`) guard with
`@pytest.mark.skipif(not TEST_DATA_DIR.exists(), ...)` so a checkout without
real sample audio files still runs everything else instead of crashing.

---

## 8.3 Reading one real test, line by line

Here is a complete, real test from `tests/test_cache.py`:

```python
class TestSimpleTag:
    """Test SimpleTag class."""

    def test_simple_tag_get_string(self):
        """Test get_string method for titleformat compatibility."""
        tag_dict = {"artist": ["Artist Name"], "album": ["Album Name"]}
        tag = SimpleTag(tag_dict)

        assert tag.get_string("artist") == ["Artist Name"]
        assert tag.get_string("album") == ["Album Name"]

        # get_string raises KeyError for missing keys (matches mutagen behavior)
        with pytest.raises(KeyError):
            tag.get_string("nonexistent")
```

Annotated:

- `class TestSimpleTag:` — pytest's default discovery rules (configured in
  `pytest.ini`, covered in §8.6) treat any class named `TestSomething`
  containing methods named `test_something` as a group of tests. The class
  itself is just an organizational folder; it's not required for pytest to
  find tests, but it groups related tests together and gives the test runner
  readable, nested output.
- `def test_simple_tag_get_string(self):` — a plain method. Pytest calls
  this with no arguments other than `self` (or, as you'll see elsewhere,
  with fixture names as extra parameters, which pytest fills in
  automatically — same mechanism as §8.2).
- `tag_dict = {...}` and `tag = SimpleTag(tag_dict)` — this is the
  **Arrange** step of the classic **Arrange-Act-Assert** pattern that nearly
  every test follows: first you set up the exact situation you want to test
  (here, a `SimpleTag` built from a small, known dictionary).
- `assert tag.get_string("artist") == ["Artist Name"]` — this line is both
  **Act** (calling `get_string("artist")`, the method actually being tested)
  and **Assert** (checking the result with Python's built-in `assert`
  statement from Chapter 0: if the expression after `assert` is falsy,
  Python raises an `AssertionError` and the test fails immediately; if it's
  truthy, execution just continues to the next line). A test typically has
  one Act per behavior, but can have several Asserts checking different
  aspects of the result — here, both `"artist"` and `"album"` are checked.
- `with pytest.raises(KeyError):` — this is a different kind of assertion:
  instead of checking a *return value*, it checks that calling code *raises
  a specific exception*. `pytest.raises(KeyError)` is a context manager
  (Chapter 0 covered `with` blocks) that pytest provides: the code inside the
  `with` block is expected to raise a `KeyError` before the block ends. If it
  does, the test passes this check. If it *doesn't* raise `KeyError` (either
  it raises nothing, or it raises some other exception), the test fails —
  `pytest.raises` turns "this should blow up in exactly this way" into a
  normal, readable assertion instead of an awkward manual
  `try`/`except`/`else` dance.
- The comment above it — `# get_string raises KeyError for missing keys
  (matches mutagen behavior)` — is a good habit worth copying: when a test
  asserts something that looks surprising (why would a *missing* key be
  correct behavior?), a one-line comment explaining the intent saves the
  next reader from wondering if it's a bug in the test itself. `mutagen` is
  the real third-party audio-tag library this project wraps, and `SimpleTag`
  is deliberately designed to mimic its exact error behavior so code written
  against real mutagen tags doesn't need special-casing for test doubles.

### Parametrization: one test function, many cases

The test above checks one specific input. But often you want to check the
*same* logic against many different inputs without copy-pasting the test
body ten times. That's what `@pytest.mark.parametrize` is for. Here's a real
example from `tests/test_cross_compilation.py`:

```python
class TestNormalizeDapRoot:
    """Test DAP root path normalization."""

    @pytest.mark.parametrize(
        "input_path,expected",
        [
            ("/Volumes/DAP", "/Volumes/DAP"),
            ("/Volumes/DAP/", "/Volumes/DAP"),
            ("E:", "E:"),
            ("E:\\", "E:"),
            ("/mnt/dap", "/mnt/dap"),
            ("/mnt/dap/", "/mnt/dap"),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize_dap_root(self, input_path, expected):
        """Test that DAP root paths are normalized correctly."""
        result = DatabaseGenerator._normalize_dap_root(input_path)
        assert result == expected, (
            f"normalize_dap_root({input_path!r}) = {result!r}, expected {expected!r}"
        )
```

How to read this: the first argument to `parametrize` is a string naming the
parameters as they'll appear in the test function's signature —
`"input_path,expected"`. The second argument is a list of tuples, one tuple
per test case, where each tuple supplies one value for each named parameter
in order. Pytest expands this into **eight separate test runs** — one for
each tuple — each reported individually (so a failure tells you exactly
*which* input broke, e.g. `test_normalize_dap_root[E:\\\\-E:]`, not just that
"the test" failed). The test function itself is written once, taking
`input_path` and `expected` as ordinary parameters, exactly like a fixture
parameter — pytest fills them in from whichever tuple is currently running.
This is far more maintainable than writing eight nearly-identical test
methods, and it makes edge cases (empty string, `None`, trailing slash,
Windows drive letter with and without backslash) explicit and easy to add to.

The `assert result == expected, (f"...")` line shows one more detail:
`assert` optionally takes a second value after a comma, which is the message
shown *only if the assertion fails* — useful for making a failure's cause
obvious without having to re-run the test with extra print statements.

---

## 8.4 Why so many `test_X.py` *and* `test_X_comprehensive.py` files?

Looking at `tests/`, you'll see pairs like:

- `test_cli_commands.py` and `test_cli_commands_comprehensive.py`
- `test_tag_core.py` and `test_tag_core_comprehensive.py`
- `test_file_scanner.py` and `test_file_scanner_comprehensive.py`
- `test_mount_detector.py` and `test_mount_detector_comprehensive.py`

The apparent convention: the plain file (`test_tag_core.py`) holds the
original, focused tests for a module's core behavior — the first tests
written when that module existed, usually covering the "happy path" and the
most obvious edge cases. The `_comprehensive.py` file is a *later* addition
that fills in the gaps: more exhaustive edge cases, more error conditions,
and often entirely different setup machinery. You can see this difference
directly in the imports — `test_cli_commands.py` patches at the boundary
(`@patch("dap_db_manager.cli.commands.generate.Database")`), while
`test_cli_commands_comprehensive.py` imports the actual command functions
(`cmd_validate`, `cmd_write`) and builds its own `mock_args` fixture from
scratch:

```python
@pytest.fixture
def mock_args():
    args = MagicMock(spec=argparse.Namespace)
    args.quiet = False
    args.json = False
    ...
```

Rather than two different test *philosophies* in conflict, this looks like
incremental coverage improvement: when someone later audited a module and
found undertested behavior, it was faster and lower-risk to add a
`_comprehensive.py` companion file than to go back and restructure the
original tests. `TEST_COVERAGE_PROGRESS.md` in the `tests/` folder (worth a
skim) documents exactly this kind of ongoing coverage effort. The practical
takeaway for you as a reader: if you're looking for tests of a module and the
plain file seems thin, **check for a `_comprehensive.py` sibling** before
assuming something is untested.

### Mocking: testing without the real thing

Notice `from unittest.mock import Mock` at the top of `test_tag_core.py` and
`test_cache.py`, and `MagicMock`/`@patch` in the CLI tests. **Mocking** means
substituting a fake, controllable stand-in object for a real dependency, so a
test can check *how your code uses* that dependency without needing the real
thing to exist (a real audio file, a real filesystem write, a real database).
For example:

```python
def test_tag_creation_with_mock(self):
    """Test creating a Tag with a mock mutagen object."""
    mock_tags = Mock()
    mock_tags.__class__.__name__ = "MP3"

    tag = Tag(mock_tags)
    assert tag is not None
    assert tag.tags == mock_tags
```

`Mock()` creates an object that will accept *any* attribute access or method
call you throw at it, recording what happened, without you having to define
a real `MP3` tag object from mutagen. Setting `mock_tags.__class__.__name__ =
"MP3"` tricks `Tag`'s format-detection logic into thinking it received a real
MP3 tag object, without needing an actual MP3 file on disk. This makes tests
fast (no disk I/O), deterministic (no dependency on a specific real file
existing), and focused (you're testing *this* class's logic, not mutagen's).
The CLI tests go one step further with `@patch(...)`, which temporarily
replaces a real class (`Database`) with a mock *for the duration of one
test*, so a "generate" command can be tested without actually writing
database files to disk.

---

## 8.5 `test_benchmarks.py`: performance as a tested property

Chapter 1 and the README both make speed claims central to this project's
value proposition — recall from the README:

> **Fast database generation**: Multiprocessing bypasses Python GIL (4-15x
> faster).
> **Cross-compilation**: Build database on laptop/server for your DAP (180x
> faster).

A correctness test can tell you *that* code still works. It cannot tell you
*whether a change accidentally made it twice as slow* — correctness and speed
are different properties, and a project whose whole pitch is "faster" needs a
way to test the second one too. That's what `test_benchmarks.py` is for,
using the `pytest-benchmark` plugin (listed in `pyproject.toml`'s dev
dependencies). The module docstring explains how to run it:

```python
"""Benchmark tests for performance monitoring.

These tests use pytest-benchmark to measure performance of key operations.
Run with: pytest tests/test_benchmarks.py --benchmark-only

To save results: pytest tests/test_benchmarks.py --benchmark-only --benchmark-save=baseline
To compare: pytest tests/test_benchmarks.py --benchmark-only --benchmark-compare=0001
"""
```

And one real benchmark test:

```python
@pytest.mark.perf
class TestUtilsBenchmarks:
    """Benchmark utility functions."""

    def test_mtime_to_fat_benchmark(self, benchmark):
        """Benchmark mtime to FAT conversion."""
        import time

        timestamp = time.time()
        result = benchmark(mtime_to_fat, timestamp)
        assert isinstance(result, int)
```

`benchmark` here is itself a fixture, provided by the `pytest-benchmark`
plugin (same mechanism as `tmp_path` in §8.2 — a plugin can register its own
fixtures, not just ones defined in `conftest.py`). Instead of calling
`mtime_to_fat(timestamp)` directly, the test hands the function and its
argument *to* `benchmark`, which calls it many times, measures how long each
call takes, and returns the actual result so the test can still assert on
correctness (`isinstance(result, int)`) in the same breath. Saving a
`--benchmark-save=baseline` snapshot and later comparing against it with
`--benchmark-compare` is how a "did this change make generation slower?"
question gets a concrete, numeric answer instead of a vague impression.

Notice `@pytest.mark.perf` on the class — a **marker**, which labels tests so
they can be selectively included or excluded later (you'll see this again in
`pytest.ini` in §8.6). Timing-based tests are inherently sensitive to how
busy the machine running them is, so this project excludes them from the
default/CI run and only runs them deliberately.

---

## 8.6 `pytest.ini`: configuring how `pytest` behaves

`pytest.ini` at the project root configures default behavior so nobody has to
remember a long command line every time. The real file:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=dap_db_manager
    --cov-report=term-missing
    --cov-report=html
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    perf: timing-sensitive; results depend on host speed and load. Excluded in CI (deselect with '-m "not perf"')
```

Line by line:

- `testpaths = tests` — when you run bare `pytest` with no arguments, only
  look inside the `tests/` directory for test files, instead of scanning the
  whole project.
- `python_files = test_*.py` / `python_classes = Test*` / `python_functions =
  test_*` — these three lines are exactly the discovery rules referenced in
  §8.3: any file named `test_*.py`, any class inside it named `Test*`, and
  any function inside those named `test_*` is automatically treated as a
  test, with zero registration needed.
- `-v` — "verbose": print each test's name and pass/fail individually,
  instead of just dots.
- `--strict-markers` — any `@pytest.mark.something` that isn't declared in
  the `markers =` list below causes an *error* rather than a silent typo.
  This is why `perf`, `slow`, and `integration` must be explicitly listed:
  it stops a misspelled marker (`@pytest.mark.intergration`) from silently
  doing nothing.
- `--tb=short` — when a test fails, print a shorter traceback (the chain of
  function calls leading to the error) instead of the full, often very long,
  default one.
- `--cov=dap_db_manager` — enables **code coverage** measurement (via the
  `pytest-cov` plugin) for the `dap_db_manager` package specifically. Code
  coverage means: as the test suite runs, a tool watches *which lines of
  source code actually executed* at least once. A line that never ran during
  any test is a line with zero test evidence behind it — it could be
  completely broken and no test would notice.
- `--cov-report=term-missing` — print a coverage summary table in the
  terminal, and specifically list the line numbers that were *not* covered,
  so you know exactly where to look.
- `--cov-report=html` — additionally write a browsable HTML report (usually
  to an `htmlcov/` folder) where you can click into any source file and see
  covered lines highlighted green and uncovered lines highlighted red.
- `markers = ...` — declares the three custom markers this project uses, with
  a one-line explanation of each, satisfying `--strict-markers` above. The
  `perf` marker's own description doubles as useful documentation: "excluded
  in CI (deselect with `-m "not perf"`)" tells you both *that* benchmarks are
  skipped automatically in continuous integration and *how* to reproduce
  that filtering yourself.

**Important nuance about coverage:** 100% coverage does not mean "100%
correct" — it only means every line *ran*, not that every line was checked
against the *right* result with a meaningful assertion. Coverage tells you
where you have *no* evidence at all; it can't tell you your assertions were
weak. Treat it as a map of blind spots, not a certificate of correctness.

---

## 8.7 `mypy.ini`: catching type mistakes before running anything

Chapter 0 introduced **type hints** — annotations like `def foo(x: int) ->
str:` — and was careful to say Python *does not enforce them at runtime*. You
can write `def foo(x: int): return x` and then happily call `foo("hello")`;
Python will not stop you, because type hints are just documentation as far as
the running interpreter is concerned.

A **static type checker** is a separate tool that reads your source code
*without running it* and checks whether the type hints are internally
consistent — "this function says it returns `str`, but this branch returns
`None`," or "you're passing an `int` where a function's hint says it expects
a `Path`." This project uses two: `mypy` (configured below) and
`basedpyright` (listed alongside it in the dev dependencies) — running both
gives two independently-implemented checkers a chance to catch different
classes of mistakes.

Why bother, if Python doesn't enforce types anyway? Because the *checker*
enforces them, and it does so **before a single test runs, before a user
ever executes the code** — the fastest and cheapest point in the whole
process to catch a mismatch. In a project like this one, where a function
might genuinely return `None` on a missing tag field versus a real value on
a hit (you'll see this pattern throughout the tagging system in Chapter 4),
a type checker can catch "you forgot to handle the `None` case over here" at
edit time, long before that code path runs against a real music file and
produces a confusing crash or, worse, silently wrong output.

The real `mypy.ini`:

```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
disallow_incomplete_defs = False
check_untyped_defs = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True
show_error_codes = True
exclude = Legacy_Codebase/

# Ignore missing imports for third-party libraries
[mypy-mutagen.*]
ignore_missing_imports = True

[mypy-wx.*]
ignore_missing_imports = True
```

Key settings, in plain English:

- `python_version = 3.11` — check against the rules and standard library
  shape of Python 3.11 specifically, matching the `requires-python = ">=3.11"`
  constraint in `pyproject.toml`.
- `disallow_untyped_defs = False` and `disallow_incomplete_defs = False` —
  this project does **not** require every single function to have complete
  type hints (a stricter project could flip these to `True` to force full
  annotation coverage). This is a pragmatic middle ground, common in codebases
  that adopted type hints after the fact rather than from day one.
- `check_untyped_defs = True` — but even for functions *without* hints, mypy
  still checks the code *inside* them for internal inconsistencies, rather
  than skipping them entirely.
- `no_implicit_optional = True` — a function hinted `def f(x: int = None)` is
  rejected unless you spell out `x: int | None = None` (or `Optional[int]`),
  forcing `None`-acceptance to be explicit rather than accidental.
- `warn_redundant_casts = True` / `warn_unused_ignores = True` — flag
  "defensive" code that no longer does anything useful: a type cast that
  wasn't needed, or a `# type: ignore` comment suppressing an error that
  doesn't actually occur anymore (so cleanup doesn't silently rot).
- `warn_unreachable = True` — flag code mypy can prove will never execute,
  often a sign of a logic bug (e.g., an `if`/`elif` chain that's missing a
  case, or a condition that can never be true given earlier type narrowing).
- `strict_equality = True` — flag comparisons between types that can never be
  equal (e.g., comparing a `str` to an `int` with `==`), which are usually
  typos rather than intentional.
- `exclude = Legacy_Codebase/` — the older, unconverted Python 2-era code
  mentioned in the README is deliberately excluded from checking; it's kept
  for reference, not actively maintained to modern standards.
- `[mypy-mutagen.*]` / `[mypy-wx.*]` with `ignore_missing_imports = True` —
  third-party libraries (`mutagen` for audio tags, `wx` for the GUI) may not
  ship their own type hints (called "type stubs"), so mypy is told not to
  complain about not finding them — otherwise every single import of these
  libraries would generate a spurious warning unrelated to this project's
  own code quality.

### What a linter adds on top of a type checker

A **linter** is a different kind of static tool: instead of checking type
consistency, it checks style and common-mistake patterns — unused imports,
unreachable code via obviously-dead branches, inconsistent formatting,
overly complex expressions, and dozens of other heuristics accumulated from
real-world bugs. This project uses `ruff`, listed in `pyproject.toml`'s dev
dependencies (`"ruff>=0.14.10"`) and run via pre-commit (next section) with
no project-specific configuration file, meaning it currently runs with
ruff's sensible defaults. A linter and a type checker are complementary, not
redundant: mypy proves your *types* line up; ruff catches a different
category of problems entirely, like `import os` that's never used, or
formatting inconsistencies that make diffs noisier than necessary.

---

## 8.8 `.pre-commit-config.yaml`: automation before every commit

A **pre-commit hook** is a script that runs automatically at a Git
lifecycle point (like right before `git commit` succeeds), so that checks
happen *before* broken or unformatted code ever enters the repository's
history — rather than relying on every contributor remembering to run
`ruff` and `mypy` manually every single time. The `pre-commit` tool (a
separate Python package, not built into Git) reads `.pre-commit-config.yaml`
and manages running these hooks for you once you've installed it in a repo
(§8.9 shows the exact command).

The real file:

```yaml
fail_fast: true

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.10
    hooks:
      - id: ruff
        args: [--fix]
        files: ^(src|tests|profiling)/
      - id: ruff-format
        files: ^(src|tests|profiling)/

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: local
    hooks:
      - id: pytest
        name: Run pytest
        entry: uv run pytest -x --ignore=tests/test_performance_regression.py
        language: system
        types: [python]
        stages: [pre-push]
        pass_filenames: false
```

Reading it section by section:

- `fail_fast: true` — stop running the remaining hooks as soon as one fails,
  instead of running every hook regardless and dumping all failures at once.
  Faster feedback for the common case of one broken hook.
- The `ruff-pre-commit` block runs two hooks limited to `files: ^(src|tests|
  profiling)/` (only inside those three folders, via a regular expression —
  not the whole repo, which would also lint things like build scripts):
  - `ruff` with `args: [--fix]` — run the linter described in §8.7, and
    automatically fix whatever issues it safely can (like reordering
    imports), rather than only reporting them.
  - `ruff-format` — a separate hook that auto-formats code style (spacing,
    quote style, line length) to a consistent standard, similar in spirit to
    tools like Python's `black`.
- The `pre-commit-hooks` block runs small, generic hygiene checks that have
  nothing to do with Python specifically: `trailing-whitespace` strips
  stray whitespace at line ends, `end-of-file-fixer` ensures files end with
  exactly one newline, `check-yaml` verifies any YAML file in the commit
  actually parses, and `check-added-large-files` blocks accidentally
  committing something huge (like a binary test fixture) straight into Git
  history.
- The `local` block defines a hook sourced from *this* repository rather
  than a downloaded tool: `id: pytest` runs `uv run pytest -x
  --ignore=tests/test_performance_regression.py`. Notice `stages: [pre-push]`
  — unlike the ruff/formatting hooks (which default to running on every
  `commit`), this one is configured to run only when you `git push`, not on
  every single commit. That's a deliberate trade-off: the full test suite is
  slower than a linter, so it's checked at the point you're about to share
  your changes rather than on every small, local, in-progress commit. `-x`
  stops at the first failing test rather than running the whole suite
  (fast failure, same idea as `fail_fast` above), and
  `--ignore=tests/test_performance_regression.py` skips the known
  machine-sensitive timing test described in §8.5, since different machines'
  speeds would make it flaky as an automatic gate.

---

## 8.9 The commands you'll actually run

Here's the practical command reference, tying every tool above to something
you type:

```bash
# Run the whole test suite with default settings from pytest.ini
pytest

# Run it with extra detail per test (pytest.ini already adds -v,
# but it's worth knowing the flag)
pytest -v

# Run a single test file
pytest tests/test_cache.py

# Run a single test function inside a file
pytest tests/test_cache.py::TestSimpleTag::test_simple_tag_get_string

# Run tests and show the coverage report (pytest.ini already enables this
# by default, but --cov is worth knowing explicitly)
pytest --cov

# Run only the performance benchmarks (excluded from the default run)
pytest tests/test_benchmarks.py --benchmark-only

# Run everything EXCEPT the slow/perf-marked tests, using the markers
# declared in pytest.ini
pytest -m "not perf"

# Lint the codebase with ruff (reports problems; add --fix to auto-fix)
ruff check .

# Type-check the source tree with mypy
mypy src

# Install the pre-commit hooks so they run automatically on future
# commits/pushes in this checkout (one-time setup per clone)
pre-commit install
```

A quick note on `uv`, which you'll see referenced inside
`.pre-commit-config.yaml`'s `entry: uv run pytest ...`: it's this project's
package/environment manager (set up in Chapter 1's tour of
`pyproject.toml`). If the plain commands above (`pytest`, `ruff`, `mypy`)
aren't found on your system path, prefix them with `uv run` — e.g. `uv run
pytest` — so they execute inside the project's managed virtual environment
rather than whatever Python happens to be installed globally.

---

## 8.10 Try It Yourself

1. **Run the whole suite and read the summary line.** From the project
   root, run `pytest`. Scroll to the very last few lines of output — pytest
   prints a one-line summary like `== 500 passed, 3 skipped in 12.34s ==`.
   Find the skipped tests mentioned in the output and figure out *why* they
   were skipped (hint: recall `music_test_folder()` from §8.2 — look for a
   printed skip reason near each skipped test's name).

2. **Break something on purpose, then fix it.** Open
   `src/dap_db_manager/tagging/tag/tagfile.py` (or any small, simple
   function you're comfortable reading) and temporarily change one line of
   real logic — for example, flip a `==` to `!=`, or change a return value.
   Run `pytest tests/test_tagfile.py -v` and watch at least one test turn
   red, read the failure's traceback and assertion message, and connect it
   back to the line you changed. Then revert your change and re-run to
   confirm it's green again. This is the single fastest way to build
   intuition for how test failures map back to real bugs.

3. **Run `ruff check .` and fix one real warning.** Read whatever ruff
   reports (if the codebase is already clean, temporarily add an unused
   `import sys` somewhere to manufacture a warning, see ruff catch it, then
   remove it). Try `ruff check . --fix` separately and see which warnings it
   can repair automatically versus which ones need a human decision.

4. **Add a tiny new test for an existing simple function.** Pick a small,
   pure utility — `mtime_to_fat` or `fat_to_mtime` from
   `dap_db_manager.utils` (the same ones benchmarked in §8.5) are good
   choices because they take one value in and return one value out, no
   mocking required. Add a new test function to `tests/test_utils.py`
   following the Arrange-Act-Assert pattern from §8.3: pick a known input,
   call the function, and `assert` the result matches what you expect. Run
   just that file (`pytest tests/test_utils.py -v`) to confirm it passes.

5. **Try `pytest --cov` and open the HTML report.** After running it once,
   look for an `htmlcov/index.html` file and open it in a browser. Click
   into a file you've read in an earlier chapter and look for any red
   (uncovered) lines — are they edge cases nobody got around to testing yet,
   or dead code that should be removed?

6. **Install the pre-commit hooks and make a trivial commit.** Run
   `pre-commit install`, then make a tiny, harmless change (like adding a
   blank line somewhere ruff would normalize), stage it, and run `git
   commit`. Watch the hooks run automatically and either pass or
   auto-fix your change before the commit completes.

---

## Where to go from here

This chapter closes the guided tour: Chapter 0 gave you the Python
vocabulary, Chapters 1–7 walked the project's architecture layer by layer —
CLI, database engine, tagging system, titleformat DSL, and the GUI — and
this chapter showed you how the project protects all of that work against
regressions as it keeps changing.

A few concrete next steps, in increasing order of commitment:

- **Re-read the chapters you skimmed.** Architecture only really sinks in on
  a second pass, once you've seen how the pieces get exercised by tests. If
  Chapter 3 (the database engine) or Chapter 4 (the tagging system) felt
  abstract the first time, revisit them now with `tests/test_database.py`,
  `tests/test_cache.py`, and `tests/test_tag_core.py` open side by side.
- **Find a small, real bug or gap and attempt it.** `TEST_COVERAGE_PROGRESS.md`
  in `tests/` is a real, living list of known gaps — a good, low-risk place
  to look for a first contribution. Alternatively, pick any `_comprehensive.py`
  file from §8.4 and look for a case it *doesn't* cover yet.
- **Run the exercises in §8.10 for real**, not just in your head. The
  difference between understanding testing as a concept and being able to
  use it under pressure (when you've actually broken something and need to
  find out why) only comes from doing it yourself.
- **Consider contributing.** Once you've broken and fixed something small
  locally, a real, scoped improvement — a new test for an undertested
  function, a small bug fix with a regression test attached, a
  documentation clarification — is exactly the kind of change that's safe to
  propose, because you'll already know how to prove, via `pytest`, `ruff`,
  and `mypy`, that it doesn't break anything else.

---

**Previous:** [Chapter 7 — The GUI Layer](07-gui-layer.md)
