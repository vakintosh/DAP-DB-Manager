A Python-based utility to accelerate Rockbox library management by generating database files on your PC. Designed to bypass the slow indexing speeds of vintage hardware, it allows you to build, validate, and map paths for your entire collection in seconds.

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPL%20v2-blue.svg)](LICENSE)

---

## Features

- **Fast database generation** from audio metadata (MP3, FLAC, MP4, Ogg Vorbis, WMA, and more)
- **Cross-compilation support** - build database on laptop/server for iPod (180x faster than on-device)
- **True parallel processing** - multiprocessing bypasses Python GIL (4-15x faster on multi-core systems)
- **Incremental updates** - delta updates with rename detection preserve playcount/rating stats
- **Intelligent caching** - persistent tag cache and memory-based optimization
- **Full CLI suite** - generate, validate, inspect, load, and copy databases
- **wxPython GUI** - async operations with cancellable tasks and real-time progress
- **Customizable titleformat** - foobar2000 syntax for flexible metadata organization
- **Docker support** - production-ready containerization with Kubernetes examples
- **CI/automation friendly** - JSON output, exit codes, and headless operation

Based on the original 2009 Python 2.x GUI implementation by **Mike Richards** and the inspect database implementation by **Aren Olson** - See [Legacy Codebase](Legacy_Codebase)

---

## Status

**Work in Progress** - Under active development

**Tested on:**
- ✅ macOS Sonoma 14.8.3 (Intel Mac)
- ✅ maOS Tahoe 26.1 (Apple Silicon)
- ✅ Ubuntu 24.04 LTS (Kernel 6.17.0, aarch64 / Raspberry Pi)
- 🔄 Windows (in progress)

---

## Requirements

### Core (CLI)
- **Python**: 3.11 or higher
- **mutagen**: 1.47.0 or higher
- **rich**: 13.0.0 or higher (for CLI formatting)

### Optional (GUI)
- **wxPython**: 4.2.4 or higher (requires framework-enabled Python on macOS)

> **Note**: wxPython is only needed for the GUI. The CLI tool (`rdbm`) works without it,
> making it ideal for headless servers or environments where GUI dependencies are problematic.

---

## Installation

### Using Docker (Recommended for Production/CI)

Clean, production-ready containerization with full Kubernetes support.

```bash
# Build the image
docker build -t rockbox-db-manager .

# Generate database
docker run --rm \
  -v /path/to/music:/input:ro \
  -v /path/to/output:/output \
  rockbox-db-manager \
  generate --music-dir /input --output /output/database_v1

# Generate with JSON output (for automation/CI)
docker run --rm \
  -v /path/to/music:/input:ro \
  -v /path/to/output:/output \
  rockbox-db-manager \
  generate --music-dir /input --output /output/database_v1 --json
```

### Using UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/vakintosh/rockbox-db-manager.git
cd rockbox-db-manager

# Install CLI only (without GUI/wxPython)
uv sync

# OR: Install with GUI support
uv sync --extra gui

# Run the CLI (works without wxPython)
uv run rdbm --help

# Run the GUI (requires wxPython)
uv run rockbox-db-manager
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/vakintosh/rockbox-db-manager.git
cd rockbox-db-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install CLI only (without GUI/wxPython)
pip install -e .

# OR: Install with GUI support
pip install -e ".[gui]"

# Run the CLI (works without wxPython)
rdbm --help

# Run the GUI (requires wxPython)
rockbox-db-manager-gui
```

---

## Quick Start

```bash
# First-time setup: Detect mount notation (e.g., /<HDD0>)
# Run this BEFORE generating your first database
rdbm detect-mounts --db-dir /path/to/.rockbox
# If no database exists yet, manually set it:
rdbm detect-mounts --db-dir /path/to/.rockbox --set-mount "/<HDD0>"

# Generate a database (mount notation auto-applied from config)
rdbm generate --music-dir /path/to/music --output /path/to/.rockbox

# Validate database integrity
rdbm validate --db-dir /path/to/.rockbox

# Inspect database files
rdbm inspect --db-dir /path/to/.rockbox

# Get detailed help for any command
rdbm --help
rdbm generate --help
```

---

## Usage

### Command-Line Interface

The `rdbm` command provides several subcommands for database management:

- **`generate`** - Create Rockbox database from music folder
- **`update`** - Update database with new/deleted files (delta update)
- **`detect-mounts`** - Detect or set Rockbox mount notation (e.g., /<HDD0>)
- **`load`** - Display existing database information
- **`validate`** - Check database integrity
- **`inspect`** - Low-level file inspection
- **`write`** - Copy database to new location

For detailed options and usage:
```bash
rdbm --help              # List all commands
rdbm generate --help     # Help for specific command
rdbm update --help       # Help for update command
```

**Key Features:**
- Tag caching for faster regeneration (`--save-tags` / `--load-tags`)
- Delta updates to add new files without full rebuild (`update` command)
- **Cross-compilation** - build database on laptop for iPod (`--ipod-root`)
- Configuration file support (`--config`)
- JSON output for automation (`--json`)
- Parallel processing (auto-configured, or use `--workers N`)
- Detailed logging levels (`--log-level debug`)

#### Cross-Compilation (Build on Laptop for iPod)

**Problem**: Building tagcache on iPod takes 30+ minutes and drains battery significantly.

**Solution**: Use `--ipod-root` to build database on laptop with correct path translation:

```bash
# Step 1: Detect mount notation (first time only)
rdbm detect-mounts --db-dir /Volumes/IPOD/.rockbox
# Auto-detects /<HDD0> and saves to config

