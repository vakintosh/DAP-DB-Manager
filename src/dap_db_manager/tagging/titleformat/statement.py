from . import string, field, function, conditional
from .base import Statement


def parse(format, end_chars=None):
    """Parse a titleformat statement.

    Return a tuple: (Statement, length of string parsed)

    The string should have the following format:
        [ string | conditional | field | function ] *

    """

    char_map = {
        "'": string.parse,
        "[": conditional.parse,
        "%": field.parse,
        "$": function.parse,
    }
    own_length = 0
    parts = []
    i = 0
    # Use list for O(1) append instead of O(n) string concatenation
    string_chars = []
    while i < len(format):
        c = format[i]
        if end_chars and c in end_chars:
            break
        if c in char_map:
            obj, length = char_map[c](format[i:])
            if string_chars:
                # Join once instead of repeated concatenation
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
