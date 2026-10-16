# Chapter 3 — The Database Engine

> **Who this is for:** you've read Chapter 0 (Python basics, including the
> `struct`/binary-file-I/O teaser and the `multiprocessing.Pool` example) and
> Chapter 1 (the architecture map — you know `database/` is "the core" and
> roughly what each file in it is for). This chapter does **not** re-teach
> variables, functions, classes, or basic `struct` usage. It teaches
> everything *new* that shows up in the real code: memory layouts, worker
> pools, `__slots__`, `bisect`, platform branching, and a genuinely clever
> rename-detection algorithm.
>
> **How to use it:** this is the single most important chapter in the whole
> series. The `database/` package *is* the product — everything else (CLI,
> tagging, config) exists to feed data into it or read data out of it. Go
> slowly. Run the test suites mentioned at the end as you go.

---

## 3.1 What is a "tag cache" database, conceptually?

Rockbox is open-source firmware that runs on dedicated music players (iPods,
Sansas, and similar hardware — collectively "DAPs", Digital Audio Players, in
this project's vocabulary). A DAP might have 50,000 songs on it. If Rockbox
had to open every single MP3/FLAC/OGG file and re-read its ID3/Vorbis tags
every time you wanted to browse "all albums by Artist X," the UI would be
unusably slow — these are underpowered embedded devices, not laptops.

So Rockbox pre-computes an index once and stores it as a handful of small
binary files on the device, collectively called the **tag cache** (hence the
`.tcd` extension — **T**ag **C**ache **D**atabase). Browsing the menu then
means reading small, already-sorted binary records instead of re-parsing
audio files. This project (DAP DB Manager) is a *desktop* tool that builds
those exact files faster and more reliably than running Rockbox's own
on-device database build (which can take hours on a large library).

### The two kinds of file

The tag cache is split into two kinds of binary file, both written to a
`.rockbox` folder on the device:

1. **Tag files** (`database_0.tcd` through `database_8.tcd`, plus
   `database_12.tcd`) — one per text field: artist, album, genre, title,
   filename/path, composer, comment, album artist, grouping, and
   canonical-artist. Each tag file is essentially "the deduplicated list of
   every distinct *string* value that appears for this field," e.g.
   `database_0.tcd` holds every unique artist name exactly once, no matter how
   many songs share that artist.
2. **The index file** (`database_idx.tcd`) — one row *per song*. Each row
   doesn't repeat the artist/album/genre text; it stores small integer
   **offsets** pointing back into the tag files, plus small numeric fields
   that don't need deduplicating (track number, play count, rating, file
   modification time, …).

This is a classic normalization trick, the same idea as a relational
database's foreign key: instead of storing the string `"Radiohead"` 9 times
for 9 songs, you store it once in `database_0.tcd` and the 9 index rows each
store a 4-byte number saying "my artist is the one at byte offset 1234 of
that file." Smaller files, faster to scan, faster to sort.

Every file in this family starts with a small fixed-size **header**
(magic number + size + count, roughly) followed by a sequence of
fixed/variable-size **records**. The rest of this chapter is about exactly
how those bytes are produced and consumed — and about the Python machinery
around that process (parallel workers, caching, rename detection) that makes
rebuilding this from scratch on a modern desktop fast enough to be pleasant.

---

## 3.2 Binary I/O: `tagfile.py` and `indexfile.py` (fed through `database/io.py`)

`database/io.py` is the *orchestrator* for reading/writing the whole
database — it loops over the ten tag fields and the index, and delegates the
actual byte-level work to two other modules: `tagging/tag/tagfile.py`
(`TagFile`/`TagEntry`) and `indexfile.py` (`IndexFile`/`IndexEntry`). We'll
look at all three together, since that's the only way the binary format
actually makes sense.

### 3.2.1 `struct` format strings, properly explained

Chapter 0 showed you `struct.unpack(">I", data)` — one unsigned 32-bit
integer, **big-endian** (`>`). The real code looks like this:

```python
# tagfile.py, TagFile.to_file
f.write(struct.pack("III", self.magic, self.size, self.count))
```

```python
# tagfile.py, TagEntry.to_file
f.write(struct.pack("II", self.length, self.index))
```

```python
# indexfile.py, IndexFile.to_file
f.write(
    struct.pack(
        "IIIIII",
        self.magic, self.size, self.count,
        self.serial, self.commitid, self.dirty,
    )
)
```

New things to notice versus Chapter 0's example:

- **No `>` or `<` prefix.** Chapter 0's example explicitly chose big-endian
  byte order. Here there's *no* order character at all, which means
  **native byte order, native size, native alignment** — whatever the CPU
  running Python natively uses. On essentially every machine this code runs
  on (x86-64, Apple Silicon), that's **little-endian**, which is also what
  Rockbox (running on little-endian ARM/MIPS DAP hardware) expects. This
  only works because both sides happen to agree on little-endian — it's an
  implicit assumption baked into the file format, not something negotiated
  at read time. (If you ever see mysterious corruption after a "port this to
  a big-endian platform" change, this line is where to look first.)
- **The letter repeated N times** (`"III"`, `"IIIIII"`) just means "N
  unsigned 32-bit integers back to back," rather than spelling out
  `"I" * 3`. `struct.pack` always returns one `bytes` object; `struct.unpack`
  always returns a `tuple`, one element per format character — which is why
  you constantly see it unpacked straight into multiple variables:

  ```python
  # indexfile.py, IndexFile.from_file
  index.magic, size, count, index.serial, index.commitid, index.dirty = (
      struct.unpack("IIIIII", f.read(4 * 6))
  )
  ```

  Six format characters in, six values out, assigned left-to-right by tuple
  unpacking (Chapter 0 §0.3 covered multiple assignment; this is that same
  mechanism, just with six names instead of two).
- `4 * 6` instead of `24` — deliberately written as "4 bytes per uint32,
  times 6 fields" so the *meaning* of the number is visible in the code, not
  just its value. You'll see this pattern (`4 * N`) throughout both files.

### 3.2.2 The tag file format: header + a list of length-prefixed strings

```python
# tagfile.py
def to_file(self, f):
    self.offsets.clear()
    f.write(struct.pack("III", self.magic, self.size, self.count))
    for entry in self.entries:
        self.offsets[f.tell()] = entry
        entry.to_file(f)
```

`f.tell()` returns the file's current byte position — "how many bytes have I
written so far?" It's called *before* writing each entry, so
`self.offsets[position] = entry` records "this TagEntry starts at exactly
this byte offset." That dictionary is exactly how the `database_idx.tcd`
file can later say "the artist for this song is at offset 1234" — those
offsets are generated here, at write time, and stored in-memory for the
index writer to use a moment later (see `DatabaseIO.write`, which always
writes tag files *before* the index file specifically because the index
needs these offsets to exist first).

Each `TagEntry` then writes itself:

```python
# tagfile.py, TagEntry
def to_file(self, f):
    self.offset = f.tell()
    f.write(struct.pack("II", self.length, self.index))
    f.write(self.raw_data)
```

So one entry on disk is: `[length: u32][index: u32][raw string bytes...]`.
`length` is the entry's own byte count (so a reader knows how many bytes to
read next without needing a terminator scan), and `index` is an internal
bookkeeping number (defaults to `0xFFFFFFFF`, i.e. "unset", via a property —
notice `__get_index` returns that sentinel instead of `None`, because this
value has to round-trip through `struct.pack("I", ...)`, and `struct` cannot
pack `None` into an unsigned int).

