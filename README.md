# DAP Database Manager

A Python-based utility created to solve the frustration of long wait times when generating or updating databases on vintage hardware. Designed to bypass these slow on-device indexing speeds, it allows you to generate, update, validate, and inspect Rockbox tag cache database (`tcd`) files directly on your PC up to x180 faster.

Based on the original 2009 Python 2.x GUI implementation by **Mike Richards** and the inspect database implementation by **Aren Olson** - See [Legacy Codebase](Legacy_Codebase)

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL%20v2-blue.svg)](LICENSE)

---

## Features

- **Fast database generation**: Multiprocessing bypasses Python GIL (4-15x faster).
- **Cross-compilation**: Build database on laptop/server for your DAP (180x faster).
- **Non-destructive rebuilds**: A full `generate` preserves the device's play counts, ratings and resume positions.
- **Incremental updates**: Delta updates with rename detection preserve stats.
- **Intelligent caching**: Persistent tag cache for speed.
- **Full CLI suite**: Generate, validate, inspect, load, and copy databases.
- **wxPython GUI**: Visual interface with async operations.
- **Docker support**: Production-ready containerization.


> **Performance Note**: When generating or updating the database directly on the DAP (e.g., via USB), performance is limited by the device's I/O bandwidth. For example, the **iPod Classic 7th Gen (2009)** is constrained by its PATA/IDE bus and USB 2.0 interface, capping sustained rates at ~23-25 MB/s write and ~14-21 MB/s read. This tool bypasses these bottlenecks by building the database on your PC. **Using a local source folder (e.g., a backup of your music library on your PC's SSD) is significantly faster than reading files directly from the device over USB.**

---

## Status

**Work in Progress** - Under active development

**Tested on:**
- yes macOS Sonoma 14.8.3 (Intel Mac)
- yes maOS Tahoe 26.1 (Apple Silicon)
- yes Ubuntu 24.04 LTS (Kernel 6.17.0, aarch64 / Raspberry Pi)
- 🔄 Windows (in progress)

> **Note**: The generated database files were tested only on an **iPod Classic 7th Gen (2009)** running **Rockbox Ver. 37690baa5f-260101**.

---

## Quick Start
Using `pip` :

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
---

## Installation

### Standard (uv / pip)

```bash
# Install with uv (CLI only)
uv sync
# Install with GUI support
uv sync --extra gui

# OR with pip
pip install -e .
pip install -e ".[gui]"
```

## Usage

### CLI (`ddm`)
The `ddm` tool is the core of the project.

- `generate`: Create a new database.
- `update`: Update an existing database (fast delta updates).
- `detect-mounts`: Configure the mount point for your DAP.
- `validate`: Check database integrity.
- `inspect`: Low-level file inspection.

**Cross-Compilation**: Use `--dap-root` when running on a PC. It ensures paths in the database match what the Rockbox OS expects (e.g. `/<HDD0>/Music/...` instead of `/Path/To/Music/Folder/...`).

**Update Command**: Use `ddm update` to add new files or handle renames without rebuilding the entire database. It preserves play counts and ratings.

### Runtime statistics are preserved across rebuilds

The device accumulates play counts, ratings, play time, last-played timestamps and
resume positions as you listen. `generate` rebuilds from the music files, which carry
none of that, so by default it now reads the database it is about to replace and carries
those values onto the new entries, matched by path.

This means a full rebuild is non-destructive: you get the speed of rebuilding on a PC
without paying for it in lost listening history.

Every run reports what happened, so a partial restore can never look like a complete one:

```
Preserved stats for 17,102 of 17,139 entries (37 new files, 12 old entries unmatched)
```

- `--no-preserve-stats` rebuilds without carrying anything over.
- `--preserve-stats-from DIR` reads the statistics from a database in `DIR` instead of
  the one in `--output`. It cannot be combined with `--no-preserve-stats`.

Files that moved since the last rebuild are treated as new and start from zero. Use
`ddm update`, which has rename detection, if you need statistics to follow a moved file.

Note that `commitid` and `mtime` are deliberately not carried over. They describe the
database and the file on disk rather than your listening, and preserving them would
produce a database that misreports when it was built.

> **Tip**: For detailed examples and advanced usage of each command, check out the [Examples](Examples/) folder.

### GUI
Run `dap-db-manager` (or `uv run dap-db-manager`) to launch the visual interface.

---

## Configuration
Configuration is stored in `~/.ddm/.rdbm_config.toml`. You can specify a custom config file with `--config`.

---

## Troubleshooting

- **wxPython errors**: On Linux, install `libgtk-3-dev`. On macOS, ensure you have a framework build of Python.
- **GUI won't start**: The CLI (`ddm`) generally has fewer dependencies and is more robust for headless usage.

---

## License
GPL v2 or later. See [LICENSE](LICENSE).
