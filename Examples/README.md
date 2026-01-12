# Rockbox Database Manager (DDM) - Examples

This directory contains detailed usage examples for the `dap-db-manager` (also known as `dap-db-manager` or `ddm`) CLI.

## Available Commands

| Command | Description | Documentation |
|---------|-------------|---------------|
| `generate` | Create a new database from a music folder. | [View Examples](generate_example.md) |
| `update` | Incrementally update an existing database. | [View Examples](update_example.md) |
| `detect-mounts` | Detect or set mount points (e.g., `/<HDD1>`). | [View Examples](detect_mounts_example.md) |
| `inspect` | View raw database structure and headers. | [View Examples](inspect_example.md) |
| `validate` | Check database integrity. | [View Examples](validate_example.md) |
| `load` | Load database and view statistics. | [View Examples](load_example.md) |
| `write` | Copy/rewrite database files. | [View Examples](write_example.md) |

## Quick Start

To generate a database for your music library:

```bash
ddm generate --music-dir MUSIC_DIR
```

To update it later:

```bash
ddm update --db-dir ~/Music/.rockbox --music-dir ~/Music
```

See individual example files for advanced usage, including JSON output, cross-compilation roots, and performance tuning.