The raw bytes themselves come from a property with padding logic:

```python
def __get_raw_data(self):
    return (self.__data + b"\x00").ljust(self.length, b"X")
```

This appends a single NUL byte (`\x00`, "the C string terminator") after the
UTF-8-encoded text, then **left-justifies** (pads on the right) with the
byte `X` up to `self.length`. Why pad with `b"X"` and not more NULs? Because
`length` itself isn't just "however many bytes this string needs" — for
every tag file *except* the path file, Rockbox requires each entry's length
to be a multiple of 8 bytes (presumably for cheap pointer alignment on the
embedded target):

```python
@property
def length(self):
    if self.is_path:
        return len(self.__data) + 1
    else:
        data_len = len(self.__data) + 1
        return ((data_len + 7) // 8) * 8
```

`((data_len + 7) // 8) * 8` is the standard "round up to the next multiple of
8" integer trick: adding 7 before floor-dividing by 8 means any remainder
pushes you into the next multiple (e.g. `data_len=10` → `(10+7)//8=2` →
`2*8=16`); an already-aligned size doesn't move (`data_len=16` →
`(16+7)//8=2` → `16`). This is exactly the kind of bit-twiddling you'll see
scattered through binary file formats — worth internalizing, since you'll
hit this pattern again in other codebases.

Reading an entry back reverses the write exactly:

```python
# tagfile.py, TagEntry.from_file
@staticmethod
def from_file(f, is_path=False):
    offset_before = f.tell()
    length, index = struct.unpack("II", f.read(4 * 2))
    entry = TagEntry()
    entry.offset = offset_before
    entry.raw_data = f.read(length)
    entry.index = index
    entry.is_path = is_path
    return entry
```

`f.read(length)` reads *exactly* `length` bytes — this only works because
the writer stored that exact count up front; there's no delimiter to scan
for. `entry.raw_data = ...` runs the setter, which strips the padding back
off:

```python
def __set_raw_data(self, raw_data):
    self.__data_bytes = raw_data.partition(b"\x00")[0]
```

`bytes.partition(sep)` splits into `(before, sep, after)` at the *first*
occurrence of `sep` and returns a 3-tuple; `[0]` keeps only the "before"
part. So reading `b"Radiohead\x00XXXXXX"` back gives `b"Radiohead"` — the
NUL terminator and the `X` padding are both discarded, because the NUL marks
"this is where the real string data actually ended," regardless of how much
trailing padding follows it.

The whole-file reader at the top level mirrors `to_file`:

```python
# tagfile.py, TagFile.from_file
header = f.read(4 * 3)
magic, size, entry_count = struct.unpack("III", header)
...
for i in range(entry_count):
    offset = f.tell()
    entry = TagEntry.from_file(f, is_path)
    tf.offsets[offset] = entry
    tf.append(entry)
```

Read the 12-byte header, unpack three integers, then loop `entry_count`
times — the header told you exactly how many entries to expect, so there's
no need to read "until end of file." This is a recurring theme in custom
binary formats: **counts and lengths are stored explicitly up front so the
reader never has to guess.** It also means a truncated/corrupted file is
caught quickly (`if len(header) < 12: raise EOFError(...)`) rather than
silently reading garbage.

### 3.2.3 Why `TagFile`/`TagEntry` use `__slots__`

```python
class TagFile:
    __slots__ = (
        "magic", "entrydict", "entries", "offsets",
        "_index_by_sort", "_is_sorted",
    )
```

```python
class TagEntry:
    __slots__ = (
        "_TagEntry__data_str", "_TagEntry__data_bytes", "_TagEntry__sort",
        "is_path", "index_entries", "_TagEntry__index", "offset",
    )
```

**This is new**, so here's the full explanation. Normally, every Python
object keeps its attributes in a hidden dictionary (`obj.__dict__`) — that's
what lets you do `obj.whatever = 123` on *any* object at any time, even
attributes the class never declared. That flexibility costs memory: every
plain object carries around a dict (tens of bytes of overhead minimum, more
once it actually holds entries) purely so arbitrary attributes *could* be
added.

`__slots__` is a class-level declaration that says "instances of this class
will *only* ever have exactly these named attributes — don't allocate a
`__dict__` at all, use a fixed-size internal C array instead." Trade-offs:

- ✅ Much less memory per instance (no `__dict__` overhead), and slightly
  faster attribute access (direct slot lookup instead of a dict lookup).
- ❌ You cannot set any attribute not listed in `__slots__` — `entry.foo = 1`
  raises `AttributeError` if `"foo"` isn't declared.

Why it matters *here specifically*: a real music library can have 50,000+
songs, each needing a `TagEntry`, and ~10 tag files' worth of entries in
total (one `TagEntry` per unique artist, per unique album, per unique title,
etc.) — potentially hundreds of thousands of small objects alive in memory
at once during a full database generation. Shaving even 50–100 bytes off
each one adds up to tens of megabytes, which matters when this whole
pipeline is explicitly designed to be memory-conscious (see §3.5's tag
cache, which has its own megabyte budget).

Notice the odd-looking slot names like `"_TagEntry__data_str"` — that's
Python's **name mangling**. Any attribute written as `self.__data_str`
inside a class body (two leading underscores, at most one trailing) is
automatically rewritten by the interpreter to
`self._ClassName__data_str`, to avoid accidental collisions if a subclass
declares its own "private" `__data_str`. `__slots__` has to list the
*mangled* name, because that's the actual attribute name Python will try to
store. You don't need to use this convention yourself to understand it, just
recognize it when you see leading double-underscore attributes.

### 3.2.4 The index file: no strings at all, just numbers and offsets

```python
# indexfile.py, IndexEntry.to_file
def to_file(self, f):
    for field in FILE_TAGS:
        tagentry = self[field]
        assert isinstance(tagentry, TagEntry) and tagentry.offset is not None
        f.write(struct.pack("I", tagentry.offset))

    for field in EMBEDDED_TAGS:
        value = self[field]
        if field == "mtime":
            value = mtime_to_fat(value)
        f.write(struct.pack("I", value))
```

Every index row is **pure numbers**: for each text field (artist, album,
genre, …) it writes the *byte offset* of that field's `TagEntry` inside its
tag file (the offsets recorded back in §3.2.2!); for each "embedded" numeric
field (track number, play count, rating, bitrate, `mtime`, flags, …) it
writes the raw value. This is the normalization trick from §3.1 made
concrete: an index row never repeats "Radiohead", it repeats a 4-byte
pointer into `database_0.tcd`.

One detail worth a second look: `mtime_to_fat(value)`. Rockbox's underlying
filesystem convention (FAT) stores modification times in a packed,
non-Unix format, so the in-memory Python value (an ordinary Unix timestamp)
has to be converted at the exact moment it's serialized to disk — and
converted back (`fat_to_mtime`) when reading:

