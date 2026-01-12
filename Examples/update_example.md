# Update Command

The `update` command performs an incremental update of an existing database. It is faster than a full regeneration as it only processes new or modified files. It also attempts to preserve runtime statistics (play counts, ratings, etc.) even if files are renamed or moved.

## Basic Usage

```bash
ddm update --db-dir /path/to/database --music-dir /path/to/music --dap-root /path/to/
```

## Arguments


| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--db-dir` | Path | **Yes** | Path to existing database directory. |
| `--music-dir` | Path | **Yes** | Path to music directory to scan. |
| `--output`, `-o` | Path | No | Output directory (default: update in place). |
| `--dap-root` | Path | No | DAP mount point for cross-compilation. |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level. |


## Examples

### Standard Update

Update the database located in `~/Music/.rockbox` with changes from `~/Music`:

```bash
ddm update --db-dir ~/Music/.rockbox --music-dir ~/Music --dap-root /Users/user
```

### Update and Save to New Location

Read the database from one location, update it, but save the result to a new location (leaving the original untouched):

```bash
ddm update --db-dir ./old_db --music-dir ~/Music --output ./new_db --dap-root /Users/user
```

### Handling Renames

The update command automatically detects renamed files to preserve their statistics.

1. You rename `01_Song.mp3` to `01 - Song.mp3`.
2. Run `update`:
   ```bash
   ddm update --db-dir .rockbox --music-dir ~/Music --dap-root /Users/user
   ```
3. The command will report:
   ```
   ✓ 1 file(s) were renamed/moved. Statistics (playcount, ratings, etc.) have been preserved.
   ```

### JSON Output

```bash
ddm update --db-dir .rockbox --music-dir ~/Music --dap-root /Users/user --json
```

**Output:**
```json
{
  "status": "success",
  "db_path": "/path/to/.rockbox",
  "music_dir": "/path/to/music",
  "original_entries": 1000,
  "final_entries": 1005,
  "added": 5,
  "renamed": 0,
  "deleted": 0,
  "unchanged": 1000,
  "duration_ms": 500
}
```
