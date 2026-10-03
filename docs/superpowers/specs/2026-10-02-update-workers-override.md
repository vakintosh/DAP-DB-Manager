# Make `--workers`/`--no-parallel` Actually Work, and Expose It on `update`

**Status:** proposed (spike -- not yet implemented, no code written)
**Date:** 2026-10-02
**Issues:** [#27](https://github.com/vakintosh/DAP-DB-Manager/issues/27) (`update` has no worker override), [#28](https://github.com/vakintosh/DAP-DB-Manager/issues/28) (`--workers` is a no-op for `generate`)
**Related specs:** `docs/superpowers/specs/2026-09-08-preserve-stats-design.md` (same house style)
**Related wiki:** `journal/2026-10-02-ddm-update-modified-files-fix.md`, `concepts/ipod-rockbox-pipeline.md`, `entities/dap-db-manager.md`

## Problem

The SoundCloud -> iPod pipeline (`soundcloud-ipod-pipeline` skill / `concepts/ipod-rockbox-pipeline`) rebuilds the Rockbox tag-cache database with `ddm generate --workers 2` instead of `ddm update`, specifically because of a 2026-09-08 real-device measurement: default concurrency (`cpu_count + 4` reader threads) against the iPod Classic's single PATA disk behind USB 2.0 silently dropped **10,687 of 17,445 files** -- classified as parse failures, database still validates, run still exits 0. `--workers 2` was measured to bring that to zero.

Two things block adopting `update` for this pipeline today, found investigating one after the other:

1. **`update` has no `--workers`/`--no-parallel` flag at all** (#27). Its own first step re-scans the whole `--music-dir` tree through the identical `FileScanner.add_dir()` path `generate` uses, at the same default concurrency -- so it's exposed to the same failure mode with no CLI-level mitigation.

2. **`--workers` doesn't actually do anything for `generate` either** (#28), discovered while scoping the fix for #1. `Database.__init__` eagerly constructs `self._scanner` (`FileScanner`, backed by a persistent `ThreadPoolExecutor`) and `self._generator` (`DatabaseGenerator`, backed by a persistent `ProcessPoolExecutor`), each sized once at construction time from `self.max_workers` (auto-detected as `min(32, cpu_count + 4)`). `cmd_generate` then does `db.max_workers = args.workers` -- but that line runs *after* both executors already exist, and nothing re-reads `self.max_workers` or rebuilds the pools afterward. Verified directly against the real `cmd_generate` code path:

   ```python
   db = Database()
   db._scanner._executor._max_workers   # 12 (cpu_count + 4 here)
   db.max_workers = 2                   # exactly what cmd_generate does for --workers 2
   db._scanner._executor._max_workers   # still 12 -- unchanged
   ```

Fixing #1 without fixing #2 would ship a flag that silently does nothing -- worse than no flag, because it looks like a fix and isn't. Both need to land together.

### The open question this raises, which this spec does not resolve

If `--workers` has been a no-op since the persistent-executor refactor (`1b5ce85`, 2026-01-15) -- which predates the 2026-09-08 measurement that it eliminated the file-loss bug -- then that measurement's causal story is in question. Either something else in that session's two runs actually differed (not isolated as carefully as the write-up implies), or there's a code path this investigation hasn't found yet that does honor the override. **This must be re-measured on the real device as part of implementing this spec**, isolating `--workers` as the only variable, before trusting either the old conclusion or the new fix. See "Testing" below.

## Goal

1. `--workers N` / `--no-parallel` actually change the concurrency used by the scan and generation phases, for both `generate` and `update`.
2. `update` gets the same `--workers`/`--no-parallel` flags `generate` has.
3. The fix is verified on the real device against the real failure mode (file-loss at scale), not just unit-level pool-size assertions -- the original bug was only ever visible at 17k-file scale.

Non-goal: changing the *default* concurrency formula (`min(32, cpu_count + 4)`). Only making the override path real, and extending it to `update`.

## Approach

### Make the override real

The root cause is construction-time binding: `FileScanner` and `DatabaseGenerator` build their executor pools in `__init__`, using whatever `max_workers` the `Database` happened to have at that moment -- which is always the auto-detected default, because `Database.__init__` builds them before any caller gets a chance to override `self.max_workers`.

Two candidate fixes; pick one during implementation, don't mix:

**Option A -- constructor parameter (preferred).** Add `max_workers: Optional[int] = None` to `Database.__init__`, and pass it straight through to the `FileScanner`/`DatabaseGenerator` constructors instead of always using the auto-detected value:

```python
def __init__(self, config=None, dap_root=None, stats_preserver=None, max_workers: Optional[int] = None):
    ...
    cpu_count = multiprocessing.cpu_count()
    self.max_workers = max_workers if max_workers is not None else min(32, cpu_count + 4)
    self._scanner = FileScanner(max_workers=self.max_workers)
    self._generator = DatabaseGenerator(max_workers=self.max_workers, ...)
```

Then both `cmd_generate` and `cmd_update` pass `max_workers=args.workers` (or `None`) at construction time, instead of mutating `db.max_workers` after the fact. This is the minimal change: one new parameter, two call sites updated, no lifecycle change to `FileScanner`/`DatabaseGenerator` themselves.

**Option B -- lazy pool construction.** Defer `ThreadPoolExecutor`/`ProcessPoolExecutor` creation in `FileScanner`/`DatabaseGenerator` until first use (`add_dir`/`generate`), reading `self.max_workers` at that point. This would make a post-construction `db.max_workers = N` mutation work too, which is more forgiving of future callers, but touches more code (two classes' lifecycle, plus whatever currently assumes the executor exists immediately, e.g. `shutdown()`). Not needed for this spec's scope; only pick this if Option A turns out to conflict with something not yet found (e.g. a code path that constructs a `Database` once and reuses it across multiple scans with different worker counts).

Recommendation: **Option A**. It's a smaller, more legible diff, and nothing in the current codebase appears to reuse one `Database` instance across calls that need different worker counts.

### Expose `--workers`/`--no-parallel` on `update`

Mirror `generate`'s existing argparser group, in `src/dap_db_manager/cli/__init__.py`, inside the `update_options` group (currently holds `-o/--output` and `--dap-root`):

```python
update_options.add_argument(
    "--no-parallel",
    action="store_true",
    help="Disable parallel processing (useful for debugging or small datasets)",
)
update_options.add_argument(
    "--workers",
    type=int,
    metavar="N",
    help="Number of worker threads for parallel processing (default: auto-calculated as CPU count + 4, max 32)",
)
```

In `cmd_update` (`src/dap_db_manager/cli/commands/update.py`), construct `Database` the same way `cmd_generate` will (via the Option A constructor parameter), and pass the parallel override down to `update_database()`:

```python
workers = args.workers if getattr(args, "workers", None) else None
db = Database.read(str(db_path), callback=callback, dap_root=dap_root, max_workers=workers)
...
no_parallel = getattr(args, "no_parallel", False)
stats = db.update_database(str(music_path), callback=update_callback, parallel=not no_parallel if no_parallel else None)
```

Note `Database.read()` is a `@staticmethod` that constructs a fresh `Database(dap_root=dap_root)` internally -- it will need the same `max_workers` parameter threaded through, since that's where the real `Database` object (and its scanner/generator) actually gets built for `update`.

### CLI help text

Match `generate`'s existing wording exactly (`"Number of worker threads for parallel processing (default: auto-calculated as CPU count + 4, max 32)"`), so the two commands don't drift into inconsistent phrasing for the same concept.

## Out of scope

- Changing `update`'s inability to bootstrap from nothing (separate, already-documented gap -- `update` requires an existing `--db-dir`).
- Exposing `--workers` on any other command (`validate`, `inspect`, `load`, `write`, `detect-mounts` don't do bulk file I/O the same way).
- Revisiting the `min(32, cpu_count + 4)` default formula itself.

## Testing

**Unit -- the plumbing itself (this is what #28 is really about):**
- `Database(max_workers=2)._scanner._executor._max_workers == 2`
- `Database(max_workers=2)._generator._executor._max_workers == 2`
- `Database()` with no override still gets `min(32, cpu_count + 4)` (regression guard for the default path)
- `cmd_generate` with `--workers 2`, inspect the constructed `Database` object's scanner/generator pool sizes (not just the `.max_workers` attribute, which is exactly what let this hide before -- assert on `._executor._max_workers`, the thing that actually controls concurrency)
- same assertion for `cmd_update` with `--workers 2`

**Unit -- CLI parsing:**
- `ddm update --help` shows `--workers`/`--no-parallel` (a literal regression test for #27 -- the bug was these flags not existing at all)
- `--no-parallel` on `update` disables parallel scanning the same way it does for `generate`

**Integration (small fixture, fast):**
- `update --workers 1` against a real fixture directory still produces a correct database (same entry count as default-worker run) -- proves the override doesn't break correctness, only concurrency

**Real-device validation (the part that actually matters here, and the part this spec cannot do without hardware access):**
- Re-run the original 2026-09-08 comparison on the real iPod Classic: full `/Music` scan (~17k files) via `generate` at default concurrency vs `--workers 2`, with the *fixed* plumbing, and confirm the failure count actually drops to the previously-measured range. This re-validates (or corrects) the original causal claim now that the mechanism has changed.
- Once that's confirmed, run the equivalent comparison for `update --workers 2` against the same library, to confirm the fix actually closes the gap for `update` the way it does for `generate`.
- Only after both of those pass should `concepts/ipod-rockbox-pipeline.md` and the `soundcloud-ipod-pipeline` skill be updated to recommend `update --workers 2` over `generate --workers 2` for this pipeline.

## Risks

| Risk | Mitigation |
|---|---|
| The original 2026-09-08 measurement's causal story turns out to be wrong (something else fixed the file-loss, not `--workers`) | The real-device re-test above is designed to surface this either way; write up whatever it finds, even if it contradicts the prior record |
| Fixing the plumbing changes default behavior for existing callers that already (incorrectly) relied on `db.max_workers` being mutable post-construction | Grep the codebase and tests for `.max_workers =` assignments after construction before landing; `tests/test_cli_generate.py` and `tests/test_generator*.py` are the likely places |
| `Database.read()`'s new `max_workers` parameter breaks existing call sites that don't pass it | Default to `None` (auto-detect), identical to today's behavior, at every call site that doesn't explicitly opt in |
| Real-device re-test isn't actually run before this ships | Don't update the pipeline's recommended command (`generate` -> `update`) until it is -- the code fix and the operational recommendation are separate deliverables |

## Open questions

- Does the real-device re-test confirm `--workers` (once actually wired up) eliminates the file-loss the same way the original measurement claimed? Unknown until run.
- Should `Database.read()` gain the `max_workers` parameter, or should callers set it via a separate method after construction but before the first `add_dir`/`generate`/`update_database` call? Option A above assumes the former (simpler, matches how `dap_root`/`config` already work on `Database.read()`).