```python
# indexfile.py, IndexEntry.from_file
for field in EMBEDDED_TAGS:
    index_entry[field] = struct.unpack("I", f.read(4))[0]
index_entry.mtime = fat_to_mtime(index_entry.mtime)
```

The project's own code comments (in `generator.py`) explicitly warn about a
real historical bug here: converting at the wrong layer (e.g. doing the FAT
conversion in memory instead of only at the file I/O boundary) silently
double-encodes the value and corrupts every timestamp comparison downstream.
That's a good first example of why binary formats deserve defensive
comments: a format conversion done in the wrong place is invisible until
something that depends on exact values (rename detection, in §3.6) starts
failing in a way that's hard to trace back to "oh, the number itself was
wrong."

Also notice `IndexEntry(dict)` — it's literally a subclass of the built-in
`dict`, with `__getattr__`/`__setattr__` overridden so `entry.playcount` and
`entry["playcount"]` are the same thing:

```python
class IndexEntry(dict):
    def __getattr__(self, name):
        return self[name]
    def __setattr__(self, name, value):
        self[name] = value
```

This is a small, elegant trick: you get dict's existing machinery (`.get()`,
`in`, iteration, `.copy()`) for free, plus attribute-style access as a
convenience layer on top, by overriding just two dunder methods.

### 3.2.5 `database/io.py`: writing files in parallel with `ThreadPoolExecutor`

`database/io.py` itself contains no `struct` calls — its job is purely
orchestration: loop over the ten tag fields plus the index, call
`.write()`/`.read()` on each, and optionally parallelize the writes:

```python
# database/io.py, _write_parallel
def write_file(field: str, file_num: int) -> tuple:
    filename = out_path / f"database_{file_num}.tcd"
    tagfiles[field].write(str(filename), buffer_size=cls.BUFFER_SIZE)
    return (filename, field)

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {}
    for i, field in enumerate(FILE_TAGS):
        file_num = FILE_TAG_INDICES[i]
        future = executor.submit(write_file, field, file_num)
        futures[future] = field

    for future in as_completed(futures):
        filename, field = future.result()
        with callback_lock:
            callback(f"Writing {filename} . . . done")
```

`ThreadPoolExecutor` is in the standard library's `concurrent.futures`
module — it's a *higher-level* cousin of the raw `multiprocessing.Pool` you
saw in Chapter 0. New vocabulary:

- `executor.submit(fn, *args)` schedules `fn(*args)` to run on a worker and
  immediately returns a **`Future`** object — a placeholder for "the result,
  whenever it's ready." It does *not* block.
- `futures[future] = field` — using the `Future` itself as a dict key. This
  works because `Future` objects are hashable, and it's a common pattern:
  "remember which input produced this still-pending output" so that once it
  completes you can report back which file/field it was for.
- `as_completed(futures)` is a generator (see Chapter 0 §0.11) that yields
  each `Future` **as soon as it finishes**, in completion order — not
  submission order. That's why the loop can't just assume "first submitted,
  first returned"; it has to ask each completed future which field it was
  (`futures[future]`).
- `future.result()` blocks (if needed) until that specific future is done,
  then returns whatever `write_file` returned (or re-raises its exception).
- `with ThreadPoolExecutor(...) as executor:` — a context manager (Chapter 0
  §0.10). On exiting the `with` block, the executor automatically waits for
  all submitted work to finish and releases its worker threads. You don't
  have to call `.shutdown()` yourself.
- `Lock()` from the `threading` module, used here as `callback_lock`: since
  multiple threads can finish and call `callback(...)` "simultaneously"
  (well — interleaved, since this is *threads*, where the GIL still applies;
  more on that distinction in §3.3), the lock ensures only one thread prints
  a progress line at a time, so output doesn't get garbled mid-line.

Notice this uses **threads**, not **processes**, even though Chapter 0 told
you threads don't help with CPU-bound work. That's deliberate: writing bytes
to disk is **I/O-bound** (the CPU is mostly waiting on the operating system
and the disk, not computing), and I/O-bound work is exactly where threads
*do* help, because while one thread is blocked waiting on `write()`, another
thread can run. The GIL only blocks *CPU* work from overlapping; it doesn't
block I/O waits from overlapping. Compare this to the next section, where
CPU-bound formatting work deliberately uses *processes* instead.

---

## 3.3 `generator.py`: building the whole database, and why it uses processes

### 3.3.1 The job: cached tags → formatted, deduplicated, sorted entries

`DatabaseGenerator.generate()` is the method that turns "a set of file
paths whose tags are already sitting in the tag cache" (§3.5) into a
populated `IndexFile` plus ten populated `TagFile`s. Conceptually, for every
song it has to:

1. Apply the user's **title-format** strings (e.g. `%artist%` or
   `$if2(%albumartist%,%artist%)`) to that song's raw tags, producing the
   actual string that will be stored for each field.
2. Deduplicate: if "Radiohead" already exists as a `TagEntry` in the artist
   tag file, reuse it; otherwise create a new one.
3. Assemble one `IndexEntry` per song, pointing at the right `TagEntry` for
   each field.

Step 1 — running the formatting logic — is genuinely CPU-intensive (it's
basically interpreting a small expression language, per song, per field),
and that's the part this module parallelizes.

### 3.3.2 Why `ProcessPoolExecutor` instead of `ThreadPoolExecutor`

```python
# generator.py, DatabaseGenerator.__init__
# Using ProcessPoolExecutor to bypass GIL for CPU-intensive string formatting
self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
```

Tying this back to Chapter 0 §0.14 directly: the **GIL** (Global Interpreter
Lock) means that, inside a single Python process, only one thread can be
executing Python bytecode at any instant — even on an 8-core machine, 8
Python *threads* doing CPU-bound work will not run meaningfully faster than
1 thread, because they're all fighting over the same lock. Title-format
evaluation (string parsing, conditional logic, numeric parsing per tag) is
exactly that kind of CPU-bound work.

`ProcessPoolExecutor` sidesteps this entirely by using **separate operating
system processes** instead of threads. Each process gets its *own* Python
interpreter, its own GIL, its own memory space — so N processes really can
use N CPU cores simultaneously. The cost: processes can't share memory
directly, so every piece of work handed to a worker, and every result handed
back, has to be **pickled** (serialized to bytes), sent across an OS pipe,
and **unpickled** on the other side. That overhead is why this code
processes work in **batches** rather than one song at a time — the fixed
per-call overhead of crossing the process boundary would dominate if you
paid it per song.

### 3.3.3 The worker function: must be a plain, top-level function

```python
def process_batch_task(
    entries_data: List[Dict[str, Any]],
    format_strings: Dict[str, Tuple[str, Optional[str]]],
    multiple_fields_config: List[str],
) -> List[Dict[str, Any]]:
    """Worker function to process a batch of entries in a separate process."""
    try:
        from ..tagging import titleformat
    except ImportError:
        return []

    global _worker_format_cache, _worker_cache_key
    cache_key = (
        frozenset(format_strings.items()),
        tuple(sorted(multiple_fields_config)),
    )

    if _worker_cache_key != cache_key:
        compiled_formats = {}
        ...
        _worker_format_cache = (compiled_formats, multiple_fields_map)
        _worker_cache_key = cache_key
    else:
        compiled_formats, multiple_fields_map = _worker_format_cache
    ...
```

