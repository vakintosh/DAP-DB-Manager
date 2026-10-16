# Learn Python by Reading DAP-DB-Manager

A guided, zero-to-hero walkthrough that teaches Python **and** teaches how a
real, working, multi-thousand-line project is built — using this project
itself as the textbook.

This is not API reference documentation. It's a *course*. Read it in order,
front to back, with the actual project checked out next to you so you can
open every file we mention and poke at it.

## Who this is for

Someone who has **never written Python before** (or has seen a little but
doesn't feel solid on it) and wants to learn by reading real, working,
intentionally-written code instead of toy tutorials. No prior knowledge is
assumed except how to open a terminal.

## How to use this

1. **Don't skip Chapter 0.** Even if you've coded in another language before,
   it sets the vocabulary every later chapter relies on.
2. **Read with the project open.** Every chapter quotes real code from real
   files and tells you exactly where to find it. Open the file, scroll to the
   quoted part, and look around it.
3. **Do the "Try It Yourself" exercises** at the end of each chapter before
   moving on. Reading about code and writing/running code are different
   skills — this project is small enough that you can safely break things
   and watch the tests catch you.
4. **Run things as you go.** `uv sync`, `ddm --help`, `pytest`. A project you
   only read about never quite sinks in; a project you run and break and fix
   does.
5. **It's fine to re-read.** Chapter 3 (the database engine) and Chapter 5
   (the titleformat DSL) are the densest — most readers benefit from a
   second pass once they've seen the rest of the project and have more
   context for why those pieces matter.

## Reading Order

| # | Chapter | What you'll learn |
|---|---|---|
| 0 | [Python Primer](00-python-primer.md) | Variables, types, control flow, functions, classes, dataclasses, exceptions, decorators, context managers, generators, pathlib, basic concurrency — the vocabulary for everything after this. |
| 1 | [Project Overview](01-project-overview.md) | What this tool does and why, the overall architecture, the folder layout, how to run it and its test suite, and your first real annotated code walkthrough. |
| 2 | [The CLI Layer](02-cli-layer.md) | How `ddm`'s subcommands are built with `argparse`, how Pydantic validates input, and a full trace of the `generate` command end-to-end. |
| 3 | [The Database Engine](03-database-engine.md) | The real core of the project: the Rockbox binary tag-cache format, `struct`-based binary I/O, multiprocessing for speed, file scanning, caching, and the rename-detection / stats-preservation algorithm. |
| 4 | [The Tagging System](04-tagging-system.md) | How audio metadata (ID3, Vorbis comments, etc.) gets normalized across formats using `mutagen` and data-driven mapping tables. |
| 5 | [The Titleformat DSL](05-titleformat-dsl.md) | How a tiny custom language (`%artist% - %title%`, `$if(...)`, etc.) is tokenized, parsed into a tree, and evaluated — real parser/interpreter concepts, not toy ones. |
| 6 | [The Peaks Subsystem](06-peaks-subsystem.md) | Waveform/peak extraction from audio, hashing, and binary serialization for the device's scrubber UI. |
| 7 | [The GUI Layer](07-gui-layer.md) | Event-driven programming with wxPython, and — the real teaching value — how background threads talk safely to a GUI thread without freezing the window. |
| 8 | [Testing and Tooling](08-testing-and-tooling.md) | Why automated tests matter, how `pytest` fixtures and parametrization work, and what `ruff`, `mypy`, and `pre-commit` add on top of the language itself. |

## Project Map (for reference while you read)

```
DAP-DB-Manager/
├── src/dap_db_manager/
│   ├── cli/              → Chapter 2: command-line interface (argparse + pydantic)
│   ├── database/          → Chapter 3: binary tag-cache format, generation, caching
│   ├── tagging/
│   │   ├── tag/           → Chapter 4: reading metadata out of audio files
│   │   └── titleformat/   → Chapter 5: the %artist% - %title% mini-language
│   ├── peaks/              → Chapter 6: waveform data extraction
│   └── gui/                → Chapter 7: the wxPython desktop app
├── tests/                 → Chapter 8: the test suite
├── profiling/             → performance measurement scripts (mentioned in Ch. 3/8)
└── Legacy_Codebase/        → the original 2009 Python 2 implementation this
                              project replaces (interesting to compare against,
                              not required reading)
```

## After you finish

By the end of Chapter 8 you should be able to:

- Read and understand any file in `src/dap_db_manager/`.
- Explain, in your own words, what happens between typing `ddm generate ...`
  and a `.tcd` file appearing on disk.
- Write and run a new `pytest` test for a small function.
- Make a small, safe, test-covered change to the project and verify it with
  `pytest`, `ruff`, and `mypy`.

From there, the best next step is picking a small real improvement — a
missing edge case, a new titleformat function, a clearer error message — and
implementing it yourself, following the [`CONTRIBUTING`](../../README.md)
workflow (tests first, see Chapter 8).

---

**Start here:** [Chapter 0 — Python Primer](00-python-primer.md)
