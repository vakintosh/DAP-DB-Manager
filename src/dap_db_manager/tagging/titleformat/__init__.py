"""Title formatting sub-package.

This package implements Foobar2000-style format string parsing and evaluation
for audio file tags. It allows formatting tag data using expressions like:
    %artist% - %title%
    [%album artist% - ]%album%
    $if(%date%,%date% - ,)%title%

Modules:
    statement.py: Top-level statement parsing
    conditional.py: Conditional expressions ([...])
    field.py: Tag field references (%fieldname%)
    string.py: Literal string handling
    function.py: Function calls ($function(...))
    tagbool.py: Boolean-like tag values
    utils.py: Utility functions for parsing

Main functions:
    compile(format_string): Parse format string into Statement object (memoized)
    format(format_string, tags): Format tags using format string
"""

import functools
from . import statement
from .statement import Statement as Statement
from .conditional import Conditional as Conditional
from .field import Field as Field
from .string import String as String
from .function import Function


@functools.lru_cache(maxsize=512)
def compile(format_string):
    """Compile a format string into a Statement object.

    Args:
        format_string: Foobar2000-style format string

    Returns:
        Statement object that can be evaluated with tags
    """
    titleformat, dummy_length = statement.parse(format_string)
    return titleformat


def format(format_string, tags):
    """Format tags using a format string.

    Args:
        format_string: Foobar2000-style format string
        tags: Tag object containing audio metadata

    Returns:
        Formatted string with tag values substituted
    """
    return compile(format_string).format(tags)


__all__ = [
    "compile",
    "format",
    "Statement",
    "Conditional",
    "Field",
    "String",
    "Function",
    "base",
    "tagbool",
    "utils",
]
