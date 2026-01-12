# Load Command

The `load` command is a simple utility to load the database and display high-level statistics. It serves as a quick check to verify the database is readable and to see entry counts.

## Basic Usage

```bash
ddm load --db-dir /path/to/database
```

## Arguments


| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--db-dir` | Path | **Yes** | Path to database directory. |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level. |


## Examples

### Show Database Stats

```bash
ddm load --db-dir ~/.rockbox
```

**Output:**
```
Database Information:
  Location: /Users/user/.rockbox
  Entries:  1250

Tag Files:
  filename    :   1250 entries
  title       :   1250 entries
  artist      :    450 entries
  album       :    120 entries
  ...
```

### JSON Output

```bash
ddm load --db-dir ~/.rockbox --json
```
