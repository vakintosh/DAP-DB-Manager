from .tagbool import TagFalse


def parse(string):
    """Parse a literal titleformat string.

    Return a tuple: (String, length of string parsed)

    The string should have the following format:
        "'" [any | "\'"]+ "'" |
        any+

    """
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


class String:
    def __init__(self, string):
        self.string = string

    @property
    def is_multiple(self):
        return False

    def format(self, tags):
        return TagFalse(self.string)

    def __repr__(self):
        return f"String({repr(self.string)})"

    def to_string(self):
        return "'{}'".format(self.string.replace("'", "\\'"))
