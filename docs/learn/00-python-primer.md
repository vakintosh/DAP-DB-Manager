# Chapter 0 — Python Primer (Zero Knowledge → Comfortable)

> **Who this is for:** you've never written Python before, or you've seen it but
> don't really know *why* it looks the way it does. This chapter teaches the
> building blocks in isolation, with tiny throwaway examples. Chapter 1 onward
> will point back here constantly ("remember dataclasses from Ch.0?").
>
> **How to use it:** don't just read — open a terminal, type `python3`, and
> type the examples yourself. Programming is a typing skill as much as a
> thinking skill.

---

## 0.1 Running Python

Two ways to run code:

```bash
# 1. Interactive shell (REPL) — great for experiments
python3
>>> 1 + 1
2
>>> exit()

# 2. Running a file
python3 myscript.py
```

Everything below can be typed directly into the REPL.

---

## 0.2 Variables and Types

Python is **dynamically typed**: a variable doesn't have a fixed type, the
*value* it holds has a type, and the variable just points at it.

```python
name = "Ada"          # str (text)
age = 36               # int (whole number)
height = 1.65          # float (decimal number)
is_cool = True         # bool (True/False)
nothing = None         # None = "no value", Python's null
```

Check a type at any time with `type()`:

```python
>>> type(age)
<class 'int'>
```

Variables can be reassigned to a different type — Python won't stop you (this
is both a convenience and a classic source of bugs):

```python
x = 5
x = "now I'm text"   # perfectly legal, just usually bad style
```

### Basic operators

```python
3 + 2     # 5
3 - 2     # 1
3 * 2     # 6
3 / 2     # 1.5   <- always float
3 // 2    # 1     <- floor (integer) division
3 % 2     # 1     <- remainder (modulo)
3 ** 2    # 9     <- power
```

### f-strings (string formatting)

The modern, preferred way to build strings with embedded values:

```python
name = "Ada"
age = 36
print(f"{name} is {age} years old")
# Ada is 36 years old
```

You will see `f"..."` everywhere in real codebases, including this project.

---

## 0.3 Collections

### Lists — ordered, mutable, allow duplicates

```python
fruits = ["apple", "banana", "cherry"]
fruits.append("date")          # add to end
fruits[0]                      # "apple"  (indexing starts at 0)
fruits[-1]                     # "date"   (negative index = from the end)
fruits[1:3]                    # ["banana", "cherry"]  (slicing)
len(fruits)                    # 4
"banana" in fruits             # True
```

### Tuples — ordered, **immutable** (can't change after creation)

```python
point = (3, 4)
x, y = point        # "unpacking" — assigns 3 to x, 4 to y
```

Used when you want to guarantee the data won't be mutated, or to return
multiple values from a function.

### Dictionaries — key → value mapping

```python
person = {"name": "Ada", "age": 36}
person["name"]              # "Ada"
person["job"] = "Engineer"  # add a new key
person.get("missing", "default value")  # safe lookup, no crash
for key, value in person.items():
    print(key, value)
```

This project uses dictionaries constantly — e.g. mapping a tag name like
`"ARTIST"` to how to read it from a file.

### Sets — unordered, unique values only

```python
seen = {1, 2, 2, 3}   # {1, 2, 3} — duplicates removed automatically
```

Used for fast "have I seen this already?" checks.

---

## 0.4 Control Flow

```python
# if / elif / else
age = 20
if age < 13:
    print("child")
elif age < 20:
    print("teen")
else:
    print("adult")

# while loop
count = 0
while count < 3:
    print(count)
    count += 1

# for loop — the one you'll use 90% of the time
for fruit in ["apple", "banana"]:
    print(fruit)

for i in range(5):       # 0,1,2,3,4
    print(i)

for i, fruit in enumerate(["apple", "banana"]):
    print(i, fruit)       # 0 apple / 1 banana
```

Python uses **indentation** (whitespace) instead of `{ }` to mark blocks of
code. This is not just style — it's required syntax. Standard is 4 spaces.

---

## 0.5 Functions

```python
def greet(name):
    return f"Hello, {name}!"

greet("Ada")   # "Hello, Ada!"
```

### Default arguments

```python
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"

greet("Ada")                # "Hello, Ada!"
greet("Ada", "Hi")           # "Hi, Ada!"
greet("Ada", greeting="Yo")  # "Yo, Ada!" (keyword argument)
```

### Type hints

Modern Python lets you annotate the *expected* types of arguments and return
values. These are **not enforced at runtime** by default — they're for
readability and for tools like `mypy`/`pyright` to catch mistakes before you
even run the code. This project uses them everywhere.

