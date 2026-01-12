# Generate Command

The `generate` command is the primary command for creating a new Rockbox database from a music directory. It scans the specified directory for audio files, extracts metadata, and creates the database files.

## Basic Usage

```bash
uv run -- ddm generate --music-dir /path/to/music --output /path/to/output
```

This will:
1. Scan `/path/to/music` for audio files.
2. Generate database entries.
3. Write the database files to `/path/to/output`.

## Arguments

| Argument | Type | Required | Description |

|----------|------|----------|-------------|
| `--music-dir` | Path | **Yes** | Path to music directory to scan. |
| `--output`, `-o` | Path | **Yes** | Target directory for database files. |
| `--dap-root` | Path | No | DAP mount point for cross-compilation (e.g., `/Volumes/DAP` or `E:`). |
| `--workers` | Integer | No | Number of worker threads for parallel processing (default: auto). |
| `--no-parallel` | Flag | No | Disable parallel processing (useful for debugging). |
| `--config`, `-c` | Path | No | Path to configuration file. |
| `--load-tags` | Path | No | Load tags from cache file to speed up regeneration. |
| `--save-tags` | Path | No | Save tags to cache file for future use. |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level (debug, info, warning, error). |
| `--cache-size` | Integer | No | Override tag cache size. |


## Examples

### Specify Output Directory

Generate the database from `~/Music` but save the database files to `~/Desktop/rockbox_db`:

```bash
ddm generate --music-dir ~/Music --output ~/Desktop/rockbox_db
```

### logical DAP Root

If you are generating a database for a device where the music will be mounted at `/<HDD0>` on the device, but currently the music is at `/Folder/To/Music/Artist/Album/Song.mp3` on your computer, add the `--dap-root` argument to ensure paths in the database are relative to the specified root and that the local path are stripped:

```bash
ddm generate --music-dir /Folder/To/Music/Artist/Album/Song.mp3 --output /path/to/output/folder --dap-root /Folder/To/
```
*Note: This ensures paths in the database are relative to the specified root so the final path on the device will be `/<HDD0>/Music/Artist/Album/Song.mp3`.*

> **Tip:** If you are unsure of the correct mount path (like `/<HDD0>`), you can use the [`detect-mounts`](detect_mounts_example.md) command to automatically find it.

**Recommendation:** It is highly recommended to use the `--dap-root` parameter when generating databases on a computer for a portable player, as it ensures paths are correctly formatted for the device.



### JSON Output

Generate the database and get the result as a JSON object (useful for scripting):

```bash
ddm generate --music-dir ~/Music --output ~/Desktop/rockbox_db --dap-root /Users/user --json
```

**Output:**
```json
{
  "status": "success",
  "input_dir": "/Users/user/Music",
  "output_dir": "/Users/user/Desktop/rockbox_db",
  "tracks": 1250,
  "files_scanned": 1250,
  "files_failed": 0,
  "duration_ms": 3500
}
```

### Using Tag Cache

To speed up subsequent generations, you can save and load parsed tags if tag has not changed between generations:

```bash
# First run: Save tags
ddm generate --music-dir ~/Music --output ~/Desktop/rockbox_db --dap-root /Users/user --save-tags tags.cache

# Second run: Load tags (much faster)
ddm generate --music-dir ~/Music --output ~/Desktop/rockbox_db --dap-root /Users/user --load-tags tags.cache
```
