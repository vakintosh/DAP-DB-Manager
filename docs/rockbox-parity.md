# Rockbox Tag-Cache Parity Audit

**ddm version audited:** 0.8.1 (`pyproject.toml`)
**Upstream reference:** Rockbox firmware `apps/tagcache.{c,h}` (5,523 + 218 lines)
**Date:** 2026-09-07

## Scope

This audit covers the **entire public surface of `tagcache.h`**, including symbols that
a PC-side generator cannot and should not implement. Device-only functions are listed
as explicit **N/A rows with a reason** rather than omitted, so the matrix is provably
complete and can be re-diffed against a future upstream pull.

Legend: ✅ implemented · ⚠️ partial / divergent · ❌ missing · ⊘ N/A (device-only)

---

## 1. On-Disk Format

Unchanged since header v16; upstream has not altered the binary layout.

| Item | Rockbox | ddm | Status |
|---|---|---|---|
| `TAGCACHE_MAGIC` | `0x54434810` (v16) | `MAGIC = 1413695504` (`constants.py:58`) | ✅ |
| `enum tag_type` order (23 tags) | `artist … tag_lastoffset` | `constants.py:7–46`, same order | ✅ |
| `struct index_entry` | `tag_seek[TAG_COUNT]` + `flag` = 24 × int32 | `IndexEntry.size = 4*24` | ✅ |
| `struct master_header` | magic, datasize, entry_count, serial, commitid, dirty | `header_size = 6*4`; fields at `indexfile.py:24–26,103–105` | ✅ |
| Flag bits | DELETED / DIRCACHE / DIRTYNUM / TRKNUMGEN / RESURRECTED | all five, `constants.py:48–52` | ✅ |
| `tag_virt_canonicalartist` → `database_12.tcd` | yes | yes (`constants.py:16`) | ✅ |
| `<Untagged>` literal | yes | `generator.py:81,134,161,199,236,592` | ✅ |
| `FLAG_TRKNUMGEN` on generated track numbers | yes | `generator.py:602` | ✅ |
| `serial` / `commitid` / `dirty` maintenance | yes | `indexfile.py:95–96` (commitid++, dirty=0) | ✅ |

**Conclusion:** binary compatibility is complete. Nothing stale here.

---

## 2. Public API Surface (`tagcache.h`)

Every non-static declaration in the header, in file order.

### 2.1 Build & update — the parity core

| Symbol | ddm equivalent | Status |
|---|---|---|
| `do_tagcache_build()` | `ddm generate` → `DatabaseGenerator` + `DatabaseIO` | ✅ |
| `tagcache_reverse_scan()` | folded into `generate` (PCTOOL-only upstream too) | ✅ |
| `tagcache_update()` | `ddm update` + `rename_detector.py` (stat preservation) | ✅ |
| `tagcache_rebuild()` | no separate command; `generate` wipes + rebuilds | ✅ (functionally) |
| `tagcache_tag_to_str()` | `constants.py` tag list / index mapping | ✅ |

### 2.2 Changelog — **the one real gap**

| Symbol | ddm equivalent | Status |
|---|---|---|
| `tagcache_create_changelog()` (`tagcache.c:3985`) | none | ❌ **missing** |
| `tagcache_import_changelog()` (`tagcache.c:3932`) | none | ❌ missing (but see note) |

Verified by grep: **zero occurrences of "changelog" anywhere in `src/`.**

Two details the previous audit did not capture, both of which change the priority:

1. **`tagcache_import_changelog` is inside `#ifndef __PCTOOL__`** (guard opens at
   `tagcache.c:3785`, closes at `:3983`). Upstream's own PC tool therefore **does not
   ship import** — it is a device-side operation. `tagcache_create_changelog` sits at
   `:3985`, *outside* the guard, and **is** compiled into PCTOOL builds.
   → For a PC-side tool, **export is the in-scope half; import is arguably out of scope**
   by upstream's own boundary. Implementing export alone reaches PCTOOL parity.
2. Export is **not** a full dump. `create_changelog` skips any entry lacking
   `FLAG_DIRTYNUM`, and skips `FLAG_DELETED` entries — it emits only rows whose numeric
   data was modified on-device. ddm currently never sets `FLAG_DIRTYNUM` on write, so a
   naive export would legitimately produce an empty changelog after a `generate`.