```python
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
```

Common type hints you'll see in this project:

```python
from pathlib import Path

def load(path: Path) -> list[str]: ...
def find(tags: dict[str, str]) -> str | None: ...   # "str or None"
def process(items: list[int] | None = None) -> None: ...
```

`-> None` means "this function doesn't return a useful value."
`str | None` (read "str or None") means the value might be missing.

### `*args` and `**kwargs`

Let a function accept any number of extra positional/keyword arguments:

```python
def log(message, *args, **kwargs):
    print(message, args, kwargs)

log("hi", 1, 2, name="Ada")
# hi (1, 2) {'name': 'Ada'}
```

You'll see this in wrapper/decorator code that needs to "pass everything
through" to another function without knowing its exact signature.

---

## 0.6 Modules and Imports

Any `.py` file is a **module**. A folder with an `__init__.py` file is a
**package** (a collection of modules you can import as a unit).

```python
import os                      # standard library module
from pathlib import Path       # import one name from a module
from mypackage.util import foo # import from your own code
import mypackage.util as u     # import with an alias
```

This project's code lives under `src/dap_db_manager/`, organized into
packages like `database/`, `tagging/`, `cli/`, `gui/`, `peaks/` — each is a
folder with an `__init__.py`.

---

## 0.7 Classes and Objects (Object-Oriented Programming)

A **class** is a blueprint for creating objects that bundle data (attributes)
and behavior (methods) together.

```python
class Dog:
    def __init__(self, name, breed):   # constructor — runs when you create one
        self.name = name                # self = "this particular dog"
        self.breed = breed

    def bark(self):
        return f"{self.name} says Woof!"

rex = Dog("Rex", "Labrador")   # create an "instance" of Dog
rex.bark()                     # "Rex says Woof!"
rex.name                       # "Rex"
```

- `self` is always the first parameter of a method — it refers to the specific
  object the method is being called on. Python passes it automatically; you
  don't supply it yourself (`rex.bark()`, not `rex.bark(rex)`).
- `__init__` is a **dunder** (double-underscore) method — Python calls these
  automatically in special situations. `__init__` runs on creation, `__str__`
  controls what `print(obj)` shows, `__eq__` controls `==`, etc.

### Inheritance

```python
class Animal:
    def __init__(self, name):
        self.name = name
    def speak(self):
        return "..."

class Dog(Animal):              # Dog "is an" Animal
    def speak(self):            # override the parent's method
        return f"{self.name} says Woof!"
```

### `dataclasses` — classes for data, with less boilerplate

Writing `__init__` by hand for simple "bag of data" classes gets repetitive.
`@dataclass` generates it for you:

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int

p = Point(3, 4)
p.x          # 3
print(p)     # Point(x=3, y=4)   <- auto-generated readable repr
```

`@dataclass` here is a **decorator** (see 0.9). This project uses dataclasses
heavily to represent structured records (e.g. one song's tag data).

### Pydantic models (used for validation)

This project also uses **Pydantic**, a library built on top of the same idea
as dataclasses, but which actively *validates* data at runtime (e.g. "this
field must be an integer between 0 and 255") and is often used for things
like CLI arguments or config files. You'll meet it properly in Chapter 2.

---

## 0.8 Exceptions (Error Handling)

```python
try:
    result = 10 / 0
except ZeroDivisionError as e:
    print(f"Something went wrong: {e}")
finally:
    print("This always runs")
```

- Code that might fail goes in `try:`.
- `except SomeError:` catches a specific kind of failure and handles it
  instead of crashing the whole program.
- `finally:` runs no matter what (cleanup code).

Raising your own errors:

```python
def set_age(age):
    if age < 0:
        raise ValueError("age cannot be negative")
```

Real projects define their own exception types for clarity:

```python
class DatabaseCorruptError(Exception):
    pass

