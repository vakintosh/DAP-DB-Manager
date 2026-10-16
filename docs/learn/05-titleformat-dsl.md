# Chapter 5: The Titleformat DSL — A Tiny Language Inside Our Language

> **Previous:** [04-tagging-system.md](04-tagging-system.md) | **Next:** [06-peaks-subsystem.md](06-peaks-subsystem.md)

This chapter is the "computer science" chapter of this series. Everywhere else in
this project we're calling libraries and shuffling data around. Here, we're going
to look at code that **implements a programming language** — a small one, but a
real one, with its own grammar, its own parser, and its own interpreter.

If you've never written a parser before, that's fine — by the end of this chapter
you'll understand, from first principles, what tokenizing, parsing, ASTs, and
recursive evaluation actually are, using nothing but the real code in this repo.

We assume you've read [Chapter 0](00-python-primer.md) (so you're comfortable with
Python classes, generators, and basic recursion) and
[Chapter 1](01-project-overview.md) (so you know where this module sits in the
overall architecture). We will not re-explain what a Python class or a `for` loop
is. We *will* explain every new parsing/CS concept the first time it shows up.

---

## 1. What is a "titleformat" string, and what problem does it solve?

Music library tools need to show users a human-readable "title" for a track —
something like `Pink Floyd - Money` in a UI list. But different users want
different things: some want `Artist - Title`, some want `Track# - Title`, some
want the album in brackets if it's known, etc.

Rather than hard-coding one format, this project borrows an idea from the
classic **foobar2000** audio player: let the user supply a small **template
string** — called a *titleformat string* — that describes how to build the
display text out of tag fields. The module's own docstring
(`src/dap_db_manager/tagging/titleformat/__init__.py`) gives these exact
examples:

```text
%artist% - %title%
[%album artist% - ]%album%
$if(%date%,%date% - ,)%title%
```

Reading these just as a human, before any code:

- `%artist%` and `%title%` are placeholders — "put the artist tag's value here."
- `%artist% - %title%` means: artist value, then a literal ` - `, then title value.
- `[%album artist% - ]` is a *conditional* chunk in square brackets — if
  `%album artist%` has no value, the **whole bracketed chunk disappears**
  (including the literal `" - "` inside it), rather than leaving a dangling
  `" - "` behind. This is the single most important "quality of life" feature
  of the format language — conditional sections collapse cleanly.
- `$if(%date%,%date% - ,)` is a **function call** — `$if(condition, then, else)` —
  the titleformat equivalent of an `if` expression.

So a titleformat string is really a tiny **program**: when you call
`format(format_string, tags)`, the code must:

1. Read the string and understand its structure (parsing).
2. Walk that structure, looking up real tag values in `tags`, and
   build the final text (evaluating/interpreting).

That's exactly what `tagging/titleformat/` does. It is a complete, if small,
**interpreter for a domain-specific language (DSL)** — a language designed to do
one job (describe title formatting) rather than general computation.

---

## 2. Three phases, in general, before we touch code

Every language processor — whether it's Python itself, SQL, or this titleformat
mini-language — is conceptually built from three phases. We'll define each
generally first, then show exactly where it happens in this codebase.

```
  raw text                 tokens/structure              final value
"%artist% - %title%"  -->  tree of Field/String nodes --> "Pink Floyd - Money"
      |                           |                              |
   TOKENIZING /                EVALUATING /
   PARSING                     INTERPRETING
```

1. **Tokenizing (lexing)** — scanning raw characters and grouping them into
   meaningful chunks ("tokens"), e.g. recognizing that `%artist%` is one
   placeholder-token, not 8 separate characters. A **tokenizer** (or **lexer**)
   is the piece of code that does this scanning.

2. **Parsing** — taking those tokens (or, as we'll see, taking raw characters
   directly) and assembling them into a structured representation that
   captures how the pieces relate to each other — which parts are nested
   inside which other parts. This structured representation is usually called
   an **AST (Abstract Syntax Tree)** or a **parse tree**. "Abstract" because it
   throws away irrelevant details (exact whitespace, punctuation used purely
   as delimiters) and keeps only the meaningful structure: "this is a function
   call named `if` with these three argument-nodes."

3. **Evaluating (interpreting)** — walking that tree and actually *doing* what
   it describes — in our case, looking up tag values and concatenating text to
   produce one final string.