Why is this a module-level function rather than a method on
`DatabaseGenerator`? Because `multiprocessing` (which `ProcessPoolExecutor`
uses under the hood) needs to **pickle** the function reference itself to
tell a worker process what to run. Plain top-level functions pickle cleanly
(by name + module path); bound methods, closures, and lambdas generally
don't (or pickle in surprising, fragile ways). This is a very common gotcha
the first time you use multiprocessing in Python — if your worker function
is "can't be pickled," moving it to module scope is usually the fix.

The `global _worker_format_cache, _worker_cache_key` lines are new too.
Normally assigning to a name inside a function creates a *local* variable;
`global` tells Python "no, I mean the module-level variable of that name."
Why cache here at all? Because **each worker process persists across
multiple batches** (a `ProcessPoolExecutor` reuses its worker processes
rather than spawning a fresh one per task), but a worker process starts with
*nothing* — none of the state from the main process. The very first batch a
given worker handles has to compile the title-format strings from scratch;
every subsequent batch *in that same worker process* can reuse the already-
compiled version instead of recompiling, as long as the format configuration
hasn't changed (`cache_key` captures exactly that configuration, including
a `frozenset` — an immutable, hashable set — of the format strings, so it
can be used as a comparison key).

This is conceptually the same instinct as `functools.lru_cache` ("remember
expensive results keyed by input, so you don't redo the work"), just
implemented by hand with plain module-level variables, because what needs
caching here is per-*process* state (compiled format objects) rather than a
simple function result.

### 3.3.4 The sliding window: submitting work without stalling

```python
# generator.py, _generate_parallel
max_futures_in_flight = self.max_workers * 2
futures = {}
batch_index = 0
total_batches = (total_paths + batch_size - 1) // batch_size

def submit_batch(batch_start):
    ...
    if batch_data:
        future = self._executor.submit(
            process_batch_task, batch_data, format_strings, multiple_fields_list
        )
        return future, len(batch_data)
    return None, 0

while batch_index < min(max_futures_in_flight, total_batches):
    future, count = submit_batch(batch_index * batch_size)
    if future:
        futures[future] = count
    batch_index += 1

while futures:
    for future in as_completed(futures):
        try:
            results = future.result()
            for result in results:
                self._assemble_entry(result, tagfiles, index, multiple_fields)
            processed += len(results)
            if callback:
                callback(processed, total_paths)
        except Exception as e:
            logging.error("Batch processing failed: %s", e)
        finally:
            del futures[future]
            if batch_index < total_batches:
                new_future, count = submit_batch(batch_index * batch_size)
                if new_future:
                    futures[new_future] = count
                batch_index += 1
            break
```

The pattern: don't submit *all* batches up front (that could queue
thousands of large pickled payloads in memory before any worker even starts
on them), and don't submit one-at-a-time-and-wait (that would leave workers
idle between batches). Instead, keep a **sliding window** of at most
`max_workers * 2` batches "in flight" at once: submit that many up front,
then every time one finishes, immediately submit exactly one more to
replace it, keeping the pipeline full. The `break` at the end of the `for`
loop is intentional and important: `as_completed` is iterating over a
dictionary that the code is mutating (`del futures[future]`, then possibly
adding a new one) *while inside the loop* — `break` forces the loop to
restart `as_completed()` against the now-updated `futures` dict on the next
pass of the outer `while futures:` loop, rather than continuing to iterate
over a collection that's shifting underneath it.

Note too: `_assemble_entry` (building the actual `IndexEntry`/`TagEntry`
objects and appending them to the shared tag files and index) runs back on
the **main process**, never inside a worker. Only the CPU-heavy formatting
is parallelized; the actual mutation of shared data structures stays
single-threaded, sidestepping any need for locks around `tagfiles`/`index`.

### 3.3.5 Deduplication, in the assembly step

```python
# generator.py, _assemble_entry
try:
    tagentry = tagfiles[field][val]
except KeyError:
    tagentry = TagEntry(val, sort)
    tagfiles[field].append_sorted(tagentry)
entry[field] = tagentry
```

`tagfiles[field][val]` uses `TagFile.__getitem__`, which looks `val` up in
`self.entrydict` (a plain dict from string value → `TagEntry`) — this is the
deduplication from §3.3.1 step 2 in one line: if this exact artist string
has already been turned into a `TagEntry` for some earlier song, reuse the
same object; only create a new `TagEntry` the first time a given value is
seen.

One more piece of new vocabulary here: `itertools.product`, used to handle
fields that can hold *multiple* values (multi-genre or multi-artist tags —
"Rock; Alternative" needs to become two separate `TagEntry` rows that both
point back at this song):

```python
combinations = []
for field, tagentries in multiple_tags_entries.items():
    combinations.append([(field, tagentry) for tagentry in tagentries])

for fields in product(*combinations):
    index_entry = entry.copy()
    for field, value in fields:
        ...
    index.append(index_entry)
```

`itertools.product(*combinations)` computes the **Cartesian product** — every
possible combination of one item from each input list. If a song has 2
genres and 2 artists, this produces `2 × 2 = 4` combinations, and the code
creates one full copy of the index entry per combination (`entry.copy()`),
so a multi-valued song can correctly show up under every relevant
browsing path without duplicating all its other fields by hand.

---

## 3.4 `file_scanner.py`: finding music files without blowing up memory

### 3.4.1 Discovering files: `os.scandir`, not `os.walk` or `.rglob()`

Chapter 0 showed `Path.glob()` for simple file-finding. The real scanner
uses a lower-level, faster primitive — `os.scandir` — and implements its own
recursion by hand:

```python
# file_scanner.py, scan_dir_metadata
def scan_directory(dir_path: str) -> None:
    try:
        with os.scandir(dir_path) as entries:
            dirs_to_scan = []
            for entry in entries:
                try:
                    if is_excluded_name(entry.name):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        dirs_to_scan.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        if Path(entry.name).suffix.lower() in self.supported_extensions:
                            stat_info = entry.stat(follow_symlinks=False)
                            abs_path = unicodedata.normalize(
                                "NFC", str(Path(entry.path).absolute())
                            )
                            metadata[abs_path] = (
                                stat_info.st_size,
                                stat_info.st_mtime,
                            )
                except OSError:
                    continue

            if recursive:
                for subdir in sorted(dirs_to_scan):
                    dircallback(subdir)
                    scan_directory(subdir)
    except OSError as e:
        logging.warning("Cannot access directory %s: %s", dir_path, e)
```

`os.scandir()` is a context manager (the `with` here) that yields
lightweight `DirEntry` objects one at a time, each of which already knows
whether it's a file or directory *without an extra system call* in the
common case — `entry.is_dir()`/`entry.is_file()` reuse information the OS
already returned while listing the directory. `Path.glob()`/`os.walk()`
(which you may see mentioned elsewhere) are built on top of similar
primitives but add overhead this hot path wants to avoid — scanning tens of
thousands of files is squarely a "every microsecond per file adds up"
situation.

