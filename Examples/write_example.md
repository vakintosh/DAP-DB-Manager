# Write Command

The `write` command loads an existing database into memory and writes it out to a new location. This effectively copies the database, but since it parses and re-writes the data, it can also be used to:
- Defragment or optimize the database files.
- Verify that the database can be fully read and written (round-trip test).

## Basic Usage

```bash
ddm write --db-dir /path/to/source --output /path/to/dest
```

## Arguments


| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--db-dir` | Path | **Yes** | Path to source database directory. |
| `--output`, `-o` | Path | **Yes** | Path to destination directory. |
| `--json` | Flag | No | Output results in JSON format. |
| `--log-level`, `-l` | String | No | Set logging level. |


## Examples

### Copy/Rewrite Database

```bash
ddm write --db-dir ~/.rockbox --output ~/Desktop/staged_rockbox
```

This will create `~/Desktop/staged_rockbox` if it doesn't exist and populate it with a fresh set of `.tcd` files generated from the source database.