**A subtlety in this codebase**: many real parsers have tokenizing and parsing
as two fully separate steps (first turn the whole string into a token list,
*then* parse the token list). This codebase **fuses tokenizing and parsing into
one step**: each `parse(string)` function looks at the next character(s), decides
what kind of node that implies, consumes exactly the right number of characters,
and immediately returns a constructed node object. There's no separate token
list sitting in memory. This is a common simplification for small, line-oriented
languages, and it's worth naming explicitly so you recognize the pattern: **the
tokenizer and the parser are the same functions here.**

This overall parsing strategy — look at what's next, decide what kind of thing
it must be, and recursively call the right sub-parser — is called **recursive
descent parsing**, and we'll see it concretely in section 7.

---

## 3. `base.py` — the AST node types and the inheritance structure

Let's look at the actual base class. This is `src/dap_db_manager/tagging/titleformat/base.py`:

```python
from .tagbool import TagFalse
from . import utils
from .function import Function


class Statement(list):
    """An object holding a list of titleformat statements."""

    def __init__(self, parts):
        list.__init__(self, parts)
```

Stop here — this is a deliberately clever design decision. `Statement` **is a
Python `list`** (it inherits from `list`). A parsed titleformat string like
`"%artist% - %title%"` doesn't produce one node — it produces a *sequence* of
nodes: a `Field` node for `%artist%`, a `String` node for `" - "`, and a `Field`
node for `%title%`. Rather than inventing a separate "container of nodes" class,
the authors just made `Statement` *be* that list, with extra methods bolted on.
So `Statement([Field("artist"), String(" - "), Field("title")])` is simultaneously
"a Python list you can iterate/index like any other" and "a titleformat AST node
you can call `.format(tags)` on."

```python
    @property
    def is_multiple(self):
        for parts in self:
            if parts.is_multiple:
                return True
        return False
```

Every node type in this system exposes an `is_multiple` property. Some tags are
inherently multi-valued (e.g. a track can have two artists), and `is_multiple`
tracks whether *this* node's output could expand into several separate strings
rather than one. `Statement.is_multiple` just asks "is any one of my child nodes
multi-valued?" — this is the first example of a very common parse-tree pattern:
**a container node derives its own properties by asking its children**.

```python
    def format(self, tags):
        ret = TagFalse("")
        for part in self:
            value = part.format(tags)
            ...
            ret = utils.add(ret, value)
        return ret[0] if len(ret) == 1 else ret
```

This is the **evaluator**. `format(tags)` is the method every node type must
implement — "given the actual tag data, produce my string value." `Statement`'s
version is simple to describe in English: *evaluate each child node in order,
and concatenate the results.* We'll explain `TagFalse`/`utils.add` in section 5
and 6 — for now, just notice the shape: **a container node's `.format()` calls
`.format()` on each of its children**. This is the evaluator side of the same
recursive pattern we saw for `is_multiple`.

### The inheritance tree

`Statement` is the base/root AST node type. Here's how the other files build on
it:

| File | Class | Relationship to `Statement` |
|---|---|---|
| `base.py` | `Statement(list)` | The root node type — a sequence of child nodes |
| `conditional.py` | `Conditional(Statement)` | **Subclasses** `Statement` directly — a conditional `[...]` block is "a `Statement`, but formats to nothing if every child evaluated to a false/empty result" |
| `field.py` | `Field` | **Does not** subclass `Statement` — it's a leaf node (no children), representing one `%fieldname%` placeholder |
| `string.py` | `String` | Also a leaf node — represents one literal chunk of text |
| `function.py` | `Function` | Also not a `Statement` subclass — it's a node with a `name` and a list of `args` (where each arg is itself a full `Statement` — more on this in section 6) |

So the hierarchy is really: `Statement` is the only "container" class with a
subclass (`Conditional`). `Field`, `String`, and `Function` are independent node
types that all *duck-type* the same two-method interface — every node type in
this system implements:

- `.format(tags)` → evaluate this node against real tag data, return a value
- `.to_string()` → turn this node back into titleformat source text (round-trip,
  useful for debugging/`repr`)
- `.is_multiple` → is this node potentially multi-valued?

This is a textbook example of the **interpreter pattern** (sometimes called the
**visitor pattern** in its more general form): instead of one giant function
with a big `if isinstance(node, Field): ... elif isinstance(node, String): ...`
chain, **each node type knows how to evaluate itself**. The code that walks the
tree (`Statement.format`) doesn't need to know what kind of node it's looking
at — it just calls `.format(tags)` on it and trusts the node to do the right
thing. This is Python's dynamic dispatch (every object already "knows its own
class") doing the work that, in a language like Java or C++, would require an
explicit `accept(visitor)` method on every node and a `visit_Field`/`visit_String`
method on the visitor. It's the same idea, simplified by Python's dynamism.