# Step 2: Generate database
# macOS - iPod mounted at /Volumes/IPOD
rdbm generate \
  --music-dir /Volumes/IPOD/Music \
  --output /Volumes/IPOD/.rockbox \
  --ipod-root /Volumes/IPOD

# Windows - iPod as drive E:
rdbm generate \
  --music-dir E:\Music \
  --output E:\.rockbox \
  --ipod-root E:

# Update existing database (cross-compiled)
rdbm update \
  --db-dir /Volumes/IPOD/.rockbox \
  --music-dir /Volumes/IPOD/Music \
  --ipod-root /Volumes/IPOD
```

**How it works:**
- Laptop path: `/Volumes/IPOD/Music/Song.mp3`
- After `--ipod-root` translation: `/Music/Song.mp3`
- After mount notation: `/<HDD0>/Music/Song.mp3` (as Rockbox expects)
- **180x faster** than building on device
- **Zero battery drain**

See [CROSS_COMPILATION.md](CROSS_COMPILATION.md) for detailed guide with automation examples.

#### Update Command (Delta Update)

The `update` command performs incremental database updates similar to Rockbox's "Update Now" feature:

```bash
# Update existing database with new/deleted/renamed files
rdbm update --db-dir /path/to/database --music-dir /path/to/music

# Update and write to different location
rdbm update --db-dir /path/to/database --music-dir /path/to/music --output /path/to/output
```

**Benefits of Delta Update:**
- ✓ Faster than full rebuild (only processes new files)
- ✓ Preserves playcount, rating, lastplayed statistics
- ✓ **Detects renamed/moved files** to maintain statistics
- ✓ Marks missing files as deleted (doesn't remove them)
- ✓ Perfect for adding new albums to existing database

**Rename Detection:**
The update command automatically detects when files or folders are renamed:
- Simple renames: `01_Song.mp3` → `01 - Song.mp3`
- Folder moves: `Artist/Album/Song.mp3` → `Music/Artist - Album/Song.mp3`
- Preserves all runtime data (play counts, ratings, last played, etc.)

This prevents the loss of statistics that would occur if renamed files were treated as deletions + additions.

### GUI Application

```bash
# Launch GUI
rockbox-db-manager

# Or with UV
uv run rockbox-db-manager
```

Features include visual folder selection, progress tracking, and database inspection.

---

## Configuration

Configuration files use TOML format. See [.rdbm_config_example.toml](.rdbm_config_example.toml) for all available options.

**Default locations:**
- Linux/macOS: `~/.rdbm/.rdbm_config.toml`
- Windows: `%USERPROFILE%\.rdbm\.rdbm_config.toml`

Use custom config with `--config` flag. For titleformat syntax, see: [Foobar2000 Titleformat Reference](http://wiki.hydrogenaudio.org/index.php?title=Foobar2000:Titleformat_Reference)

---

## Development

```bash
# Run tests
uv run pytest -v

# With coverage
uv run pytest --cov=src/rockbox_db_manager --cov-report=html -v

# Linting and formatting
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

---

## Troubleshooting

### wxPython Installation Issues

#### Linux: GTK+ Development Files Error

If you encounter this error on Linux:
```
configure: error: The development files for GTK+ were not found.
```

**Solution 1: Use CLI Only (Recommended for Servers)**

The CLI (`rdbm`) works without wxPython. Install without GUI support:
```bash
# Using uv
uv sync

# Using pip
pip install -e .
```

**Solution 2: Install GUI Dependencies**

If you need the GUI, install GTK+ development files:

Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install libgtk-3-dev
```

Fedora/RHEL:
```bash
sudo dnf install gtk3-devel
```

Then install with GUI support:
```bash
# Using uv
uv sync --extra gui

# Using pip
pip install -e ".[gui]"
```

#### macOS: Framework Python Required

wxPython requires framework-enabled Python on macOS. If using Homebrew:
```bash
brew install python-tk@3.11
```

#### GUI Won't Start

If the GUI entry point fails with "wxPython is not installed":
```bash
# Install with GUI support
pip install rockbox-db-manager[gui]

# Or in development mode
pip install -e ".[gui]"
```

#### Testing Without GUI

Verify the CLI works independently:
```bash
rdbm --version
rdbm generate --help
```

---

## Contributing

Contributions welcome! Please ensure:

1. All tests pass (`uv run pytest`)
2. Code passes linting (`uv run ruff check`)
3. Pre-commit hooks installed (recommended):
   ```bash
   uv run pre-commit install
   uv run pre-commit install --hook-type pre-push
   ```

Pre-commit hooks automatically check code quality on commit/push.

---

## License

GPL v2 or later

See LICENSE for full license text.

---

## Additional Resources

- [Rockbox Official Website](https://www.rockbox.org/)
- [Rockbox Database Format](https://www.rockbox.org/wiki/DataBase)
- [Foobar2000 Titleformat Reference](http://wiki.hydrogenaudio.org/index.php?title=Foobar2000:Titleformat_Reference)
- [mutagen Documentation](https://mutagen.readthedocs.io/)
- [wxPython Documentation](https://docs.wxpython.org/)

---

## Known Issues

- GUI testing requires manual verification (0% automated coverage)
- Some titleformat functions not yet fully implemented
- Watch command disabled pending further testing

See [GitHub Issues](https://github.com/vakintosh/rockbox-db-manager/issues) for complete list and updates.

---

**Enjoy managing your Rockbox databases! 🎵**