The recursion is plain **function recursion**, not a generator: `scan_directory`
calls itself on every subdirectory it finds, and all the results accumulate
into one shared `metadata` dict (closed over from the enclosing function —
this is the same closure mechanism Chapter 0 implied when it showed nested
functions, just put to direct use: `scan_directory` reads and writes
`metadata` from its enclosing scope without it being passed as a parameter).

`follow_symlinks=False` is a deliberate safety choice — it stops the scanner
from checking what a symlink *points to*, avoiding both infinite loops
(a symlink pointing into its own ancestor directory) and following links
outside the intended music folder.

`unicodedata.normalize("NFC", ...)` is worth pausing on, since it's a real,
documented gotcha in this codebase: macOS's filesystem APIs hand back
**decomposed** Unicode (NFD — e.g. `é` as the two codepoints `e` + combining
acute accent) for any path it reads off a FAT/exFAT volume, regardless of
how the bytes are actually stored on disk. Rockbox's own on-device code
compares paths byte-for-byte assuming **precomposed** form (NFC — `é` as one
single codepoint). If this code didn't normalize to NFC right here, a
filename with an accented character would scan and tag correctly on a Mac,
get written into the database in the "wrong" Unicode form, and then
silently fail to open when Rockbox later tried to match it to the file on
the device. The comment block above this code (`_add_file_internal`) spells
this out in more detail — it's a good example of a bug that's invisible
unless you know exactly how two different pieces of software each encode
the "same" string differently.

### 3.4.2 Reading tags in parallel — the same `ProcessPoolExecutor` pattern again

```python
def read_single_file_tags(path: str) -> Tuple[str, Optional[int], Optional[int], Optional[Any]]:
    """Read tags from a single file (standalone function for multiprocessing)."""
    try:
        try:
            from dap_db_manager import tagging
        except ImportError:
            return (path, None, None, None)

        path_obj = Path(path)
        stat = path_obj.stat()
        size, mtime = stat.st_size, int(stat.st_mtime)

        lowerpath = path.lower()
        if TagCache.contains(lowerpath):
            cached_size, cached_mtime = TagCache.get(lowerpath)[0]
            if mtime == cached_mtime and size == cached_size:
                cached_tags = TagCache.get(lowerpath)[1]
                return (path, size, mtime, cached_tags)

        tags = tagging.read(path)
        if tags is None:
            return (path, None, None, None)
        return (path, size, mtime, tags)
    except Exception as e:
        logging.debug("Error reading tags from %s: %s", path, e)
        return (path, None, None, None)
```

Same reasoning as §3.3.2: actually parsing an MP3/FLAC file's tag frames is
CPU work (decoding frame headers, decompressing text encodings), so this
too is a module-level function handed to a `ProcessPoolExecutor`:

```python
# file_scanner.py, read_tags_batch
futures = {
    self._executor.submit(read_single_file_tags, path): path
    for path in file_paths
}
for future in as_completed(futures):
    try:
        result = future.result()
        results.append(result)
    except Exception as e:
        path = futures[future]
        logging.error("Error processing %s: %s", path, e)
        results.append((path, None, None, None))
```

`futures = {...}` here is a **dict comprehension** (briefly introduced in
Chapter 0 §0.11) — build the whole "future → path" mapping in one
expression instead of a manual loop with `.update()`/`[] = `.

Notice the cache check happens **inside the worker function**, i.e. inside
the *child* process, not the parent. This matters, and the comment right
above the code block calls it out: "Note: Cache access from worker
processes — they get a copy of the cache." Because the worker runs in a
separate OS process, it does not share the parent's live `TagCache` object
in memory — when a worker process is spawned, the data it needs gets
pickled across the process boundary, so each worker effectively works with
its own snapshot. That's fine here because cache *reads* just check "is this
unchanged since last time," and the result is handed back to the parent to
decide what to do with — but it's an important mental model to carry
forward: **mutating shared global state inside a `ProcessPoolExecutor`
worker does not propagate back to the parent process automatically.**

### 3.4.3 Why discovery and tag-reading are separate passes

Notice `scan_dir_metadata` (cheap: just `os.stat` — size/mtime) is a
completely separate pass from `add_files`/`read_tags_batch` (expensive: full
tag parsing). This two-phase design shows up explicitly in
`Database.update_database` (Chapter 1's architecture tour mentioned this):
Phase 1 does a fast metadata-only scan to figure out *which* files are new,
changed, or gone; only Phase 2 pays the real cost of parsing tags, and only
for files that Phase 1 determined actually need it. This is a general
lesson worth carrying forward: when an expensive operation (tag parsing)
can be skipped for most inputs based on a cheap check (file size + mtime
compared to a cache), always do the cheap check first, in bulk, before
touching the expensive path at all.

---

## 3.5 `cache.py`: the `TagCache` — what's cached, and why "caching" matters

### 3.5.1 The general idea of caching

A **cache** is a place to store the *result* of an expensive computation so
that, the next time you need that same result, you can retrieve it instead
of recomputing it. The trade-off is always memory (or disk) space traded for
time. Caching is only a net win if: (a) the same input is likely to be
needed again, and (b) storing the result is cheaper than recomputing it. Both
hold strongly here: reading and parsing an audio file's tags (decompressing
ID3 frames, decoding text encodings) is far slower than comparing two small
numbers (file size, modification time).

### 3.5.2 What's actually stored

```python
TagCache._cache: OrderedDict[str, bytes]
```

Keyed by **lowercased absolute file path**, each value is
`((size, mtime), tags)` — the file's size and modification time at the
moment it was last read, paired with a minimal dictionary of just the tag
fields this project actually needs (`extract_essential_tags`):

```python
essential_fields = [
    "artist", "album", "genre", "title", "composer", "comment",
    "grouping", "date", "discnumber", "tracknumber", "bitrate",
    "length", "path", "albumartist", "performer",
]
```

The docstring is explicit about the payoff: "reduces pickle size dramatically
(from ~117KB to ~1KB per file)." A full `mutagen` tag object (the library
that actually parses the audio file formats) carries a lot of internal
structure the database doesn't need; keeping only what's needed matters both
for raw memory (this cache can hold tens of thousands of entries) and for
pickling cost, since — as you now know from §3.3/§3.4 — any data that
crosses a process boundary has to be pickled, and smaller objects pickle (and
unpickle) faster.

### 3.5.3 Why `OrderedDict` specifically, and LRU eviction

```python
from collections import OrderedDict
_cache: OrderedDict[str, bytes] = OrderedDict()
```

A plain `dict` in modern Python already remembers insertion order, but
`OrderedDict` additionally provides `.move_to_end(key)` and
`.popitem(last=False)` (pop the *oldest* item) as first-class, efficient
operations — exactly the two primitives needed to implement **LRU (Least
Recently Used) eviction**:

```python
@classmethod
def get(cls, key: str, default=None):
    if key in cls._cache:
        cls._cache.move_to_end(key)   # mark as "just used"
        return cls._cache[key]
    return default
```

```python
# _check_memory_and_trim
while cls._current_memory_bytes > target_bytes and cls._cache:
    _, value = cls._cache.popitem(last=False)   # evict the LEAST recently used
    ...
```

The idea: every time an entry is read (`get`) or freshly written (`set`,
which also calls `move_to_end` elsewhere), it's moved to the *end* of the
ordering — "most recently used." When the cache grows past its memory
budget (`MAX_CACHE_MEMORY_MB`, default 512MB, tracked via
`_current_memory_bytes`, an estimate computed by actually serializing a
sample entry with `msgpack`/`pickle` and measuring its byte length), it
evicts from the *front* — the entries that haven't been touched in the
longest time — on the reasonable assumption that files you haven't looked at
recently are the least likely to be looked at again soon. This is one of the
most common caching strategies in all of software engineering (operating
system page caches, CPU caches, web caches, and database buffer pools all
use some variant of LRU), so recognizing this `OrderedDict` idiom is broadly
useful knowledge, not just a detail of this project.

### 3.5.4 Persisting the cache across runs: `save`/`load`

The in-memory cache only exists for the lifetime of one Python process. To
avoid re-reading every tag on *every single run* of the tool, `save()` and
`load()` serialize the cache to a `.gz`-compressed file on disk between
runs:

```python
# cache.py, save (msgpack path)
packer = msgpack.Packer(use_bin_type=True)
with gzip.open(path, "wb", compresslevel=6) as f:
    f.write(packer.pack(len(valid_paths)))
    for path_entry in sorted(valid_paths):
        ...
        f.write(packer.pack((path_entry, (size_mtime, essential_tags))))
```

`gzip.open(...)` is a drop-in context manager replacement for `open()` that
transparently compresses/decompresses — same `with` pattern you already
know, just backed by a compression codec instead of raw bytes.
`msgpack` (preferred when available, with a `pickle` fallback — see the
`try`/`except ImportError` at the top of the module setting `USE_MSGPACK`)
is a binary serialization format similar in spirit to JSON, but
compact and fast; it's used here purely as "a faster way to turn Python
data structures into bytes and back" than the standard library's `pickle`,
with the same two-way contract (`pack`/`unpack` mirror `pickle.dump`/
`pickle.load`).

---

## 3.6 Preserving history across a rebuild: `rename_detector.py` + `stats_preserver.py`

This is the cleverest, most interesting algorithm in the whole project, so
it's worth a careful, worked walkthrough.

### 3.6.1 The problem

When this tool rebuilds or updates the database, the *runtime statistics*
Rockbox itself has accumulated on the device — play count, star rating,
total playtime, last-played timestamp, last playback position
(`STAT_TAGS` in `stats_preserver.py`) — live only inside the *old*
`database_idx.tcd` that's about to be overwritten. A freshly-generated
database, built straight from the audio files on disk, knows nothing about
listening history — audio files don't carry that information, only the old
database does.

The naive fix — "match old and new entries by exact file path" — works for
unchanged files, but breaks the moment a file is **renamed or moved**: the
path changes, so a naive path match sees "an old entry whose path no longer
exists" (looks deleted) and "a new entry whose path didn't exist before"
(looks brand new), and the listening history for that song would silently
vanish. That's precisely the bug `rename_detector.py` exists to prevent.

### 3.6.2 The algorithm, step by step

`detect_renames()` is only ever called with the files that already look
"suspicious" after exact-path matching: paths that exist in the old
database but not on disk anymore (`paths_to_delete`), matched against paths
that exist on disk but weren't in the old database (`paths_to_add`) — see
`Database.update_database` in `database/__init__.py`. It then tries three
strategies, in order of confidence, each one catching cases the previous one
missed:

**Strategy 1 — exact metadata match (highest confidence).** Build a
**fingerprint** for each candidate: `(audio_length_ms, bitrate, mtime)`.
Crucially, note what's used and what's *not*: no path, no filename, no
artist/title — just properties of the file's actual bytes and timestamp.
If an old (now-missing) entry and a new (previously-unseen) file share the
same fingerprint *and* the same filename, that's about as strong a signal as
you can get without hashing the whole file: same audio content, same
recorded modification time, same name — almost certainly the same file,
just relocated.

```python
candidates = new_by_mtime.get(int(round(old_mtime)), [])
for new_path in candidates:
    new_filename = Path(new_path).name.lower()
    if old_filename == new_filename:
        _, new_mtime = new_file_info[new_path]
        if new_mtime and abs(old_mtime - new_mtime) <= 1:
            renames[old_path_lower] = (new_path, "exact_metadata_match")
```

Notice the performance trick: rather than comparing every deleted entry
against every new file (an `O(n × m)` nested loop that would be painfully
slow on a library with thousands of changes), the code first builds
`new_by_mtime`, a `dict[int, list[str]]` mapping "rounded modification
time" → "new file paths with that mtime" (a `defaultdict(list)` from
`collections`, which auto-creates an empty list the first time a new key is
touched, so you can `.append()` without a separate "does this key exist
yet?" check). Looking up candidates by `new_by_mtime.get(mtime)` is an
**O(1) dictionary lookup**, turning the whole first pass into roughly
`O(n + m)` instead of `O(n × m)` — a textbook example of trading a little
extra memory (the index) for a lot less time, the same trade-off that
underlies caching itself (§3.5.1), just applied to a one-off computation
instead of a long-lived cache.

**Strategy 2 — path similarity (for simple renames with no mtime match).**
Some renames *do* change the mtime (editing ID3 tags in a tag editor
typically bumps the file's modification time even though the audio and
filename are nearly identical — e.g. `01_Song.mp3` manually renamed to
`01 - Song.mp3`). For these, the code falls back to comparing how similar
the *text* of the old and new paths are:

```python
def _path_similarity(path1: str, path2: str) -> float:
    name1 = Path(path1).name.lower()
    name2 = Path(path2).name.lower()
    filename_similarity = SequenceMatcher(None, name1, name2).ratio()
    full_similarity = SequenceMatcher(None, path1.lower(), path2.lower()).ratio()
    return 0.7 * filename_similarity + 0.3 * full_similarity
```

`difflib.SequenceMatcher(None, a, b).ratio()` is a standard-library tool
that returns a similarity score between 0.0 (completely different) and 1.0
(identical), based on finding the longest matching blocks of characters
between the two strings (conceptually related to "edit distance" — how many
character insertions/deletions/substitutions would turn one string into the
other, just computed via a different, faster algorithm). The code weights
the *filename* comparison more heavily (70%) than the full path (30%),
on the theory that a file moved to a different folder (full path changes a
lot) but keeping the same filename is still very likely the same song,
while a filename that changed completely is a weaker signal even if it
happens to still be in the same folder.

To avoid `O(n × m)` again, there's a cheap **pre-filter** before running the
expensive similarity computation on every candidate:

```python
prefix = old_filename[:3].lower()
candidates = [
    p for p in new_file_info.keys()
    if p.lower() not in matched_new_paths
    and Path(p).name.lower().startswith(prefix)
]
```

