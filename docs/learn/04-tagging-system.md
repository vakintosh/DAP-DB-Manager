# Chapter 4 — The Tagging System

> **Who this is for:** you've read Chapter 0 (Python basics) and Chapter 1
> (project architecture). This chapter assumes you know what a dict, a class,
> a decorator, and a type hint are — if any of that is fuzzy, flip back to
> Chapter 0 first.
>
> **What we're building understanding of:** `src/dap_db_manager/tagging/`,
> specifically the `tag/` subpackage, which reads artist/album/title-style
> metadata out of music files in a dozen different audio formats and
> presents it through one consistent interface.

---

## 4.1 What is "tagging", and why is it hard?

An MP3, FLAC, or M4A file isn't just audio samples. Scattered through the
file (usually at the start or end) is a block of **metadata** — the artist
name, album, track title, track number, genre, and so on. This metadata
block is called a **tag**.

The hard part: every audio format invented its own tag format, with its own
field names:

| Concept | ID3 (MP3) | Vorbis Comment (FLAC/Ogg) | MP4 atom | ASF/WMA |
|---|---|---|---|---|
| Artist | `TPE1` | `ARTIST` | `©ART` | `Author` |
| Album | `TALB` | `ALBUM` | `©alb` | `WM/AlbumTitle` |
| Track title | `TIT2` | `TITLE` | `©nam` | `Title` |
| Track number | `TRCK` (as `"3/12"`) | `TRACKNUMBER` | `trkn` (a tuple!) | `WM/TrackNumber` |

