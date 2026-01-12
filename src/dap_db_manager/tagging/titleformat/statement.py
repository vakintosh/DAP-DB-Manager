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
    last_string = ""
    while i < len(format):
        c = format[i]
        if end_chars and c in end_chars:
            break
        if c in char_map:
            obj, length = char_map[c](format[i:])
            if last_string:
                parts.append(string.String(last_string))
                last_string = ""
            parts.append(obj)
            own_length += length
            i += length
        else:
            own_length += 1
            last_string += c
            i += 1

    if last_string:
        parts.append(string.String(last_string))
    return Statement(parts), own_length