**File format** (`TAGCACHE_FILE_CHANGELOG = "database_changelog.txt"`, `tagcache.c:152`):

```
## Changelog version 1
artist="…" album="…" genre="…" title="…" filename="…" … lastoffset="0"
```

One line per dirty entry, all 23 tags emitted in enum order — numerics as decimal
(`itoa_buf`), text tags via `tagcache_retrieve`. Serialisation is `write_tag`
(`tagcache.c:3751`): `key="value" ` with `"` and `\` backslash-escaped, newline written
as literal `\n`, **512-byte per-tag buffer cap**. Lines beginning `#` are comments.
Import keys off `filename=`, resolves via `find_index()`, and imports only
`{playcount, rating, playtime, lastplayed, commitid, lastelapsed, lastoffset}`.

### 2.3 Search engine — N/A (device-only)

Runtime query layer for on-device browsing. A generator writes the DB; it never
serves queries against it. All ⊘.

| Symbol | Reason |
|---|---|
| `tagcache_search()` | ⊘ on-device browse-time query |
| `tagcache_search_add_filter()` | ⊘ ditto |
| `tagcache_search_add_clause()` | ⊘ full `enum clause` set (is/is_not/gt/lt/contains/begins_with/ends_with/*_oneof/logical_or) |
| `tagcache_check_clauses()` | ⊘ ditto |
| `tagcache_search_set_uniqbuf()` | ⊘ dedup buffer for browse results |
| `tagcache_get_next()` / `tagcache_retrieve()` | ⊘ result iteration |
| `tagcache_get_numeric()` | ⊘ result accessor |
| `tagcache_search_finish()` | ⊘ result teardown |
| `tagcache_find_index()` | ⊘ *(but see Gap 3 below — the import path needs an equivalent)* |

### 2.4 Runtime numeric edits — N/A (device-only)

These mutate stats as the user plays music. ddm's write path sets numerics at
generation time instead.

| Symbol | Reason |
|---|---|
| `tagcache_update_numeric()` | ⊘ playback-time stat write |
| `tagcache_modify_numeric_entry()` | ⊘ ditto |
| `tagcache_increase_serial()` | ⊘ serial bump on device edit (ddm sets serial at build) |

### 2.5 Lifecycle / init / commit — N/A (firmware lifecycle)

| Symbol | Reason |
|---|---|
| `tagcache_init()` / `is_initialized()` / `is_fully_initialized()` / `is_usable()` | ⊘ firmware boot lifecycle |
| `tagcache_start_scan()` / `stop_scan()` | ⊘ background scan thread |
| `tagcache_commit_finalize()` | ⊘ multi-step on-device commit; ddm writes atomically |
| `tagcache_get_stat()` / `get_commit_step()` / `get_max_commit_step()` | ⊘ on-device progress UI |
| `tagcache_prepare_shutdown()` / `shutdown()` | ⊘ safe-poweroff hooks |
| `tagcache_remove_statefile()` | ⊘ `database_state.tcd` is device-managed |
| `tagcache_screensync_event()` / `screensync_enable()` | ⊘ on-device UI redraw |

### 2.6 RAM cache — N/A (`HAVE_TC_RAMCACHE`)

| Symbol | Reason |
|---|---|
| `tagcache_is_in_ram()` | ⊘ in-memory DB copy, device only |
| `tagcache_fill_tags()` | ⊘ populates `struct mp3entry` from ramcache at playback |
| `tagcache_unload_ramcache()` | ⊘ ditto |

### 2.7 `tagtree.c` — N/A

The browser layer (`.tcnav` / tagnavi menu tree, virtual tags, browse formatting).
Entirely on-device UI. ⊘

### 2.8 Virtual tags — correctly not stored

`tag_virt_basename`, `_length_min`, `_length_sec`, `_playtime_min`, `_playtime_sec`,
`_entryage`, `_autoscore` are index ≥ `TAG_COUNT` and computed at browse time.
ddm correctly does not persist them. ✅ (by omission)

---

## 3. Format-Level Gaps (tags ddm *does* implement, but reads wrong)

These are **correctness** defects in shipped functionality — higher practical severity
than the changelog gap.

### Gap 1 — `grouping` (tag 8) missing on MP4 and WMA/ASF — **FIXED 2026-09-07**

Confirmed by grep: `grouping` appears in `mappings/` **only** in `id3.py:361–362`
(`EasyID3.RegisterTextKey("grouping", "TIT1")`, correctly matching Rockbox).

- **MP4** dict (`format_specific.py:48–61`) has **no `grouping` key**. Rockbox reads the
  native **`©grp`** atom. ddm falls through to `MP4_custom_field`, which resolves to
  `----:com.apple.iTunes:GROUPING` — a freeform foobar-convention atom. Files tagged
  correctly for Rockbox produce **empty tag 8**.
- **ASF** dict (`format_specific.py:33–46`) likewise has no `grouping`. Rockbox reads
  **`WM/ContentGroupDescription`**; ddm falls through to `foobar2000/GROUPING`.

**Fix applied:** added `"grouping": "\xa9grp"` to the MP4 dict and
`"grouping": "WM/ContentGroupDescription"` to the ASF dict; the freeform lookups remain
as user-key fallbacks.

A third defect surfaced while fixing this: **`grouping` was never in the default
basic-field table** (`mappings/default.py`). Registering it per-format therefore emitted
`UserWarning: No conversion is defined for field "grouping"` on every import, and
Vorbis/FLAC/Opus resolved grouping only through the user-field fallback rather than a
first-class mapping. Added `"grouping": conv_string_list` to the default table.

**Verified on real data:** of 3,860 MP4 files sampled from a production music
library, **2,754 carry a native `©grp` atom**. Pre-fix, reading `grouping`
from one of these raised `KeyError: ----:com.apple.iTunes:GROUPING` and yielded an empty
tag 8; post-fix it returns the atom's value, and those values are present in the
generated `database_8.tcd`.

### Gap 2 — exotic codecs unsupported

`supported_extensions` (`file_scanner.py:117`) covers ~17 mutagen-taggable formats.
Rockbox additionally indexes chiptune/tracker formats (SID, MOD, SPC, NSF), AC3/A52,
and raw AAC-ADTS. mutagen has no taggers for most. Irrelevant to the current library;
recorded for completeness. Would require hand-written parsers. ⚠️ won't-fix

---

## 4. Gap 3 — AppleDouble sidecars enqueued as tracks — **FIXED**

**Not a Rockbox-parity gap — a deliberate, documented divergence.** See the parity
analysis below before treating this as a bug-for-bug difference.

`scan_directory` (`file_scanner.py:344–361`) selects files on **suffix alone**:

```python
if Path(entry.name).suffix.lower() in self.supported_extensions:
    files_in_dir.append(entry.path)
```

`add_file` (`:161`) and `add_files` (`:254`) apply the same suffix-only test. Grep
confirms **no `._` prefix filter, no dotfile filter, and no `__MACOSX` filter anywhere
in `src/`**.

On exFAT/FAT — the usual format for removable media and portable players — every macOS
tag write creates an AppleDouble sidecar `._<track>.mp3`. That name ends in `.mp3`, so
ddm enqueued it as a candidate track. It is not a valid audio stream, so the tag read
failed and it was reported as a failed file.

### What Rockbox actually does

Upstream does **not** filter these by name. `probe_file_format()`
(`lib/rbcodec/metadata/metadata.c`) matches on the extension alone — exactly like ddm's
original code — so `._track.mp3` passes it. Rockbox instead relies on a **second gate**:
`add_tagcache()` calls `get_metadata_ex()` (`tagcache.c:2295`, `:2343`) and, on failure,
logs and returns without creating an entry.

ddm has the equivalent second gate: an unparseable file goes to the failed list and is
never added to the path set, so it never becomes a database row. **Verified empirically**
— a non-audio `.mp3` yields `paths=0, failed=1`.

### Consequences of the fix

Because both tools already reject these at the parse stage, **the generated database is
identical either way**. This fix does not change database content. What it changes:

- **Failure reporting** — sidecars were counted as failed files, so a library that had
  been tag-edited from macOS reported one spurious failure per previously-written file.
  Rockbox treats the same rejection as a routine skip (a log line), not a failure.
- **Wasted I/O** — each sidecar was opened and parsed before being rejected.

### The divergence, stated plainly

A file *legitimately* named `._something.mp3` containing real audio would be indexed by
Rockbox and is skipped by ddm. This is accepted: the name is reserved by the AppleDouble
format, and no tagger or ripper produces it.

**Fix applied:** added a single `is_excluded_name(name)` predicate to `file_scanner.py`,
returning True for `._*` and `__MACOSX`. Applied at all four selection sites —
`scan_directory`'s entry loop (which now also refuses to *descend* into `__MACOSX`),
`add_file`, and `add_files`. One definition, one place to test.

The predicate is **name-based and not guarded by `sys.platform`**, deliberately. These
files originate on macOS but travel with the volume, so a Linux or Windows host indexing
the same media encounters them identically. A platform guard would leave the behaviour
broken for precisely the users who did not create the files.

**Verified:** a full `ddm generate` over a 17,139-track library on an exFAT volume
scanned **17,139 files with 0 failed**.

---

## 5. Summary

| Category | Count | Notes |
|---|---|---|
| ✅ Implemented | 5 API + 9 format items | build/update/rebuild core + full binary layout |
| ❌ Missing | 2 | `create_changelog` (in scope), `import_changelog` (device-side upstream) |
| ⚠️ Divergent | 1 | exotic codecs (won't-fix) |
| ✅ Fixed this pass | 3 | `grouping` on MP4/ASF, default `grouping` mapping, AppleDouble filtering (divergence) |
| ⊘ N/A (device-only) | 27 | search ×9, numeric edits ×3, lifecycle ×12, ramcache ×3, `tagtree.c` |

## 6. End-to-End Verification (2026-09-07)

Generated against a mounted exFAT volume holding a 17,139-track library, **read-only** —
output written to a temp directory outside the volume; a directory listing of the music
root hashed identical before and after, and zero sidecars were created.

```
ddm generate --music-dir <volume>/Music \
             --output <tmpdir> \
             --dap-root <volume>
```

| Check | Result |
|---|---|
| Files scanned | 17,139 — **0 failed** |
| Wall time | 58.8 s |
| Files written | 11 (`database_{0,1,2,3,4,5,6,7,8,12}.tcd` + `database_idx.tcd`) |
| `ddm validate` | **Passed** — all files present, loads, no orphaned references |
| Master header magic | `1048 4354` LE = `0x54434810` ✅ |
| `entry_count` | `0x42F3` = 17,139 ✅ |
| Path cross-compilation | `/<HDD0>/Music/…`; **0** paths retaining the host mount prefix ✅ |
| `grouping` (tag 8) | 3,107 entries incl. values read from native `©grp` ✅ |
| Test suite | 542 passed, 23 skipped, 0 correctness failures |

The 2 remaining failures are in `test_performance_regression.py` — machine-dependent
comparisons against `.performance_baselines.json`, pre-existing and unrelated. Baselines
need re-recording on this machine (separate task).

### Observation: generation is not byte-reproducible

Two `generate` runs over an unchanged library, with **identical code**, produce
byte-different `database_3.tcd`, `database_4.tcd` and `database_idx.tcd`. The *content*
is equivalent — identical file sizes and identical sorted string sets (`diff` of sorted
`strings` output returns zero lines) — only the on-disk ordering varies, presumably from
parallel batch completion order.

This is **pre-existing and not caused by any change in this pass** (verified by running
the same build twice). `ddm validate` passes on each run, so the databases are
functionally valid. It does mean `.tcd` output cannot be checksum-compared between runs
to detect drift, which is worth knowing before anyone builds a "has the DB changed?"
check on hashes. Not filed as a defect; recorded so the next audit doesn't mistake it
for one.

**Bottom line:** the on-disk format is at exact parity and the generation pipeline
covers everything upstream's PCTOOL build does, with one exception —
`tagcache_create_changelog`. The two correctness defects found in this pass have been
fixed and verified end-to-end. The remaining work is:

1. **`create_changelog` export** — the genuine feature gap; requires `FLAG_DIRTYNUM` to
   be tracked for the output to be non-empty.
2. **Exotic codecs** — won't-fix; mutagen has no taggers.

Import (`tagcache_import_changelog`) additionally needs a `find_index()` equivalent —
a filename→index lookup over `database_4.tcd` — which ddm does not currently expose.
Note that upstream excludes import from PCTOOL builds, so this is optional for parity.