raise DatabaseCorruptError("header checksum mismatch")
```

---

## 0.9 Decorators (the `@something` syntax)

A decorator is a function that wraps another function to add behavior
without changing its code. You've already seen one: `@dataclass`.

```python
def shout(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result.upper()
    return wrapper

@shout
def greet(name):
    return f"hello {name}"

greet("ada")   # "HELLO ADA"
```

`@shout` above `def greet` is exactly equivalent to writing
`greet = shout(greet)`. Decorators are used for logging, timing, caching,
registering CLI commands, validating inputs, and more — you'll see them used
for several of these purposes in this project.

Common built-in decorators:

```python
class MyClass:
    @staticmethod
    def utility():            # doesn't need `self`, just namespaced here
        return 42

    @property
    def computed_value(self): # lets you call obj.computed_value (no parens!)
        return self._x * 2
```

---

## 0.10 Context Managers (`with`)

Used to guarantee cleanup (closing a file, releasing a lock) even if an error
happens in between.

```python
with open("file.txt") as f:
    contents = f.read()
# file is automatically closed here, even if read() raised an exception
```

You write your own with a class implementing `__enter__`/`__exit__`, or more
commonly with `@contextmanager` from `contextlib`. This project uses `with`
for file handles and for things like progress bars.

---

## 0.11 Generators and Iteration

A **generator** produces values one at a time, lazily, instead of building a
whole list in memory at once — useful for processing huge numbers of files.

```python
def countdown(n):
    while n > 0:
        yield n     # pause here, hand back a value, resume on next request
        n -= 1

for number in countdown(3):
    print(number)   # 3, 2, 1
```

`yield` is what makes a function a generator. Each call to the loop resumes
the function right where it left off.

List/dict comprehensions are a compact way to build collections:

```python
squares = [x * x for x in range(5)]          # [0, 1, 4, 9, 16]
evens = [x for x in range(10) if x % 2 == 0] # [0, 2, 4, 6, 8]
lookup = {x: x * x for x in range(3)}        # {0: 0, 1: 1, 2: 4}
```

---

## 0.12 Reading Files and Paths

```python
from pathlib import Path

p = Path("/Users/me/music/song.mp3")
p.name          # "song.mp3"
p.suffix        # ".mp3"
p.parent        # Path("/Users/me/music")
p.exists()      # True/False
for file in p.parent.glob("*.mp3"):
    print(file)
```

`pathlib.Path` is the modern, object-oriented way to handle file paths in
Python (replacing older string-based `os.path` functions). This project uses
it throughout instead of raw strings.

Binary files (not text) are read like this — important for this project
since database files are binary:

```python
with open("data.bin", "rb") as f:   # "rb" = read binary
    raw_bytes = f.read()

import struct
value = struct.unpack(">I", raw_bytes[0:4])[0]  # read a big-endian uint32
```

You'll see `struct` used a lot in Chapter 3 (the database file format is a
custom binary layout).

---

## 0.13 Command-Line Programs

The standard library module `argparse` builds command-line interfaces:

```python
import argparse

parser = argparse.ArgumentParser(description="Greet someone")
parser.add_argument("name")                       # positional argument
parser.add_argument("--loud", action="store_true") # optional flag
args = parser.parse_args()

if args.loud:
    print(args.name.upper())
else:
    print(args.name)
```

Run as: `python3 script.py Ada --loud` → `ADA`

This project's CLI (`ddm`) is built this way, but organized into
**subcommands** (`ddm generate`, `ddm update`, …) — Chapter 2 shows exactly
how.

---

## 0.14 Concurrency, Briefly

Two concepts you'll meet in Chapter 3:

- **Multiprocessing**: run code in multiple separate OS processes to use
  multiple CPU cores at once (Python's `multiprocessing` module). This
  sidesteps Python's **GIL** (Global Interpreter Lock), a quirk that
  normally prevents true CPU-bound parallelism within a single process.
- **Threading**: run code in multiple threads of the *same* process — good
  for keeping a GUI responsive while work happens in the background, not
  for CPU-bound speedups (because of the GIL).

```python
from multiprocessing import Pool

def square(x):
    return x * x

with Pool(4) as pool:                 # 4 worker processes
    results = pool.map(square, [1, 2, 3, 4])
```

---

## 0.15 Cheat Sheet — Glossary

| Term | Meaning |
|---|---|
| Module | a single `.py` file |
| Package | a folder of modules with `__init__.py` |
| Instance | a specific object created from a class |
| Attribute | a variable that belongs to an object (`obj.x`) |
| Method | a function that belongs to a class (`obj.method()`) |
| `self` | the instance a method is operating on |
| Dunder method | `__init__`, `__str__`, etc. — special hooks Python calls for you |
| Decorator | `@something` — wraps a function/class to add behavior |
| Type hint | `name: str` — documents expected types (not enforced at runtime) |
| Exception | an error object raised when something goes wrong |
| Generator | a function using `yield` that produces values lazily |
| Context manager | a `with` block that guarantees setup/cleanup |
| GIL | Global Interpreter Lock — why Python threads don't speed up CPU work |

---

**Next:** [Chapter 1 — Project Overview](01-project-overview.md), where we
stop writing toy examples and start reading the real codebase.