---

## 4. `string.py` and `field.py` — the two leaf node types

### `String` — literal text

Literal text (anything that isn't `%...%`, `$...(...)`, or `[...]`) becomes a
`String` node. From `string.py`:

```python
class String:
    def __init__(self, string):
        self.string = string

    @property
    def is_multiple(self):
        return False

    def format(self, tags):
        return TagFalse(self.string)
```

A `String` node's evaluation is trivial: it ignores `tags` entirely and always
returns its own fixed text. It's never `is_multiple` — a literal piece of text
can't "expand" into several values. Notice it returns `TagFalse(self.string)`,
not a plain Python `str`. We'll explain exactly why in section 5 — short
version: literal text by itself should never make a conditional block "true".

There's also a `parse` function in the same file, worth reading closely because
it's our first taste of real parsing logic:

```python
def parse(string):
    assert string.startswith("'"), "Missing starting quote"
    extra_chars = 2  # The quotes
    ret = ""
    for c in string[1:]:
        if c == "'":
            if ret and ret[-1] == "\\":
                extra_chars += 1
                ret = ret[:-1]
            else:
                return String(ret), len(ret) + extra_chars
        ret += c
    raise ValueError("Unending string")
```

This handles *quoted* literals like `'%'` (used when you want a literal percent
sign in your output rather than starting a field reference — see the test
`titleformat_compile("'%' means percent")`). Notice the **return type**:
`(String(ret), len(ret) + extra_chars)` — a tuple of *(the node we built, how
many characters of the input we consumed)*. This "node, length consumed" pattern
is used by **every** `parse` function in this package, and it's the mechanism
that lets one parser call another and know exactly where to resume scanning.

### `Field` — `%fieldname%` placeholders

From `field.py`:

```python
def parse(string):
    assert string.startswith("%"), 'Missing starting "%"'
    string = string[1 : string.index("%", 1)]
    if string.startswith("<"):
        assert string.endswith(">"), 'Missing closing ">"'
        string = string[1:-1]
        return Field(string, multiple=True), len(string) + 4  # two %, two <>
    return Field(string), len(string) + 2  # two %
```

This is the tokenizer/parser for `%artist%` and the rarer `%<artist>%` form
(which marks a field as explicitly multi-valued, e.g. for multi-artist tags).
It finds the matching closing `%`, slices out the name between them, and
returns `Field(name)` plus the number of characters consumed (`len(string) + 2`
for the two `%` delimiter characters).

The `Field` class itself is more interesting because of *how* it resolves a
field name to actual tag-lookup behavior:

```python
class Field:
    def __init__(self, name, multiple=False):
        self.name = name
        self.multiple = multiple

    def get_name(self):
        return self.__name

    def set_name(self, name):
        self.__name = name
        try:
            self.function = self.func_map[name]
        except KeyError:
            def user_field(tags):
                return tags.get_string(name)
            self.function = user_field

    name = property(get_name, set_name)
```

This uses Python's `property()` to intercept assignment to `self.name`. The
moment you set `field.name = "artist"`, the setter looks up `"artist"` in a
class-level dictionary `func_map`. If `"artist"` has a **registered** special
handler (it does — see below), that handler becomes `self.function`. Otherwise,
it falls back to a generic `user_field` closure that just calls
`tags.get_string(name)` for *any* unrecognized tag name — this is how arbitrary
custom tags (not just the built-in ones) work through `%customtag%`.

Further down, `field.py` registers the built-ins:

```python
for name in (
    "album", "date", "discnumber", "totaldiscs", "title", "totaltracks",
    "genre", "replaygain_track_gain", "replaygain_album_gain",
    "replaygain_track_peak", "replaygain_album_peak", "samplerate",
    "path", "filesize", "last_modified",
):
    Field.RegisterSimpleField(name)

for name, fields in {
    "artist": ["artist", "album artist", "composer", "performer"],
    "album artist": ["album artist", "albumartist", "artist", "composer", "performer"],
}.items():
    Field.RegisterMappedField(name, fields)
```

`RegisterMappedField` is the implementation of the fallback behavior you saw
mentioned in the module docstring for `%albumartist%`-style fields: `%artist%`
tries the `artist` tag first, then `album artist`, then `composer`, then
`performer` — whichever is found *first* wins:

```python
@classmethod
def RegisterMappedField(cls, name, mappings):
    def getter(tags):
        for field in mappings:
            try:
                return tags.get_string(field)
            except KeyError:
                pass
        raise KeyError(name)
    cls.RegisterField(name, getter)
```

Finally, `Field.format` turns a looked-up tag value into the node's actual
output:

```python
def format(self, tags):
    try:
        if self.multiple:
            return list(map(TagTrue, self.function(tags)))
        else:
            return TagTrue(", ".join(self.function(tags)))
    except KeyError:
        return TagFalse("?")
```

If the lookup raises `KeyError` (field not present — e.g. `mock_tag.get_string =
Mock(side_effect=KeyError)` in the tests), the field evaluates to
`TagFalse("?")` — falsy, with the literal text `"?"`. If found, it's wrapped in
`TagTrue`, meaning "this evaluated successfully, and it's truthy." Time to
explain `TagTrue`/`TagFalse` properly.

---

## 5. `tagbool.py` and `conditional.py` — custom "truthiness" and conditional blocks

### Why not just use Python's `True`/`False`?

Here's the actual design problem: in `[%album artist% - ]%album%`, the bracketed
section should vanish **only if `%album artist%` is actually missing** — but the
*text itself* produced (`"Pink Floyd - "`) is a perfectly normal, non-empty
string, which Python would consider truthy anyway! We need a value that is
**both** a usable string (for concatenation) **and** carries an independent
true/false flag that specifically means "did a real tag lookup succeed
somewhere in here," completely decoupled from whether the string happens to be
empty or non-empty.

That's exactly what `tagbool.py` implements:

```python
class TagBoolWrapper(str):
    """
    A boolean unicode class. The class derives from unicode, so any
    unicode methods should be transparent. The class evaluates to a
    boolean value independent of its unicode value.
    """

    def __new__(cls, value, rep=None):
        if rep is None:
            rep = "1" if value else ""
        obj = str.__new__(cls, rep)
        obj._value = bool(value)
        return obj

    def __bool__(self):
        return self._value
```

`TagBoolWrapper` **subclasses `str`** — so a `TagBoolWrapper` instance genuinely
*is* a string for every practical purpose (concatenation, `len()`, slicing, you
name it) — except its boolean value (`bool(x)`, used implicitly by `if x:`) is
whatever `self._value` says, totally independent of the string's own content.
That's the override of `__bool__`.

```python
    def __add__(self, other):
        return TagBool(bool(self) or bool(other), super().__add__(other))
```

And here's the payoff: when you add two `TagBoolWrapper`s together (string
concatenation with `+`), the *text* concatenates normally (`super().__add__`),
but the *boolean flag* of the result is `True` if **either** operand was `True`.
This is exactly the rule from the module docstring:

> When boolean wrapper objects are added together ... the resulting boolean
> value of the wrapper class returns True if *either* of the added objects
> evaluates to True.

The three factory functions at the bottom just wrap `TagBoolWrapper` construction
with friendlier names:

```python
def TagBool(value, rep=None):
    return TagBoolWrapper(value, rep)

def TagTrue(rep="1"):
    return TagBool(True, rep)

def TagFalse(rep=""):
    return TagBool(False, rep)
```

So: `TagTrue("Pink Floyd")` is the string `"Pink Floyd"` that is also `True`.
`TagFalse("?")` is the string `"?"` that is also `False`. When `Statement.format`
concatenates a run of nodes via `utils.add(ret, value)` (which, peeking at
`utils.py`, ultimately uses `operator.add`, i.e. Python's `+`), the "is anything
in here truthy" flag rides along automatically through every `+`.

### `Conditional` — making `[...]` collapse

Now `conditional.py` makes complete sense:

```python
class Conditional(Statement):
    """A titleformat object representing a conditional statement."""

    def format(self, tags):
        ret = Statement.format(self, tags)
        if isinstance(ret, list):
            return [r if r else TagFalse() for r in ret]
        return ret if ret else TagFalse()
```

`Conditional` **subclasses `Statement`** (inheritance, confirming the table in
section 3) and reuses `Statement.format` to do the actual work of evaluating
and concatenating its children — then adds exactly one rule on top: *if the
combined result is falsy* (i.e. no real tag lookup inside the brackets
succeeded — only literal `String` nodes and/or missing `Field`/`Function`
results contributed), **throw away whatever text was produced** and return
`TagFalse()` (empty string, false) instead. This is precisely how
`[%album artist% - ]` disappears cleanly when there's no album artist: the
`String(" - ")` node alone is never enough to make the bracket "true" (recall
`String.format` returns `TagFalse(self.string)` — always false!), so if the
`Field("album artist")` lookup fails, the *entire bracketed block* — text and
all — collapses to nothing.

The `parse` function for conditionals shows recursive descent explicitly,
calling back into the top-level statement parser for everything *between* the
brackets:

```python
def parse(format):
    from . import statement  # Local import to break the circle
    assert format.startswith("["), "Missing starting square bracket"
    tf, length = statement.parse(format[1:], end_chars="]")
    return Conditional(tf), length + 2  # two []
```

(The `from . import statement` *inside* the function, instead of at the top of
the file, is a deliberate fix for a **circular import**: `statement.py` needs to
import `conditional.py` to know how to parse `[`, and `conditional.py` needs
`statement.py` to parse what's inside `[...]`. Deferring the import until the
function actually runs breaks that cycle.)

---

## 6. `function.py` — `$if(...)`, `$upper(...)`, and recursive evaluation of arguments

### Parsing a function call

```python
def parse(string):
    assert string.startswith("$"), 'Missing starting "$"'
    name = string[1 : string.index("(", 1)]
    string = string[1 + len(name) + 1 :]
    args = []
    own_length = len(name)
    while string and not string.startswith(")"):
        arg, length = statement.parse(string, end_chars=",)")
        own_length += length
        args.append(arg)
        string = string[length:]
        if string.startswith(","):
            own_length += 1
            string = string[1:]
    func = Function(name, args)
    assert func.is_valid()
    return func, own_length + 1 + 2  # One $, two ()
```

Read this as a loop that peels off one comma-separated argument at a time,
calling `statement.parse(...)` on each one. **Each argument of a function call
is itself a full mini-program** — it can contain fields, more function calls,
conditionals, literal text, anything. For `$if(%artist%,Yes,No)`, the three
arguments parsed are `Statement([Field("artist")])`, `Statement([String("Yes")])`,
and `Statement([String("No")])`.

This is the moment to name the general concept precisely:

> **Recursive descent parsing** is a parsing strategy where each kind of
> grammar construct gets its own function, and those functions call each other
> (including, sometimes, themselves) to handle nested structure. `statement.parse`
> calls `function.parse` when it sees `$`; `function.parse` calls back into
> `statement.parse` for each argument; `statement.parse` calls `conditional.parse`
> when it sees `[`; `conditional.parse` calls back into `statement.parse` for
> what's inside. The "descent" is through the grammar, mirroring how deeply the
> brackets/parens are nested in the actual input.

You can see this concretely in `statement.py`'s dispatch table:

```python
char_map = {
    "'": string.parse,
    "[": conditional.parse,
    "%": field.parse,
    "$": function.parse,
}
```

Whenever the top-level loop sees one of these four leading characters, it hands
off to the matching specialist parser — and three of those four specialists
call straight back into `statement.parse` for their inner content. That mutual
back-and-forth calling (`statement.parse` → `function.parse` → `statement.parse`
→ ...) *is* recursion, just spread across several functions instead of one
function calling itself directly.

### Evaluating a function call — recursion again, this time at runtime

```python
class Function:
    def format(self, tags):
        return self.function(tags, *self.args)
```

Notice: `self.args` is passed **unevaluated** — each arg is still a `Statement`
node, not a string yet! It's up to the specific registered function
implementation to decide *when* (or *whether*) to call `.format(tags)` on each
argument. Let's look at two different registration styles to see why that
choice matters.

**String functions** (like `$upper`) always evaluate every argument immediately:

```python
@classmethod
def RegisterStringFunction(cls, func, bool_test=TEST_ARG(0)):
    def string_function(tags, *args):
        ret = []
        formatted_args = tuple(arg.format(tags) for arg in args)
        for args in utils.iter_arg_list(*formatted_args):
            value = func(*args)
            ...
            ret.append(TagBool(bool_value, str(value)))
        return ret
    cls.__register_function(string_function, func)
```

`arg.format(tags) for arg in args` is a generator expression that calls
`.format(tags)` on *every single argument node*, unconditionally, before the
real Python function (e.g. `upper`) even runs. And `upper` itself is almost
embarrassingly simple:

```python
def upper(str):
    return str.upper()
```

`Function.RegisterStringFunction(upper, TEST_ARG(0))` is literally how `$upper`
gets wired up (among a whole list registered together — `lower`, `caps`,
`caps2`, `upper`, etc.). The entire job of making `$upper(%artist%)` work is:
(1) parse `%artist%` into a `Field` node, (2) at evaluation time, call
`Field.format(tags)` to get the actual string, (3) call Python's built-in
`.upper()` on it. Everything else (the `TagBool`/multi-value plumbing) is
generic infrastructure shared by every string function.

**Conditional functions** (like `$if`), by contrast, do **not** eagerly evaluate
every argument. That's the entire point of `$if` — it would be wrong (and
wasteful) to evaluate *both* the "then" and "else" branches before knowing which
one is needed:

```python
def _test_conditions(tags, conditions, _then, _else=None):
    ret = []
    then_result = None
    else_result = None
    for condition in utils._to_list(conditions):
        if condition:
            if then_result is None:
                then_result = _then.format(tags)
            ret.append(then_result)
        else:
            if else_result is None:
                else_result = _else.format(tags) if _else is not None else TagFalse()
            ret.append(else_result)
    return ret

def _if(tags, condition, _then, _else=None):
    return _test_conditions(tags, condition.format(tags), _then, _else)
```

Look closely: `_if` evaluates `condition.format(tags)` first (it has to — we
need to know whether the condition is true or false before choosing a branch).
*Then*, inside `_test_conditions`, **only the chosen branch's node**
(`_then` or `_else`) gets `.format(tags)` called on it — lazily, only when that
branch is actually needed, and the registration mechanism
(`RegisterConditionalFunction`) deliberately hands this function the raw,
*unevaluated* `Statement` nodes for `_then`/`_else` rather than pre-formatted
strings, specifically so it can make that choice:

```python
@classmethod
def RegisterConditionalFunction(cls, func):
    """
    Conditional functions should only evaluate the necessary portions of the
    arguments. They recieve the arguments directly without prior
    formatting, so all formatting needs to be done in the function.
    """
```

