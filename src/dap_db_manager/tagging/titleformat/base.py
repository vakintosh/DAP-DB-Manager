from .tagbool import TagFalse
from . import utils
from .function import Function


class Statement(list):
    """An object holding a list of titleformat statements."""

    def __init__(self, parts):
        list.__init__(self, parts)

    @property
    def is_multiple(self):
        for parts in self:
            if parts.is_multiple:
                return True
        return False

    def format(self, tags):
        ret = TagFalse("")
        for part in self:
            value = part.format(tags)
            if isinstance(value, list):
                for v in value:
                    assert v.__class__.__name__ in (
                        "TagTrue",
                        "TagFalse",
                        "TagBoolWrapper",
                    )
            else:
                assert value.__class__.__name__ in (
                    "TagTrue",
                    "TagFalse",
                    "TagBoolWrapper",
                )

            ret = utils.add(ret, value)
        return ret[0] if len(ret) == 1 else ret

    def __repr__(self):
        """Standard representation for debugging."""
        return "Statement({})".format(", ".join(repr(part) for part in self))

    def to_string(self):
        return "".join(part.to_string() for part in self)

    def __pprint_helper(self, tabs=0):
        tab_char = "    "
        lines = []
        lines.append(tab_char * tabs + f"{self.__class__.__name__}([")
        for part in self:
            if isinstance(part, Statement):
                lines.extend(Statement.__pprint_helper(part, tabs + 1))
            elif isinstance(part, Function):
                lines.append(tab_char * (tabs + 1) + f"Function({repr(part.name)}, [")
                for arg in part.args:
                    lines.extend(Statement.__pprint_helper(arg, tabs + 2))
                    lines[-1] += ","
                lines.append(tab_char * (tabs + 1) + "])")
            else:
                lines.append(tab_char * (tabs + 1) + repr(part))
            lines[-1] += ","
        lines.append(tab_char * tabs + ")]")
        return lines

    def pprint(self):
        print("\n".join(self.__pprint_helper()))