Only bother computing full similarity against files whose name starts with
the same first three characters as the old one — a quick, cheap narrowing
step before the slower, more precise comparison. (The code acknowledges this
pre-filter's own weakness in a comment elsewhere in the codebase: a rename
that changes the first few characters, e.g. adding a leading accented
character, slips past this filter — which is exactly why the separate
"renormalized" path-fixing logic in `Database.update_database` exists as a
*different*, deterministic mechanism rather than relying on this fuzzy
filter to catch it.)

A match only counts if its similarity score clears
`similarity_threshold` (default `0.75`, i.e. 75% similar) **and** either the
modification times are close (`abs(old_mtime - new_mtime) <= 2` seconds) or
the similarity is very high (`>= 0.85`) regardless of mtime.

**Strategy 3 — lenient fallback.** A final, looser pass re-checks mtime
matches with only a weak path-similarity sanity check (`>= 0.3`), catching
genuine moves that strategies 1–2 missed for some reason, while still
requiring *some* textual resemblance so wildly different files that
happen to share a timestamp aren't mismatched.

### 3.6.3 Worked example

Say the old database has an entry for:

```
/Music/Radiohead/01_Paranoid_Android.mp3   mtime=1700000000   length=383000ms  bitrate=256
```

And after scanning the device, the tool finds a file it's never seen before
at:

```
/Music/Radiohead/OK Computer/01 - Paranoid Android.mp3   mtime=1700000000
```

(Same song, same audio content, same `mtime` — the user just reorganized
their folders and the filesystem preserved the modification time during the
move.) Walking through the algorithm:

1. The old entry's `fingerprint` is `(383000, 256, 1700000000)`. We don't
   have `length`/`bitrate` for the *new* file yet (tags haven't been read —
   see §3.4.3, discovery happens before tag parsing), so
   `new_by_mtime` only has `mtime` to index on.
2. **Strategy 1** looks up `new_by_mtime[1700000000]`, finds the new path,
   but compares *filenames*: `"01_paranoid_android.mp3"` vs
   `"01 - paranoid android.mp3"` — **not equal**, so strategy 1 declines
   this match (it requires exact filename equality, by design, to stay
   high-confidence).
3. **Strategy 2** computes `_path_similarity()` between the two full paths.
   The filenames are extremely close (same words, minor punctuation/spacing
   differences) — `SequenceMatcher` would score that well above `0.75`.
   Combined with the mtimes being identical (`abs(diff) <= 2` easily
   satisfied), this clears the threshold: **match found**, reason
   `"path_similarity"`.
4. `apply_renames()` then does the actual database surgery: it finds the
   *existing* `TagEntry` object for the old path and mutates its `.data`
   attribute in place (`old_path_entry.data = new_path`) rather than
   deleting it and creating a new one — crucially, this means the
   `IndexEntry` that already pointed at this exact `TagEntry` object
   (and crucially, all its other fields: play count, rating, etc.) needs
   **no other changes at all**. The entry just silently "becomes" the
   renamed file, stats intact.

```python
# rename_detector.py, apply_renames
old_path_entry.data = new_path
if old_path in path_tagfile.entrydict:
    del path_tagfile.entrydict[old_path]
path_tagfile.entrydict[new_path] = old_path_entry
```

The dict housekeeping (`del ... ; entrydict[new_path] = ...`) exists purely
to keep the path tag file's internal lookup table (`entrydict`, used for
deduplication lookups — §3.3.5) consistent with the object's new `.data`;
without it, a lookup for the new path would miss, and the deduplication
logic would create a *second*, duplicate `TagEntry` for the same path.

### 3.6.4 `stats_preserver.py`: the actual copying of history

Once `rename_detector.py` has matched up old and new *paths* for files that
moved, `stats_preserver.py` handles the simpler, more common case directly:
copying the six "stuff the user accumulated by listening" fields from an old
entry onto a new/regenerated entry that shares the *same* (normalized) path
— used both for a plain update (file untouched) and, after a full rebuild,
for every file whose path didn't change at all:

```python
STAT_TAGS = (
    "playcount", "rating", "playtime",
    "lastplayed", "lastelapsed", "lastoffset",
)

class StatsPreserver:
    def apply(self, path: str, entry) -> bool:
        key = path.lower()
        stats = self._stats.get(key)
        if stats is None:
            self.unmatched_new += 1
            return False
        for tag in STAT_TAGS:
            value = stats.get(tag)
            if value:
                entry[tag] = value
        self._claimed.add(key)
        self.matched += 1
        return True
```

Notice what's deliberately *excluded* from `STAT_TAGS` — the module's
docstring explains: `commitid` and `mtime` describe the *database* and the
*file on disk* respectively, not the user's listening history, so carrying
them forward from the old database would make the freshly-built database
lie about when it was built and when its files last changed. This is a good
general principle for any "preserve old data across a rebuild" feature:
be explicit and narrow about exactly which fields represent durable user
state versus which fields are supposed to always reflect the *current*
build, and don't let convenience blur that line.

The class also tracks its own accounting (`self.matched`,
`self.unmatched_new`, and the `unmatched_old` property) specifically so a
*partial* restore can never masquerade as a complete one — the module's own
docstring is blunt about this: *"A partial restore that looks like a
complete one is the failure mode this feature is specifically meant to
avoid, so the counts are not optional."* That's a useful piece of
engineering philosophy worth internalizing on its own: when a feature's
entire job is "silently preserve something the user cares about," make sure
failures to do so are **never silent**.

---

## 3.7 `mount_detector.py`: finding where the DAP actually is, per OS

### 3.7.1 The problem

Rockbox stores paths in the database using its own internal device notation
— `/<HDD0>/Music/Song.mp3` rather than `/Volumes/IPOD/Music/Song.mp3` (the
path your laptop sees once the device is mounted). This tool needs to figure
out the right notation for a given device, and different operating systems
expose "what partitions exist on this device" through completely different
APIs. That's what the `platform.system()` branching in
`detect_from_device_storage` is for:

```python
import subprocess
import platform
...
if platform.system() == "Darwin":  # macOS
    result = subprocess.run(
        ["diskutil", "info", str(device_root)],
        capture_output=True, text=True, timeout=5,
    )
    ...
elif platform.system() == "Linux":
    result = subprocess.run(
        ["findmnt", "-n", "-o", "SOURCE", str(device_root)],
        capture_output=True, text=True, timeout=5,
    )
    ...
elif platform.system() == "Windows":
    import os
    drive = os.path.splitdrive(str(device_root))[0]
    if drive:
        mounts = [f"/<{storage_prefix}0>"]
        ...
```

