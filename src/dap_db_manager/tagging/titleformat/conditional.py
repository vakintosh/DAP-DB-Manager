from .base import Statement, TagFalse


def parse(format):
    """Parse a conditional titleformat statement.

    Return a tuple: (Conditional, length of string parsed)

    The string should have the following format:
        '[' statement ']'

    """
    # Local import to break the circle
    from . import statement

    assert format.startswith("["), "Missing starting square bracket"
    tf, length = statement.parse(format[1:], end_chars="]")
    return Conditional(tf), length + 2  # two []


class Conditional(Statement):
    """A titleformat object representing a conditional statement."""

    def format(self, tags):
        ret = Statement.format(self, tags)
        if isinstance(ret, list):
            return [r if r else TagFalse() for r in ret]
        return ret if ret else TagFalse()

    def __repr__(self):
        return "Conditional({})".format(", ".join(repr(part) for part in self))

    def to_string(self):
        return "[" + super().to_string() + "]"