This is the clearest possible illustration of **recursive evaluation of an
AST**: evaluating a `Function` node (`$if(...)`) requires evaluating some of its
*argument nodes*, and each of those argument nodes might itself be another
`Function` node (`$if(%artist%,$if(%album%,Both,Artist only),None)` — a real
test case!) requiring evaluation of *its* arguments, and so on, until you bottom
out at leaf nodes (`Field`, `String`) that don't need to recurse further. The
call stack naturally unwinds back up, each level combining results from the
level below it, exactly like the recursive functions from
[Chapter 0](00-python-primer.md).

---

## 7. `statement.py` — assembling a full format string top to bottom

We already looked at the dispatch table, but let's re-read the full parse loop
with fresh eyes, now that you know what every piece means:

```python
def parse(format, end_chars=None):
    char_map = {
        "'": string.parse,
        "[": conditional.parse,
        "%": field.parse,
        "$": function.parse,
    }
    own_length = 0
    parts = []
    i = 0
    string_chars = []
    while i < len(format):
        c = format[i]
        if end_chars and c in end_chars:
            break
        if c in char_map:
            obj, length = char_map[c](format[i:])
            if string_chars:
                parts.append(string.String("".join(string_chars)))
                string_chars.clear()
            parts.append(obj)
            own_length += length
            i += length
        else:
            own_length += 1
            string_chars.append(c)
            i += 1

    if string_chars:
        parts.append(string.String("".join(string_chars)))
    return Statement(parts), own_length
```

In plain English, this is the **tokenizer+parser main loop** for the whole
language:

1. Walk the string one logical chunk at a time (`i` is our cursor).
2. If the current character is one of `'`, `[`, `%`, `$`, hand off to the
   matching specialist parser, which consumes some number of characters and
   returns a finished node (`obj`) plus how many characters it ate (`length`).
   Before appending that node, flush any plain-text characters accumulated so
   far into a `String` node (so "Artist: " before a `%artist%` becomes its own
   `String` node).
3. Otherwise, it's an ordinary character — just buffer it in `string_chars`
   (a Python list used for efficient accumulation, joined with `"".join(...)`
   only once we actually need the text — note the code comment: *"Use list for
   O(1) append instead of O(n) string concatenation"*, an actual performance
   consideration left in the source).
4. `end_chars` is how nested parsers (conditional's `]`, function's `,`/`)`)
   tell this same loop "stop early, I've hit my closing delimiter" — without
   `end_chars`, the top-level call just runs until the string ends.
5. Package everything collected into one `Statement(parts)` — remember,
   `Statement` *is* a `list`, so this is just "the final ordered list of
   top-level nodes," ready to be evaluated via `Statement.format`.