Notice the last row: ID3 crams "track 3 of 12" into **one string** `"3/12"`,
while MP4 stores it as a **tuple** `(3, 12)`. Same *concept* ("this is track
3 of 12 total"), completely different *representation* on disk.

If every part of this project that wanted to know a song's artist had to
know all of these quirks, every tag format's weirdness would leak into
database-building code, GUI code, CLI code — everywhere. The fix is a
**mapping layer**: one piece of code whose entire job is "given a format and
a concept like `'artist'`, know how to get/set/delete it correctly." Every
other part of the codebase then just does `tag["artist"]` and never thinks
about `TPE1` vs `©ART` again. That mapping layer is what this chapter is
about.

### A new dependency: `mutagen`

This project doesn't parse MP3/FLAC/MP4 binary layouts itself — that would
be reinventing a very large wheel. It uses **mutagen**, a third-party
("not part of the Python standard library, installed separately") audio
tagging library. You'll see `import mutagen` and `from mutagen.mp3 import
EasyMP3` throughout this chapter's files. mutagen already knows how to
read/write the raw tag bytes for ~15 formats and exposes each file as a
dict-like object (`tags["TPE1"]` or `tags["ARTIST"]`, depending on format).
What this project's `tagging/tag/` package adds on top is the **uniform
naming layer** mutagen itself doesn't provide out of the box for every
field (mutagen's "Easy" wrappers cover some fields; this project extends
that coverage and makes it consistent and explicit).

---

## 4.2 The package layout

```
tagging/
  __init__.py          # exports: read, Tag, TagFile, TagEntry, format
  tag/
    __init__.py         # exports: Tag, read, TagFile, TagEntry; runs setup_all_mappings()
    core.py              # the Tag class itself
    formats.py           # file-extension → mutagen class table, and read()
    tagfile.py           # TagFile/TagEntry — NOT audio tags (see 4.4 note!)
    utils.py             # small value-conversion helper functions
    mappings/
      __init__.py        # setup_all_mappings() calls the three setup functions below
      default.py         # field names that work the same for every format
      format_specific.py # overrides for ASF, MP4, APE, Musepack, WavPack, WAVE
      id3.py              # overrides for ID3 (MP3) — the messiest format by far
```

The top package's `__init__.py` says this plainly in its docstring:

```python
"""Audio file tagging sub-package.
...
Sub-packages:
    tag/: Tag reading and manipulation (refactored from tag.py)
        - core.py: Core Tag class
        - formats.py: Audio format definitions
        - utils.py: Conversion utilities
        - mappings/: Field mappings for different formats
"""
```

Worth pausing on one line in `tag/__init__.py`:

```python
from .mappings import setup_all_mappings
...
# Initialize all tag field mappings
setup_all_mappings()
```

This call runs **at import time** — the moment anything does
`import dap_db_manager.tagging`, all the mapping tables get built and
registered before you've asked to read a single file. We'll see exactly
what "registered" means in the next section.

---

## 4.3 `core.py` — the `Tag` class

### 4.3.1 What problem is `Tag` solving?

`Tag` is a **wrapper** around a mutagen tag object. You construct one from
an already-opened mutagen file, and from then on you access fields using
one vocabulary (`"artist"`, `"album"`, `"tracknumber"`, …) no matter what
format the underlying file is:

```python
class Tag:
    """
    Encapsulates a mutagen tag object so that property access is similar across
    formats. (what a chore!)
    ...
    """
```

The docstring's "(what a chore!)" is the author being honest — unifying a
dozen incompatible tag formats behind one API is genuinely fiddly, and
that's exactly why it's centralized here instead of scattered everywhere.

### 4.3.2 The registry: `field_map`

```python
field_map: Dict[Any, Dict[str, Dict[str, Optional[Callable]]]] = {}
```

This is a **class attribute** (shared by every `Tag` instance, not
per-object) — it's the central registry of "how do I read/write/delete
field X for format Y." Reading the type hint from the inside out:

- innermost `Dict[str, Optional[Callable]]` — e.g.
  `{"getter": <function>, "setter": <function>, "deleter": <function>,
  "convert": <function>}`
- middle `Dict[str, ...]` — field name (`"artist"`) → the dict above
- outer `Dict[Any, ...]` — a **mutagen class** (like `MP3` or `FLAC`), or the
  special string `"default"` → the whole field-name dict for that format

So `field_map[FLAC]["artist"]["getter"]` would be "the function that reads
the artist field out of a FLAC file's tags." This nested-dict-as-lookup-table
structure is sometimes called a **dispatch table**: instead of writing

```python
if format == "mp3":
    ...
elif format == "flac":
    ...
```

the code builds a dictionary once and then just *looks up* the right
behavior. This is much easier to extend (add a new row to a table) than to
extend an ever-growing `if/elif` chain, and it's a recurring idiom in this
codebase — you'll see it again in `formats.py` and throughout `mappings/`.

### 4.3.3 Registering a key: `RegisterKey` and its helpers

`Tag.RegisterKey` is a `@classmethod` — defined on the class, called as
`Tag.RegisterKey(...)` rather than on an instance — that fills in one entry
of `field_map`:

```python
@classmethod
def RegisterKey(
    cls,
    name: str,
    type: Any = "default",
    getter: Optional[Callable] = None,
    setter: Optional[Callable] = None,
    deleter: Optional[Callable] = None,
    convert: Optional[Callable] = None,
):
    if type not in cls.field_map:
        cls.field_map[type] = {}
    ...
    cls.field_map[type][name] = {
        "getter": getter,
        "setter": setter,
        "deleter": deleter,
        "convert": convert,
    }
```

`type` here means "which mutagen class this registration is for" (confusingly
it shadows the built-in name `type()`, but Python allows that — it's just a
parameter name). `"default"` is a special pseudo-format meaning "use this
unless the specific format overrides it."

Notice the **functions themselves are stored as values in a dict** —
`getter`, `setter`, `deleter`, `convert` are all `Callable` (a function
object, passed around just like any other value). This is possible because
in Python, functions are **first-class objects**: you can store them in
variables, put them in dicts and lists, and pass them as arguments, exactly
like a string or a number. `mappings/default.py` and friends will define
small functions and hand them straight to `RegisterKey` — they're never
called directly by the code that defines them, only later, by `Tag.get`.

Three convenience wrappers build on `RegisterKey` for common cases:

```python
@classmethod
def RegisterBasicKey(cls, key, name, type="default", convert=None):
    def getter(tags):
        return tags[name]
    ...
    def setter(tags, value):
        tags[name] = value
    ...
    def deleter(tags):
        del tags[name]
    ...
    cls.RegisterKey(key, type, getter, setter, deleter, convert)
```

This is the common case: "field X is just `tags["SOME_RAW_KEY"]`, full
stop." `RegisterBasicKey("artist", "TPE1", MP3)` would mean "to get the
artist from an MP3, do `tags["TPE1"]`." Notice `getter`, `setter`, and
`deleter` are small **nested functions defined inside another function** —
they only exist to be handed to `RegisterKey`, and each one *closes over*
(remembers) the `name` argument (`"TPE1"`) from its enclosing call, a
pattern called a **closure**. That's how three differently-named `getter`
functions, created in a loop, each still point at the right raw tag name.

`RegisterInfoKey` is similar but reads from `tags.info` (format metadata
like sample rate or bitrate, rather than user-editable fields):

```python
@classmethod
def RegisterInfoKey(cls, key, name, type="default", convert=None):
    def getter(tags):
        return tags.info.__dict__[name]
    ...
    cls.RegisterKey(key, type, getter, convert=convert)
```

`RegisterUserKey` handles **unknown/custom fields** — anything not
explicitly registered falls back to a generic handler that takes *both* the
tags object and the requested field name, and builds the real tag name on
the fly:

```python
@classmethod
def RegisterUserKey(cls, name_func: Callable, type: Any = "default"):
    def user_field_getter(tags, name):
        return tags[name_func(name)]
    ...
    cls.RegisterKey("user_field", type, user_field_getter, ...)
```

`name_func` is itself a function — e.g. for MP4 it's
`lambda_like(name) = "----:com.apple.iTunes:" + name.upper()`. So asking for
a custom field called `"mood"` on an MP4 file looks up
`"----:com.apple.iTunes:MOOD"` automatically.

### 4.3.4 Reading a value: `get()`, `get_string()`, `__getitem__`

```python
def get(self, name: str) -> Any:
    try:
        return self.tag_mapping[name]["convert"](
            self.tag_mapping[name]["getter"](self.tags)
        )
    except KeyError:
        return self.tag_mapping["user_field"]["convert"](
            self.tag_mapping["user_field"]["getter"](self.tags, name)
        )
```

Read this inside-out, since it's two function calls nested together:

1. `self.tag_mapping[name]["getter"]` — look up the registered getter
   function for this field name (e.g. `"artist"`).
2. `(self.tags)` — call that getter, passing in the real mutagen tags
   object, to get the **raw** value straight out of the file (could be a
   string, a list, a tuple — whatever mutagen natively returns for that
   format).
3. `self.tag_mapping[name]["convert"]` — look up the registered converter.
4. Wrap the raw value in a call to that converter, to **normalize** it (e.g.
   always a list of strings).

If `name` isn't a recognized field (a `KeyError` is raised doing the lookup),
the `except` block falls back to the special `"user_field"` entry instead,
which handles arbitrary custom tag names. This is the project's
**fallback pattern**: look for an exact match first, and if there isn't one,
use a general-purpose handler.

`self.tag_mapping` (singular, no `_map` suffix) is **not** the class-wide
`field_map` — it's set up per-instance in `update_mapping()`:

```python
def update_mapping(self):
    self.tag_mapping = self.field_map["default"].copy()
    try:
        self.tag_mapping.update(self.field_map[type(self.tags)])
    except KeyError:
        pass
```

This starts from a copy of the **default** mappings, then layers the
format-specific mappings for this particular file's mutagen type
(`type(self.tags)` — e.g. `FLAC`) on top, overwriting any entries that the
format overrides. `dict.update()` merges one dict's keys into another,
overwriting on conflict — so format-specific entries win over defaults, and
any field a format *doesn't* override simply falls through to the default
behavior.

`get_string()` is a thin wrapper that always normalizes to a list of
strings — handy when you just want something printable, not a typed value:

```python
def get_string(self, name: str) -> list:
    """Convert the items to a string list before returning."""
    return conv_string_list(self.get(name))
```

Finally, `Tag` supports the **dict-like square-bracket syntax**
(`tag["artist"]`) by implementing the dunder method `__getitem__`:

```python
def __getitem__(self, name: str) -> Any:
    return self.__getitem_func(name)
```

`__getitem_func` is set up in the `force_string` property setter to point at
either `self.get` or `self.get_string`, depending on a flag chosen at
construction time — so `tag["artist"]` behaves differently depending on
whether you asked for `force_string=True`. (This is the same "store a
function as a value, call it later" idiom from 4.3.3, just applied to pick
between two whole methods instead of two closures.)

`__setitem__` and `__delitem__` are the write/delete mirror images, with the
same registered-lookup-then-fallback-to-user_field structure.

### 4.3.5 Pickling oddities (a brief aside)

The bottom third of `core.py` (`__getstate__`/`__setstate__`) deals with
**pickling** — Python's built-in mechanism for serializing an object to
bytes (e.g. to send it between worker processes, which Chapter 3 touched on
with `multiprocessing`). Some mutagen objects hold things that don't pickle
cleanly (bound methods, info objects defined inside another class, FLAC
seek-point tuples) and this code manually works around each quirk. You don't
need to understand every branch — just recognize the pattern: `__getstate__`
customizes *what gets saved* when an object is pickled, `__setstate__`
customizes *how it's restored*. This matters here because `Tag` objects get
passed between the multiprocessing worker pool and the main process while
scanning a music library.

---

## 4.4 `formats.py` and `tagfile.py` — format detection

This is the one place the chapter needs a correction to a natural
assumption: **`tagfile.py` is not about detecting MP3 vs FLAC vs MP4.**
Despite the similar name to `Tag`, `TagFile`/`TagEntry` implement something
completely different — the binary string-table file format used by the
on-device Rockbox database (the `database_*.tcd` files, covered properly in
the database-engine chapter). It's worth flagging explicitly because the
naming collision ("Tag" vs "TagFile") is a real trap when first reading this
codebase. The actual audio-format dispatch logic lives entirely in
`formats.py`.

### 4.4.1 The format table

```python
FORMAT_MAPPING = {
    # Microsoft / Windows
    ".asf": ASF,
    ".wma": ASF,
    ".wav": WAVE,
    # MPEG / Apple
    ".mp3": MP3,
    ".mp4": MP4,
    ".m4a": MP4,
    ".m4b": MP4,
    ...
    ".flac": FLAC,
    ...
}

SUPPORTED_EXTENSIONS = set(FORMAT_MAPPING.keys())
```

This is the same **data-driven dispatch table** idiom from `field_map`:
instead of

```python
if ext == ".mp3":
    cls = MP3
elif ext == ".flac":
    cls = FLAC
elif ext == ".m4a" or ext == ".mp4" or ext == ".m4b":
    cls = MP4
...
```

the extension-to-class relationship is just *data* (a dict), and
`SUPPORTED_EXTENSIONS` (a **set**, giving fast "is this extension
supported?" checks) is derived from it automatically by taking
`.keys()`. Add a new row to the dict and you've added format support —
no new branches, no risk of forgetting an `elif`.

### 4.4.2 Reading a file: delegated to mutagen's own dispatch

Interestingly, `FORMAT_MAPPING` isn't actually used to *pick* the format
when reading — it's mostly documentation/metadata (used elsewhere for
things like "is this extension even one we claim to support"). The real
read function hands the job to mutagen itself:

```python
_FALLBACK_PARSERS = [OggFLAC, ID3]

READ_OPTIONS = list(set(FORMAT_MAPPING.values())) + _FALLBACK_PARSERS


def read(filename: str, force_string: bool = False) -> Optional[Tag]:
    # mutagen.File will iterate through options to sniff the correct format
    tags = mutagen.File(filename, options=READ_OPTIONS)

    if tags:
        return Tag(tags, force_string)
    else:
        return None
```

`mutagen.File(..., options=READ_OPTIONS)` is mutagen's own **format
sniffing**: given a list of candidate parser classes, it tries each one
against the file's actual bytes (magic numbers / header signatures) until
one successfully parses it — not relying on the file extension at all. This
is more robust than trusting `.mp3`/`.flac` extensions, which can be wrong
or missing. `_FALLBACK_PARSERS` adds a couple of extra parsers
(`OggFLAC`, plain `ID3`) that aren't the "primary" handler for any
extension in `FORMAT_MAPPING` but are still useful to try.

The function returns `Optional[Tag]` (recall from Chapter 0: `Tag | None`)
— `None` if mutagen couldn't find any tags at all, otherwise a `Tag` object
wrapping whatever mutagen produced. This `read()` is what the rest of the
project calls — e.g. in `database/file_scanner.py`:

```python
tags = tagging.read(path)
```

The caller never needs to know or care whether `path` pointed at an MP3, a
FLAC, or an M4A — `read()` sorts that out and hands back a uniform `Tag`.

---

## 4.5 `mappings/` — data-driven field tables

This directory is the clearest example in the whole codebase of
**data-driven design**: preferring tables of data over long conditional
branches. Nearly every function in `mappings/` is a `for` loop over a
dictionary literal, calling `Tag.RegisterKey`/`RegisterBasicKey` once per
entry. This is deliberate — adding support for one more field in one more
format means adding one line to a dict, not writing a new `if` branch
somewhere.

### 4.5.1 `default.py` — the fallback used by every format

```python
for name, conv in {
    "artist": conv_string_list,
    "album artist": conv_string_list,
    "album": conv_string_list,
    "date": conv_string_list,
    "discnumber": conv_number_list,
    "totaldiscs": conv_number_list,
    "title": conv_string_list,
    "tracknumber": conv_number_list,
    "totaltracks": conv_number_list,
    "genre": conv_string_list,
    "composer": conv_string_list,
    "grouping": conv_string_list,
    "performer": conv_string_list,
    "comment": conv_string_list,
    "replaygain_album_gain": conv_number_list,
    ...
}.items():
    Tag.RegisterBasicKey(name, name, convert=conv)
```

Read this carefully: `Tag.RegisterBasicKey(name, name, convert=conv)` — the
**raw tag key equals the field name itself** (e.g. `"artist"` → raw key
`"artist"`, `"genre"` → raw key `"genre"`). This works because mutagen's
"Easy" wrapper classes (`EasyMP3`, `EasyID3`, `OggVorbis`, `FLAC`'s Vorbis
comments, etc.) already use these same plain-English names internally for
most fields — Vorbis-comment-based formats (FLAC, Ogg) natively call the
field `ARTIST`, which mutagen's Easy layer exposes case-insensitively as
`"artist"`. So `default.py` covers the *common case* where a format already
agrees with the project's naming convention. `conv_string_list` and
`conv_number_list` (from `utils.py`, see 4.6) are the "convert" functions —
e.g. `conv_number_list` turns `["3"]` into `[3]` (actual integers).

File-level fields that don't come from tag data at all — `path`,
`filesize`, `last_modified`, `codec` — are registered with plain functions
instead of relying on format conventions:

```python
def get_path(tags):
    return tags.filename

def get_filesize(tags):
    return os.stat(get_path(tags)).st_size
...
Tag.RegisterKey("path", getter=get_path, convert=conv_string_list)
Tag.RegisterKey("filesize", getter=get_filesize, convert=conv_number_list)
```

`"bitrate"`, `"channels"`, `"length"`, `"samplerate"` are registered via
`RegisterInfoKey`, because mutagen reports those under `tags.info` rather
than as a regular tag field:

```python
for key, value in {
    "bitrate": "bitrate",
    "channels": "channels",
    "length": "length",
    "samplerate": "sample_rate",
}.items():
    Tag.RegisterInfoKey(key, value, convert=conv_number_list)
```

Finally, unrecognized fields fall back to themselves verbatim:

```python
def default_custom_field(name):
    return name

Tag.RegisterUserKey(default_custom_field, "default")
```

### 4.5.2 `format_specific.py` — where formats disagree

Formats whose **native** field names don't match the defaults get explicit
override tables. ASF/WMA and MP4 are the biggest offenders, since neither
uses plain-English Vorbis-style names:

```python
ASF: {
    "artist": "Author",
    "album artist": "WM/AlbumArtist",
    "album": "WM/AlbumTitle",
    "date": "WM/Year",
    ...
},
MP4: {
    "artist": "\xa9ART",
    "album artist": "aART",
    "album": "\xa9alb",
    ...
},
```

`"\xa9ART"` is a string containing the Unicode copyright symbol `©` followed
by `ART` — MP4's "atoms" (its internal tag containers) are conventionally
named with a leading `©` for Apple-defined fields; `\xa9` is just how
Python writes that one character by its code point inside a string literal
(same idea as `\n` for newline, but using a hex escape for an arbitrary
Unicode character).

The outer loop structure is worth naming explicitly — it's a **dict of
dicts**, iterated with a nested `for`:

```python
for tag_type, tag_dict in {
    ASF: {...},
    MP4: {...},
    APE: {"date": "Year"},
    Musepack: {"date": "Year"},
    WavPack: {"date": "Year"},
}.items():
    for key, value in tag_dict.items():
        Tag.RegisterBasicKey(key, value, tag_type)
```

Outer loop: which **format class** (`ASF`, `MP4`, …). Inner loop: which
**field name → raw key** pairs for that format. This two-level iteration
over a table is the whole file's organizing idea, repeated several times for
different groups of fields (info fields, basic fields, tuple-based
track/disc fields, string-split track/disc fields).

**Non-table logic** appears only where the data genuinely can't be
expressed as a flat string-to-string mapping. Two examples:

MP4 stores track/disc numbers as **tuples** like `(3, 12)` rather than
single values, so a small factory function builds matching getter/setter/
deleter trios:

```python
def from_tuple(key, index, default=0):
    def getter(tags):
        val = tags[key][0][index]
        if val == default:
            raise KeyError(key)
        return val
    ...
    return getter, setter, deleter
```

`from_tuple("trkn", 0)` means "track number lives at index 0 of the tuple
stored under `trkn`"; `from_tuple("trkn", 1)` means "total tracks lives at
index 1." Calling this function **returns a 3-tuple of functions**, which is
then unpacked directly into `RegisterKey` using `*` (the "splat" operator
from Chapter 0's `*args` section, used here in reverse — spreading a
tuple's elements out as separate positional arguments):

```python
Tag.RegisterKey(key + "number", tag_type, *from_tuple(value, 0))
Tag.RegisterKey("total" + key + "s", tag_type, *from_tuple(value, 1))
```

APE/Musepack instead store `"3/12"` as a plain string (ID3-style), so a
parallel `split_string()` factory does the analogous job using
`str.partition()` instead of tuple indexing.

WAVE format gets a fully bespoke treatment for its `date` field because
WAVE's embedded ID3 tags support *several* possible date frames
(`TDRC`/`TDOR`/`TYER`/`TYE`, representing different ID3 version eras) and the
code must check them in priority order:

```python
def WAVE_date_getter(tags):
    id3 = tags.tags
    for frame in ["TDRC", "TDOR", "TYER", "TYE"]:
        if frame in id3:
            return list(id3[frame])
    raise KeyError("date")
```

This is the point where a simple dict mapping genuinely isn't enough
expressive power, and hand-written logic takes over — a useful lesson: data
tables are great until the *shape* of the problem stops being "name A maps
to name B," at which point you write code, not data.

### 4.5.3 `id3.py` — the messiest format, by far

ID3 (MP3's tag format) earns its own whole module because of historical
cruft: ID3 has had several incompatible versions (v2.2, v2.3, v2.4) each
with different frame names for the same concept, plus foobar2000 (a
popular Windows player this project's naming conventions borrow from, as
seen in `core.py`'s docstring "a la foobar2000") invented its own
conventions for fields ID3 never standardized, stuffed into generic
`TXXX` ("user-defined text") frames.

`ID3_GENRES` is a plain list of ~190 strings — the historical numeric genre
codes from the original ID3v1 spec (genre `0` = Blues, `1` = Classic Rock,
etc. — "Winamp extensions" added more later). It's included here purely as
reference data; skim past it.

The interesting part is `RegisterAdaptableKey` — note this registers keys
on `EasyID3` (mutagen's own ID3 wrapper class) rather than on this
project's `Tag` class, extending mutagen's vocabulary *before* `Tag`'s
default/format-specific tables even see it:

```python
def RegisterAdaptableKey(name, key_finder, key_setter):
    def getter(id3, key):
        return list(id3[key_finder(id3)])

    def setter(id3, key, value):
        try:
            frame = id3[key_finder(id3)]
        except KeyError:
            key_setter(id3, value)
        else:
            frame.text = value

    def deleter(id3, key):
        del id3[key_finder(id3)]

    EasyID3.RegisterKey(name, getter, setter, deleter)
```

`key_finder` is a function that *searches* for the right frame rather than
assuming a fixed name — because, again, the "right" frame might be
`TXXX:REPLAYGAIN_TRACK_GAIN` or might not exist yet. This is used for
ReplayGain fields and for `"comment"`, which has to search for any key
starting with `COMM` since comment frames can carry a language code suffix
(`COMM::eng`):

```python
def comment_finder(id3):
    for k in id3:
        if k.startswith("COMM"):
            return k
    raise KeyError("COMM")
```

The thorniest piece is `RegisterNumberPair`, handling `tracknumber`/
`totaltracks` and `discnumber`/`totaldiscs`. foobar2000 writes "3/12" into
one ID3 frame (`TRCK`) when possible, but if you only know the total (not
the number), it has nowhere to put "12" inside `"TRCK"` alone, so it stores
it in a side `TXXX:TOTALTRACKS` frame instead. The code's own comment sums
up the pain:

```python
# foobar stores 'tracknumber' and 'totaltracks' in the tracknumber frame 'TRCK'
# as such: %tracknumber[/%totaltracks%]
# If the %tracknumber% is blank, %totaltracks% is stored under TXXX
# (what a pain in the ass)
```

You don't need to trace every branch of `RegisterNumberPair` — the lesson to
take away is structural: when a *single logical field* ("total tracks") can
legitimately live in **two different places** depending on what else is
present, you can't express that with a one-line dict entry; you need real
getter/setter functions with conditional logic, same as the WAVE date
example above.

Finally:

```python
EasyID3.GetFallback = user_getter
EasyID3.SetFallback = user_setter
EasyID3.DelFallback = user_deleter
```

This assigns functions directly as **class attributes** of `EasyID3` (a
mutagen class, not this project's own `Tag`) — mutagen specifically looks
for attributes with these exact names to decide what to do for any field
name it doesn't otherwise recognize. This is mutagen's own extension
mechanism, being used here to teach `EasyID3` about TXXX-based custom
fields.

---

## 4.6 `utils.py` — small, pure conversion helpers

This is the smallest file in the package, and deliberately so — it holds
only stateless, no-side-effects conversion functions used as the `"convert"`
entry everywhere above:

```python
def conv_string(value: Any) -> str:
    """Convert a value to a comma-separated string."""
    if not isinstance(value, (list, tuple)):
        value = [value]
    return ", ".join(str(v) for v in value)
```

First line: if the value isn't already a list/tuple, wrap it in a
single-item list — this means the rest of the function can always assume
"a collection," never having to special-case "just one string." `", ".join(
... for v in value)` is a **generator expression** (same family as the list
comprehensions from Chapter 0) feeding `str.join`, producing e.g.
`"Rock, Pop"` from `["Rock", "Pop"]`.

```python
def conv_number(value: Any) -> Union[int, float]:
    """Convert a value to a number (int or float)."""
    if isinstance(value, (int, float)):
        return value
    value = conv_string(value)
    ...
    # Chop to the last non-numeric value
    ...
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return 0
```

This handles messy real-world tag data like `"3/12"` (want just `3`) or
`"2020-01-01T00:00:00"` for a year field, by trimming to the leading numeric
prefix, then trying `int()` first, falling back to `float()`, falling back
to `0` if nothing parses. This is a defensive pattern worth recognizing: real
music files in the wild have malformed tags, and a tag reader that crashes
on one weird file instead of degrading gracefully is a liability when
scanning a 50,000-track library.

`conv_string_list` and `conv_number_list` are just the "always return a
list" variants, applying `conv_string`/`conv_number` to every item:

```python
def conv_string_list(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [conv_string(v) for v in value]
```

`conv_default` is the fallback used when no explicit converter is given:
numbers pass through unchanged, everything else becomes a string. All four
functions are referenced by *name* throughout `mappings/`, never called
directly in `utils.py` itself — their only job is to be handed to
`Tag.RegisterKey(..., convert=conv_number_list)` and invoked much later, by
`Tag.get()`.

---

## 4.7 Worked example: tracing `ARTIST` through an MP3 file

Let's follow one concrete field, `artist`, from bytes on disk to a Python
value, for an MP3 file.

**1. Reading the file.** Somewhere in the project (e.g.
`database/file_scanner.py`):

```python
tags = tagging.read(path)   # path = "song.mp3"
```

**2. Format sniffing.** Inside `formats.py`'s `read()`:

```python
tags = mutagen.File(filename, options=READ_OPTIONS)
```

mutagen inspects the file's actual bytes, recognizes the ID3v2 header, and
returns an `EasyMP3` instance (ID3-based). That gets wrapped:

```python
return Tag(tags, force_string)
```

**3. Building the per-instance mapping.** Setting `self.tags = tags` (via
the `tags` property) triggers `update_mapping()`:

```python
self.tag_mapping = self.field_map["default"].copy()
self.tag_mapping.update(self.field_map[type(self.tags)])
```

`type(self.tags)` is `EasyMP3`/`MP3` (the class imported in `core.py` as
`from mutagen.mp3 import EasyMP3 as MP3`). Because `id3.py`'s registrations
target `EasyID3` (patched directly, not keyed by `MP3` in `Tag.field_map`),
and `default.py` already registered `"artist"` generically, the entry that
wins for `"artist"` here is the **default** one from `default.py`:

```python
Tag.RegisterBasicKey("artist", "artist", convert=conv_string_list)
```

which expands (via `RegisterBasicKey`) to:

```python
field_map["default"]["artist"] = {
    "getter": lambda tags: tags["artist"],
    "setter": lambda tags: ...,       # (actually named functions, not lambdas)
    "deleter": lambda tags: ...,
    "convert": conv_string_list,
}
```

**4. The caller asks for the artist:**

```python
artist = tag["artist"]
```

`__getitem__` dispatches to `self.get` (assuming default `force_string`):

```python
def get(self, name: str) -> Any:
    return self.tag_mapping[name]["convert"](
        self.tag_mapping[name]["getter"](self.tags)
    )
```

- `self.tag_mapping["artist"]["getter"](self.tags)` runs `tags["artist"]`.
  Because `self.tags` is an `EasyMP3`/`EasyID3` object, mutagen's *own*
  Easy-ID3 layer translates the friendly name `"artist"` internally to the
  real ID3 frame `TPE1`, and returns something like `["Radiohead"]`.
- `conv_string_list(["Radiohead"])` normalizes that to `["Radiohead"]` (a
  list of plain strings — already was one here, but this guarantees the
  *shape* of the result is always the same regardless of format).

**Result:** `tag["artist"] == ["Radiohead"]`, achieved without any calling
code ever needing to know the magic frame ID `TPE1` existed. If the exact
same logical field were being read from an **ASF/WMA** file instead, step 3
would instead pick up the format-specific override:

```python
ASF: {
    "artist": "Author",
    ...
}
```

registered via `Tag.RegisterBasicKey("artist", "Author", ASF)` in
`format_specific.py` — so the getter would do `tags["Author"]` instead of
`tags["artist"]`. Same call site (`tag["artist"]`), same result shape
(`["Radiohead"]`), completely different raw key under the hood. That
substitution, happening invisibly based on `type(self.tags)`, is the entire
point of this chapter's mapping layer.

---

## 4.8 Try It Yourself

1. **See what mutagen actually returns.** Find (or create) a real `.mp3`
   file, then in a Python REPL:
   ```python
   import mutagen
   tags = mutagen.File("song.mp3")
   print(type(tags))
   print(dict(tags))          # raw frame names and values, e.g. TPE1, TALB
   ```
   Compare that raw dict against what `dap_db_manager.tagging.read(...)`
   returns for the same file (`tag["artist"]`, `tag["album"]`, …). Notice
   how the raw keys differ from the project's normalized names.

2. **Do the same for a `.flac` file**, and compare its raw keys (`ARTIST`,
   `ALBUM`, all-caps Vorbis comments) to the MP3 ones. This should make the
   "different formats, different names, same concept" problem from 4.1
   concrete rather than theoretical.

3. **Add a `print()` inside `Tag.get()`** in `core.py` (temporarily!) that
   logs `name`, the raw getter result, and the converted result. Run the
   test suite (`pytest tests/test_tag_core.py`) or read a real file through
   `tagging.read()` and watch the trace. Remove the print when done.

4. **Trace a field that *isn't* `artist`.** Pick `"totaltracks"` and follow
   it through for an MP3 (`RegisterNumberPair` in `id3.py` — notice it can
   come from either `TRCK`'s `"3/12"` suffix *or* a separate `TXXX:TOTALTRACKS`
   frame) versus an MP4 (`from_tuple("trkn", 1)` in `format_specific.py` —
   a tuple index instead). Write down, in your own words, why MP4 needed a
   factory function instead of a one-line dict entry.

5. **Exercise: add a brand-new tag field**, e.g. `"mood"`. List every file
   you believe you'd need to touch, and why:
   - `mappings/default.py` — register a sensible default raw key (likely
     `"mood"` itself, if most formats already use that Vorbis-style name).
   - `mappings/format_specific.py` — add overrides for any format whose
     native name differs (check if MP4/ASF have a "mood"-like atom, or if
     it would have to fall through to their user-key fallback instead).
   - `mappings/id3.py` — ID3 has no standard mood frame; you'd likely need
     a `TXXX:MOOD` registration similar to `RegisterFoobarTXXXKey`.
   - Possibly `utils.py`, if `"mood"` needs a new conversion rule beyond
     plain string/number (it probably doesn't).
   - No changes needed in `core.py`, `formats.py`, or `tagfile.py` — that's
     the whole point of the mapping layer: new fields are additions to
     *data* (dicts), not changes to *dispatch logic*.
   Don't actually make the change yet — just write the list. This is the
   best way to confirm you understand how responsibility is divided across
   this package.

---

**Previous:** [Chapter 3 — The Database Engine](03-database-engine.md)
**Next:** [Chapter 5 — The Titleformat DSL](05-titleformat-dsl.md)
