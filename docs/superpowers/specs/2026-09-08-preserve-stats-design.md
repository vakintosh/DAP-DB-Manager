# Preserve Runtime Stats Across `generate`

**Status:** design approved, not implemented
**Date:** 2026-09-08
**Target version:** 0.9.0 (behavioural change to `generate`)

## Problem

`ddm generate` performs a full rebuild from the music files on disk. It has no
stats source, so every rebuild **silently destroys the device's runtime
statistics** — playcount, rating, playtime, lastplayed, and the resume position.

This undercuts the tool's entire purpose. `ddm` exists because rebuilding the
tag cache on an iPod Classic is ~180× slower than doing it on a PC. But today
the fast path is also the lossy one: anyone who actually listens to the device
must either accept losing their history or fall back to `update`, which is
incremental and cannot recover from a corrupt or missing database.

`update` already preserves stats — it keeps existing entries and uses rename
detection to carry them across path changes. `generate` has no equivalent.

## Goal

Make `generate` non-destructive by default: a full rebuild keeps the listening
history that the device accumulated.

Non-goal: matching the upstream Rockbox surface. See "Rejected alternatives".

## Approach

Before wiping the output directory, read the database already there and carry
the runtime stats into the newly generated entries, matched by path.

### Source of stats

The existing database in `--output`. `generate` already resolves and creates
that directory; it will now attempt `Database.read()` on it first.

An optional `--preserve-stats-from <dir>` covers the case where the new database
is written somewhere other than where the old one lives.

If no readable database is found, the rebuild proceeds and says so.

### Matching

By database path (tag 4), exact, case-insensitive — consistent with `dap_root`
handling elsewhere in the codebase.

Both sides are produced by `utils.normalize_dap_path()`, so old and new paths
are directly comparable. This is what makes the match reliable, and is only
true as of the de-duplication in #21.

### Fields carried

| Tag | Field | Carried |
|---|---|---|
| 15 | `playcount` | yes |
| 16 | `rating` | yes |
| 17 | `playtime` | yes |
| 18 | `lastplayed` | yes |
| 21 | `lastelapsed` | yes |
| 22 | `lastoffset` | yes |
| 19 | `commitid` | **no** — describes the database, regenerated |
| 20 | `mtime` | **no** — describes the file, regenerated |

`commitid` and `mtime` are properties of the database and the file on disk, not
of the user's listening. Carrying them forward would produce a database that
lies about when it was built and when its files last changed.

### Reporting

Every run reports the outcome explicitly:

```
Preserved stats for 17,102 of 17,139 entries (37 new files, 12 old entries unmatched)
```

Silence is not acceptable here. A partial restore that looks like a full one is
the specific failure mode that disqualified the changelog approach; this design
must not reproduce it. If the old database is missing, unreadable, or empty,
that is stated plainly and the rebuild continues.

### CLI

- Default: **on** when a readable database is found.
- `--no-preserve-stats` opts out (restores current behaviour).
- `--preserve-stats-from <dir>` reads stats from a different directory.

Precedence, so the combinations are unambiguous:

| Flags given | Behaviour |
|---|---|
| neither | read stats from `--output` if a database is there |
| `--preserve-stats-from D` | read from `D`; if `D` has no readable database, warn and continue without stats (do **not** silently fall back to `--output`) |
| `--no-preserve-stats` | no stats carried, from anywhere |
| both | **error and exit** — contradictory intent, better to reject than to guess |

Defaulting to on is a deliberate behavioural change. The current default
silently loses data, and a user who does not already know that will never think
to pass a flag. The cost is that `generate` no longer means "build clean from
files only" — `--no-preserve-stats` restores that meaning for scripts that need
it. This warrants a minor version bump to **0.9.0**.

## Out of scope

**Rename detection during rebuild.** A file that moved between rebuilds gets
fresh stats, exactly as today. `update` already owns rename detection, and
folding it into `generate` requires fingerprinting the whole library — a
separate feature with its own performance characteristics. Ship the common case
first.

**Changelog import/export.** See below.

## Rejected alternatives

### Changelog import (`database_changelog.txt`)

Read a device-exported changelog and apply the stats during generation.

Rejected as the primary mechanism because **the export is partial by design**.
`tagcache_create_changelog` (tagcache.c:3985) skips every entry lacking
`FLAG_DIRTYNUM`, so the file contains only entries modified since the last
commit. If the device has committed, the export is empty. The user would get a
silent, partial stat restore with no way to tell which entries were missed.

It also requires a manual device step the user must remember, on every rebuild.

Reading the old database directly gets the same fields, complete, with no device
interaction.

### Changelog export (`tagcache_create_changelog`)

The symbol the parity audit lists as missing, and the only one compiled into
upstream's own PCTOOL build.

Rejected because it solves nothing for this tool. The device can already export
its own changelog through the Rockbox menu (`tagtree_export`), and `ddm update`
already preserves stats in place. Implementing it in `ddm` would also require
inventing `FLAG_DIRTYNUM` semantics for a tool that generates rather than plays:
`ddm` never marks entries dirty, so the exported file would always be empty.

This is parity as a checkbox. It may still be worth doing later purely to close
the audit item, but it does not serve the goal and should not be confused with
this work.

## Testing

**Unit — the matcher:**
- exact path match carries all six fields
- case-differing path still matches
- new file with no old entry gets zero stats
- old entry with no new file is counted as unmatched, not silently dropped
- empty old database is a clean no-op
- unreadable/corrupt old database does not abort the rebuild

**Unit — CLI precedence:**
- `--no-preserve-stats` together with `--preserve-stats-from` exits with an error
- `--preserve-stats-from` pointing at a directory with no database warns and
  continues, and does not fall back to `--output`

**Integration:**
- generate, inject known stats into the index, regenerate, assert all six fields
  survive with correct values
- assert `commitid` and `mtime` are *not* carried
- `--no-preserve-stats` reproduces current behaviour exactly

**Real-data validation** (17,139-track library):
- generate, inject stats, regenerate
- assert stats preserved for all matched entries
- assert every other tag file is byte-size and sorted-content identical to a run
  without the feature — the same comparison used to validate #21

Note that generated output is not byte-reproducible between runs (ordering
varies); comparisons must be on sorted content and file size, never raw hashes.

## Risks

| Risk | Mitigation |
|---|---|
| Behavioural change surprises existing scripts | `--no-preserve-stats`; minor version bump; reported in every run |
| Path mismatch silently preserves nothing | Explicit counts in the report; integration test asserts non-zero preservation |
| Reading a corrupt old database aborts a rebuild | Treated as "no stats available", rebuild proceeds with a warning |
| Stats carried onto the wrong file after a path collision | Match is exact-path; no fuzzy matching in v1 |

## Open questions

None. Approach, field list, reporting, and the default-on decision are settled.
