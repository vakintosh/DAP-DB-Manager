# Inspect Command

The `inspect` command allows you to view the raw contents and header information of Rockbox database files (`.tcd`). This is useful for debugging or understanding the low-level structure of the database.

## Basic Usage

```bash
ddm inspect --db-dir /path/to/database
```

By default, this inspects the master index file (`database_idx.tcd`).

## Arguments


| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--db-dir` | Path | **Yes** | Path to database directory. |
| `--file-number` | Integer | No | Database file number (0-8) to inspect. |
| `--quiet`, `-q` | Flag | No | Show only header information, not entries. |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level. |


### File Numbers

| Number | Tag File | Description |
|--------|----------|-------------|
| 0 | exact filenames | Full filenames |
| 1 | filenames | Filenames (maybe truncated/processed) |
| 2 | directory names | Directory paths |
| 3 | titles | Track titles |
| 4 | artists | Artist names |
| 5 | albums | Album names |
| 6 | genres | Genre names |
| 7 | composers | Composer names |
| 8 | comments | Comments/Descriptions |
| (None) | Index | The main index file linking all tags. |

## Examples

### Inspect Index File

View header info and first few entries of the main index:

```bash
ddm inspect --db-dir ~/.rockbox
```

### Inspect Artist Tags

View the list of artists stored in the database (File #4):

```bash
ddm inspect --db-dir ~/.rockbox --file-number 4
```

**Output:**
```
Tag File Header (artist)
  Magic       0x54434434
  Data Size   15,240 bytes
  Entry Count 450

First 10 entries:
Index  Offset  Length  Data
    0     N/A       5  ABBA
    1     N/A       7  Beatles
...
```

### JSON Output

Get technical details in JSON:

```bash
ddm inspect --db-dir ~/.rockbox --file-number 3 --json
```

**Output:**
```json
{
  "status": "success",
  "file_path": "/path/to/database_3.tcd",
  "file_type": "title",
  "magic": "0x54434433",
  "entry_count": 1250,
  ...
}
```