The `__init__.py` module ties it all together with the two public entry points:

```python
@functools.lru_cache(maxsize=512)
def compile(format_string):
    titleformat, dummy_length = statement.parse(format_string)
    return titleformat

def format(format_string, tags):
    return compile(format_string).format(tags)
```

`compile` is decorated with `@functools.lru_cache` — if you've read
[Chapter 0](00-python-primer.md)'s notes on decorators, you know this means:
parsing the *same* titleformat string twice reuses the previously-built
`Statement` tree instead of re-parsing it, which matters because the same
handful of format strings (e.g. a user's configured display template) get
formatted over and over, once per track, in a loop.

---

## 8. One complete worked trace

Let's trace `"$upper(%artist%)"` end to end, against a fake tag object where
`get_string("artist")` returns `["pink floyd"]`.

### Phase A — Parsing (building the tree)

1. `statement.parse("$upper(%artist%)")` starts scanning at `i=0`.
2. `format[0]` is `$` → found in `char_map` → calls `function.parse("$upper(%artist%)")`.
3. Inside `function.parse`:
   - `name = "upper"` (everything between `$` and the first `(`).
   - Remaining string to scan for args: `"%artist%)"`.
   - Loop: not starting with `)`, so call `statement.parse("%artist%)", end_chars=",)")`.
     - **Recursive call #1.** Inside this nested `statement.parse`:
       - `format[0]` is `%` → calls `field.parse("%artist%)")`.
         - Finds the next `%`, slices out `"artist"`, returns
           `(Field("artist"), 8)` (`len("artist")` is 6, plus 2 for the `%%`).
       - Appends `Field("artist")` to `parts`. Cursor `i` jumps past it.
       - Next character is `)`, which is in `end_chars=",)"` → loop breaks.
       - Returns `(Statement([Field("artist")]), 8)`.
   - Back in `function.parse`: `args = [Statement([Field("artist")])]`.
     `string` is now just `")"`, which starts with `)` → loop ends.
   - Builds `Function("upper", [Statement([Field("artist")])])`.
   - `func.is_valid()` checks argument count against `upper`'s registered
     `min_args`/`max_args` (1/1 — `upper(str)` takes exactly one argument) → OK.
   - Returns `(Function("upper", [...]), 16)` (the whole `$upper(%artist%)` is
     16 characters).
4. Back in the *outer* `statement.parse`: appends this `Function` node.
   Input exhausted → returns `(Statement([Function("upper", [...])]), 16)`.

The resulting tree, drawn as nested boxes:

```
Statement
└── Function("upper")
    └── args[0]: Statement
        └── Field("artist")
```

### Phase B — Evaluating (walking the tree)

Call `tree.format(fake_tags)` where `fake_tags.get_string("artist") == ["pink floyd"]`.

1. `Statement.format` iterates its one child: the `Function` node. Calls
   `function_node.format(fake_tags)`.
2. `Function.format` → `self.function(tags, *self.args)`, i.e. calls the
   generic `string_function(tags, Statement([Field("artist")]))` wrapper that
   `RegisterStringFunction` built around the real `upper`.
3. `string_function` evaluates **its** one argument first:
   `arg.format(tags)` → that argument is `Statement([Field("artist")])`, so we
   recurse: **`Statement.format` is called again** (this time for the inner,
   one-element statement).
   - It calls `Field("artist").format(tags)`.
   - `Field.format` calls `self.function(tags)` (the resolved getter for
     `"artist"`, since `"artist"` has a registered mapped-field handler), which
     calls `tags.get_string("artist")` → `["pink floyd"]`.
   - Not multiple, so: `TagTrue(", ".join(["pink floyd"]))` → `TagTrue("pink floyd")`.
   - Back in the inner `Statement.format`: one child, result is
     `TagTrue("pink floyd")`.
4. Back in `string_function`: `formatted_args = (TagTrue("pink floyd"),)`.
   Iterating `utils.iter_arg_list(...)` yields that single value;
   `value = func(*args)` calls the *real* `upper("pink floyd")` → `"PINK FLOYD"`.
   `bool_test` for `upper` is `TEST_ARG(0)` → the boolean flag is taken from
   whether argument 0 (`TagTrue("pink floyd")`) was truthy → `True`.
   Wraps it: `TagBool(True, "PINK FLOYD")`.
5. Back in `Function.format`: returns that single-element list's value up to
   the outer `Statement.format`.
6. Outer `Statement.format` concatenates its one part (`utils.add` against the
   initial `TagFalse("")`) → final result is the string `"PINK FLOYD"` (with a
   `True` flag riding along, discarded by the caller since we just want the text).

**Final output: `"PINK FLOYD"`.** This matches the real test in
`tests/test_titleformat_parser.py`:

```python
def test_eval_with_function(self):
    fmt = titleformat_compile("$upper(%artist%)")
    mock_tag = Mock()
    mock_tag.get_string = Mock(return_value=["test artist"])
    result = fmt.format(mock_tag)
    assert result == "TEST ARTIST"
```

Notice the recursive shape of the trace: `Statement.format` called
`Function.format`, which (via its helper) called `.format` on an *argument
that was itself a `Statement`*, which called `Field.format`. **Four different
classes, one shared method name, each handing off to the next and trusting it
to do its part correctly** — that's the interpreter pattern in action, and it's
exactly how `$if(%artist%,$if(%album%,Both,Artist only),None)` works too, just
with more branching and more depth.

---

## 9. Try It Yourself

1. **Read the tests as documentation.** Open `tests/test_titleformat_parser.py`
   and `tests/test_titleformat_comprehensive.py`. Find and read these three
   assertions carefully, and for each one, predict the AST shape *before*
   reading the code that handles it:
   - `test_eval_conditional` (the `$if(%artist%,Has artist,No artist)` case)
   - `test_field_missing` (what happens to `Field.format` on a `KeyError`)
   - `test_real_world_format` (a full, realistic multi-field, multi-function
     titleformat string — try tracing the top-level `Statement`'s children by
     eye, left to right, before running it)

2. **Run the test suite for this module** and watch it pass:
   ```bash
   pytest tests/test_titleformat_parser.py tests/test_titleformat_comprehensive.py -v
   ```
   Then **break something on purpose** — e.g. temporarily change
   `Field.format`'s `TagFalse("?")` to `TagFalse("MISSING")` — and re-run the
   tests to see exactly which assertion catches it. This is the fastest way to
   build intuition for how tightly these pieces are tested.

3. **Add `$lower()` end to end**, even though it likely already exists (check!)
   — if it does, instead add a brand-new, simple one-argument string function,
   e.g. `$reverse(str)` that reverses a string. Follow the exact same path
   `$upper` takes:
   - **No new tokenizer work needed** — `function.py`'s `parse()` already
     handles *any* `$name(...)` call generically; you don't touch the parsing
     code at all for a new string function. (This alone is worth sitting with:
     a good grammar design means adding vocabulary doesn't require touching the
     grammar.)
   - **Node class**: no new class needed either — `Function` already represents
     any function call; you're only adding a new *registered implementation*.
   - **Evaluator**: in `function.py`, write
     ```python
     def reverse(str):
         return str[::-1]
     ```
     and add `reverse` to the list of functions passed to
     `Function.RegisterStringFunction(func, TEST_ARG(0))` (find the `for func
     in [... upper, lower, caps ...]:` loop and add your function to that
     list).
   - **Files touched**: just `src/dap_db_manager/tagging/titleformat/function.py`.
   - **Verify**: write a quick test (or a throwaway script) that does
     `titleformat.format("$reverse(%artist%)", fake_tags)` with a mock `tags`
     object and check the output is reversed.

4. **Trace a conditional by hand.** Before running any code, write out on paper
   (or in a scratch `.md` file) the full node tree for
   `"[%album artist% - ]%album%"`, then trace `format(tags)` for two cases:
   `tags` with `album artist` present, and `tags` with it missing (raises
   `KeyError`). Confirm your prediction by actually running:
   ```python
   from unittest.mock import Mock
   from dap_db_manager.tagging import titleformat

   tags = Mock()
   tags.get_string = Mock(side_effect=lambda f: {"album": ["Animals"]}.get(f) or (_ for _ in ()).throw(KeyError(f)))
   print(titleformat.format("[%album artist% - ]%album%", tags))
   ```

5. **Connect it back to Chapter 1's architecture.** Find where
   `titleformat.format(...)` is actually *called* elsewhere in the codebase
   (try `grep -rn "titleformat" src/dap_db_manager --include=*.py` outside the
   `titleformat/` package itself) and read the surrounding code to see what
   real `tags` object gets passed in and what the resulting string is used for.

---

**Previous:** [04-tagging-system.md](04-tagging-system.md) | **Next:** [06-peaks-subsystem.md](06-peaks-subsystem.md)