`platform.system()` returns a string identifying the OS Python is currently
running on: `"Darwin"` for macOS (its underlying kernel's historical name),
`"Linux"`, or `"Windows"`. This if/elif chain is the standard idiom for
**"do fundamentally different things depending on what OS this code is
running on"** — there's no portable, built-in Python API for "list the
partitions on this physical disk," because that concept simply doesn't
exist identically across operating systems, so the code has to shell out to
each platform's own native tool.

`subprocess.run([...], capture_output=True, text=True, timeout=5)` is a new
(but very common) pattern: it runs an external command-line program (here,
macOS's `diskutil` or Linux's `findmnt`/`lsblk`) as a child process and waits
for it to finish, exactly like you'd type it in a terminal. The argument
list form (`["diskutil", "info", str(device_root)]`, a list of separate
strings rather than one shell command string) deliberately avoids
"shell injection" risk and avoids ambiguity about word-splitting/quoting —
each list element is passed to the OS as exactly one argument, with no shell
parsing in between. `capture_output=True` captures the command's stdout/
stderr into `result.stdout`/`result.stderr` instead of letting it print
directly to the terminal; `text=True` decodes that output as text (`str`)
instead of raw `bytes`; `timeout=5` prevents the whole tool from hanging
forever if the external command misbehaves — after 5 seconds without a
response, Python raises `TimeoutError` instead of waiting indefinitely.

On macOS, the code parses `diskutil`'s human-readable text output
line-by-line looking for the string `"Device Node:"`, then runs a *second*
`diskutil` command on the *base disk* (stripping the partition suffix
with a regex, `re.match(r"(/dev/disk\d+)", device_node)`) to enumerate all
of that disk's partitions and count how many are FAT/exFAT formatted (the
only filesystem types Rockbox-compatible devices actually use) — each one
becomes one `/<HDD{i}>` or `/<MMC{i}>` mount notation. This string-parsing
approach (reading plain-text CLI output rather than a structured API) is
fragile in the abstract — a point this project's own code is honest about,
only using it as one signal among several (see the module docstring's
three-tier reliability ordering: storage analysis first, reading an
*existing* database's own paths second, and inferring from
`rockbox-info.txt`'s device-type hint only as a last resort) — but it is
genuinely the only interface macOS exposes for this information outside
writing much more invasive low-level disk-access code.

### 3.7.2 The other detection method: reading paths back out of an existing database

```python
# mount_detector.py, detect_mounts
MOUNT_PATTERN = re.compile(r"^/<([A-Z]+\d+)>/")
...
for entry in path_tagfile.entries:
    path = entry.data
    match = MOUNT_PATTERN.match(path)
    if match:
        mount_name = match.group(1)
        mount_notation = f"/<{mount_name}>"
        ...
```

This is a nice complementary approach that doesn't need the device plugged
in at all: it reads `database_4.tcd` (the *path* tag file — recall from
§3.1 that file index 4 is specifically "filename/path") directly using the
exact same `TagFile.read()` machinery from §3.2, then runs a regular
expression over every stored path string to pull out whatever mount
notation Rockbox itself already baked into the paths the last time its
database was built. `re.compile(r"^/<([A-Z]+\d+)>/")` matches "starts with
`/<`, then one-or-more uppercase letters, then one-or-more digits, then
`>/`" — e.g. `/<HDD0>/`, `/<MMC1>/` — and `match.group(1)` extracts just the
captured `([A-Z]+\d+)` portion (`"HDD0"`) from inside the parentheses.

---

## 3.8 Try It Yourself

Work through these in order — each builds on the previous one's mental
model.

1. **Trace one file through the whole pipeline.** Pick any single audio
   file (or use a tiny test one). Mentally (or with a debugger/`print`)
   follow it through:
   - `FileScanner.scan_dir_metadata` discovers its path + size + mtime
     (§3.4.1).
   - `FileScanner.add_files` → `read_single_file_tags` reads its actual tags
     (§3.4.2), and `_add_file_internal` stores a minimal version in
     `TagCache` (§3.5.2).
   - `DatabaseGenerator.generate` → `process_batch_task` formats its tags
     into final string values (§3.3.3), and `_assemble_entry` turns those
     into one `IndexEntry` plus however many `TagEntry` objects it needed
     (reusing existing ones where possible — §3.3.5).
   - `DatabaseIO.write` → `TagFile.to_file`/`IndexFile.to_file` serialize
     everything to the five-or-so bytes-on-disk formats from §3.2.

   Write down, in your own words, what the *smallest unit of change* is at
   each stage (a `(path, size, mtime, tags)` tuple → a cache entry → a
   batch-processed dict → assembled objects → raw bytes).

2. **Run the real tests and read the assertions, not just the pass/fail.**

   ```bash
   cd DAP-DB-Manager
   python -m pytest tests/test_database_io.py tests/test_generator.py tests/test_file_scanner.py -v
   ```

   For each test, before running it, guess what it's checking based on its
   name; then read the body and see if you guessed right. Pay particular
   attention to `test_write_sequential` vs `test_write_with_parallel` in
   `test_database_io.py` — notice they assert the *same* outcome
   (`database_idx.tcd` exists) despite using completely different
   concurrency strategies internally. That's the hallmark of a well-designed
   parallel optimization: changing *how* the work happens shouldn't change
   *what* the result is.

3. **Break a `struct` format string on purpose, then fix it.** In a
   scratch copy of the repo (or a tiny standalone script using just
   `tagfile.py`'s pattern), change

   ```python
   f.write(struct.pack("III", self.magic, self.size, self.count))
   ```

   to

   ```python
   f.write(struct.pack("IIH", self.magic, self.size, self.count))
   ```

   (`H` is an unsigned *16-bit* short instead of a 32-bit `I` — look it up
   in Python's `struct` module docs table of format characters if you're
   curious what else is available.) Try writing then reading a `TagFile`
   with this mismatched pair of format strings (write with `"IIH"`, read
   back with the original `"III"`) and observe exactly what goes wrong —
   either a `struct.error` about buffer size, or (worse, and instructive)
   *silently wrong values*, if the byte counts happen to still divide
   evenly. This is the best way to build real intuition for why every byte
   of a binary format's layout has to be agreed on by both the writer and
   the reader, with zero room for "close enough."

4. **Simulate a rename by hand.** Using `rename_detector.detect_renames()`
   directly (it's a pure function — no file I/O, easy to call from a
   script or a `python3` REPL), construct a tiny fake "deleted entry" object
   with `.is_deleted()`, `.get("length")`, `.get("bitrate")`,
   `.get("mtime")`, and `["path"].data` (or just reuse real `IndexEntry`/
   `TagEntry` objects), plus a fake `new_file_info` dict with one new path,
   and watch which of the three strategies (§3.6.2) catches your scenario.
   Then change the mtime so it no longer matches, and see the algorithm
   fall through to path-similarity matching instead — confirm for yourself
   that the `match_reason` string returned changes accordingly.

5. **Trim the tag cache's memory budget and watch LRU eviction happen.**
   Call `TagCache.set_max_cache_memory(100)` (the minimum allowed) after
   loading a reasonably large folder of music, then call
   `TagCache.get_current_memory_usage()` before and after adding more files,
   and confirm the entry count drops once the 100MB ceiling is crossed —
   tying back directly to the `OrderedDict`/`popitem(last=False)` mechanism
   in §3.5.3.

---

**Previous:** [Chapter 2 — The CLI Layer](./02-cli-layer.md)
**Next:** [Chapter 4 — The Tagging System](./04-tagging-system.md)
