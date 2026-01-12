# Detect Mounts Command

The `detect-mounts` command analyzes an existing Rockbox database to determine the "mount notation" used. Rockbox databases often use prefixes like `/<HDD0>` or `/<MMC1>` to represent storage devices. This command identifies these prefixes or allows you to set them manually.

## Basic Usage

```bash
ddm detect-mounts --db-dir /path/to/.rockbox/
```

## Arguments


| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--db-dir` | Path | **Yes** | Path to existing database directory. |
| `--set-mount` | String | No | Manually set mount notation (e.g., `/<HDD0>`). |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level. |


## Examples

### Detect Existing Mounts

Scan the database to see what mount points are used:

```bash
ddm detect-mounts --db-dir ~/.rockbox
```

**Output:**
```
Detected Mount Points
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Mount Notation ┃ File Count ┃ Sample Paths             ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ /<HDD1>        │      1,250 │ /<HDD1>/Music/Song.mp3   │
│                │            │ /<HDD1>/Music/Album/     │
└────────────────┴────────────┴──────────────────────────┘

✓ Primary mount: /<HDD1> (1250 files)
  Saved to config: ...
```

### Manually Set Mount Notation

If you know the mount point should be `/<SD1>` but don't have a database yet, or want to override the detection:

```bash
ddm detect-mounts --db-dir ~/.rockbox --set-mount /<SD1>
```

### Multiple Mount Points

If your database spans multiple storage devices (e.g., internal storage + SD card), this command will list all of them.

```bash
ddm detect-mounts --db-dir ~/.rockbox
```

**Output:**
```
Detected Mount Points
...
│ /<HDD0>        │        500 │ ...                      │
│ /<MMC1>        │        750 │ ...                      │
...
⚠ Multiple mount points detected!
```
