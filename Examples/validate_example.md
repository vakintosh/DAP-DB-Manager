# Validate Command

The `validate` command checks the integrity of a Rockbox database. It ensures all required files exist, parses the index, and checks for common issues like orphaned tag references or duplicate entries.

## Basic Usage

```bash
ddm validate --db-dir /path/to/database
```

## Arguments


| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--db-dir` | Path | **Yes** | Path to database directory. |
| `--quiet`, `-q` | Flag | No | Quiet mode - only output errors. |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level. |


## Examples

### Check Database Integrity

```bash
ddm validate --db-dir ~/.rockbox
```

**Output:**
```
Validating database: /Users/user/.rockbox

✓ All database files present
✓ Database loaded successfully
✓ No orphaned references found

✓ Validation Passed
```

### JSON Output (for CI/CD or Scripts)

```bash
ddm validate --db-dir ~/.rockbox --json
```

**Output:**
```json
{
  "status": "success",
  "db_path": "/Users/user/.rockbox",
  "entries": 1250,
  "warnings": null
}
```

### Failure Scenario

If the database is corrupted or missing files:

```
✗ Missing database files
  • Missing 1 required database files: database_4.tcd

✗ Validation Failed
Issues found:
  • Missing 1 required database files: database_4.tcd
```
