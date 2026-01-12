import functools
from pathlib import PurePosixPath
import operator
import re
from functools import reduce, lru_cache
from typing import Callable

from . import utils
from . import statement
from .tagbool import TagBool, TagTrue, TagFalse


def parse(string):
    """Parse a titleformat function.

    Return a tuple: (Function, length of string parsed)

    The string should have the following format:
        '$' any+ '(' [ statement ',' ]* ')'

    """
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


# Values for return checks.
TEST_RETURN = -4
TEST_TRUE = -3
TEST_FALSE = -2
TEST_ALL = -1


def TEST_ARG(x):
    return x


class Function:
    """A titleformat object representing a function."""

    def __init__(self, name, args):
        self.name = name
        self.args = args

    def is_valid(self):
        """Test to see if the number of args is correct for the function."""
        nArgs = len(self.args)
        if nArgs < self.function.min_args:  # type: ignore[attr-defined]
            return False
        if self.function.max_args != -1 and nArgs > self.function.max_args:  # type: ignore[attr-defined]
            return False
        return True

    @property
    def is_multiple(self):
        for arg in self.args:
            if arg.is_multiple:
                return True
        return False

    def get_name(self):
        return self.__name

    def set_name(self, name):
        self.__name = name
        self.update_function()

    name = property(get_name, set_name)

    func_map: dict[str, Callable] = {}

    def update_function(self):
        self.function = self.func_map[self.name]

    def format(self, tags):
        return self.function(tags, *self.args)

    @classmethod
    def __register_function(cls, func, original_func=None):
        """Register a function in the class's function map.

        If original_func is supplied, the func's name and docstring
        attributes will be overwritten.

        func will have a min_args and max_args attributes added that describe
        the required number of arguments for the function.  If original_func
        is supplied, these statistics will be derived from original_func.

        """
        if original_func is not None:
            func.__name__ = original_func.__name__
            func.__doc__ = original_func.__doc__
        else:
            original_func = func

        # Add arbitrary attributes that describe the number of required
        # arguments.
        nArgs = original_func.__code__.co_argcount
        if original_func.__defaults__ is not None:
            nDefaults = len(original_func.__defaults__)
        else:
            nDefaults = 0
        flags = original_func.__code__.co_flags
        has_varargs = (flags & 0x04) or (flags & 0x08)

        func.min_args = nArgs - nDefaults
        if has_varargs:
            func.max_args = -1
        else:
            func.max_args = nArgs

        cls.func_map[func.__name__] = func

    @classmethod
    def RegisterStringFunction(cls, func, bool_test=TEST_ARG(0)):
        """
        String functions have all their arguments formated as strings.

        Boolean evaluation is tricky for string functions, and varies by
        function.  Each function can specify how boolean is determined:
            Always True
            Always False
            Evaluate the return value
            Any argument must be true
            A specific argument must be true

        Examples:
            1. The $strstr function (and its relatives) evaluates to True if
        a string is successfully found. [TEST_RETURN]
            2. The $longest function evaluates to True if the longest argument
        evaluates to True. [TEST_RETURN]
            3. The $char function always returns False. [TEST_FALSE]
            4. The $left function evaluates to True if its first argument
        evaluates to True. [TEST_ARG(0)]
        """

        def string_function(tags, *args):
            ret = []
            formatted_args = tuple(arg.format(tags) for arg in args)
            for args in utils.iter_arg_list(*formatted_args):
                value = func(*args)

                # Evaluate the bool value of this function
                if bool_test == TEST_RETURN:
                    bool_value = bool(value)
                elif bool_test == TEST_TRUE:
                    bool_value = True
                elif bool_test == TEST_FALSE:
                    bool_value = False
                elif bool_test == TEST_ALL:
                    bool_value = any(args)
                else:
                    bool_value = bool(args[bool_test])

                ret.append(TagBool(bool_value, str(value)))
            return ret

        cls.__register_function(string_function, func)

    @classmethod
    def RegisterNumberFunction(cls, func):
        """
        Number functions have all their arguments converted to ints, and
        always evaluate to False.
        """

        def number_function(tags, *args):
            ret = []
            formatted_args = tuple(arg.format(tags) for arg in args)
            for iter_args in utils.iter_arg_list(*formatted_args):
                int_args = [_to_int(arg) for arg in iter_args]
                ret.append(TagFalse(str(func(*int_args))))
            return ret

        cls.__register_function(number_function, func)

    @classmethod
    def RegisterMetaFunction(cls, func):
        """
        Meta functions should have the signature:
            func(tags, field, *args)
        Meta functions return True or False based on whether or not the field
        was found in the tag object (similar to Field objects).
        """

        def meta_function(tags, field, *args):
            return utils.call_func(
                func, tags, field.format(tags), *(arg.format(tags) for arg in args)
            )

        cls.__register_function(meta_function, func)

        # Since meta functions recieve the tags argument, we need to adjust
        # the min/max number of arguments calculated by __register_function().
        f = cls.func_map[func.__name__]
        f.min_args -= 1  # type: ignore[attr-defined]
        if f.max_args > 0:  # type: ignore[attr-defined]
            f.max_args -= 1  # type: ignore[attr-defined]

    @classmethod
    def RegisterConditionalFunction(cls, func):
        """
        Conditional functions should only evaluate the necessary portions of the
        arguments.  They recieve the arguments directly withiout prior
        formatting, so all formatting needs to be done in the function.
        The functions must have an underscore in front of it (because e.g "if"
        is not a valid function name).
        Conditional functions must return either TagTrue or TagFalse (i.e. this
        registration function doesn't handle the conversion.)

        *Important*
        The conditional functions must handle their own string/list/function
        mapping.
        i.e. If the input to a conditional function is
            ['Al Di Meola', 'Paco De Lucia']
        we should return a list of values.
        """
        func.__name__ = func.__name__[1:]
        cls.__register_function(func)

        # Since conditional functions recieve the tags argument, we need to
        # adjust the min/max number of arguments calculated by
        # __register_function().
        f = cls.func_map[func.__name__]
        f.min_args -= 1  # type: ignore[attr-defined]
        if f.max_args > 0:  # type: ignore[attr-defined]
            f.max_args -= 1  # type: ignore[attr-defined]

    def __repr__(self):
        return f"Function({self.name}, {repr(self.args)})"

    def to_string(self):
        return "${}({})".format(self.name, ",".join(a.to_string() for a in self.args))


# -------------------------------------------------------------------------------
# Number functions
# -------------------------------------------------------------------------------
@lru_cache(maxsize=512)
def _parse_number_from_string(value_str):
    """Parse a number from a string value. Cached for performance."""
    # Chop to the last non-numeric value
    value = value_str.strip()
    if value.startswith("-") or value.startswith("+"):
        sign = value[0]
        value = value[1:]
    else:
        sign = ""
    for i, c in enumerate(value):
        if c not in "1234567890.":
            value = sign + value[:i]
            break
    else:
        value = sign + value

    # Convert
    for conv in (int, float):
        try:
            return conv(value)
        except ValueError:
            pass
    return 0


def _to_number(value):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        value = "".join(str(v) for v in value)
    assert isinstance(value, str)

    return _parse_number_from_string(value)


def _to_int(value):
    return int(_to_number(value))


def _to_float(value):
    return float(_to_number(value))


def add(*args):
    return reduce(operator.add, args)


def sub(*args):
    return reduce(operator.sub, args)


def mul(*args):
    return reduce(operator.mul, args)


def div(*args):
    return reduce(operator.floordiv, (a for a in args if a != 0))


def mod(*args):
    return reduce(operator.mod, (a for a in args if a != 0))


def muldiv(a, b, c):
    return int(round(float(a) * b / c))


def min_(*args):
    return min(args)


min_.__name__ = "min"


def max_(*args):
    return max(args)


max_.__name__ = "max"

for func in [add, sub, mul, div, muldiv, mod, min_, max_]:
    Function.RegisterNumberFunction(func)


# -------------------------------------------------------------------------------
# String functions
# -------------------------------------------------------------------------------
def left(str, num):
    return str[: _to_int(num)]


def right(str, num):
    return str[len(str) - _to_int(num) :]


def cut(str, num):
    return str[_to_int(num) :]


def insert(str, insert_str, n):
    n = _to_int(n)
    return str[:n] + insert_str + str[n:]


def len_(obj):
    return len(obj)


len_.__name__ = "len"


def longest(string1, *strings):
    longest = string1
    for s in strings:
        if len(s) > len(longest):
            longest = s
    return longest


def shortest(string1, *strings):
    shortest = string1
    for s in strings:
        if len(s) < len(shortest):
            shortest = s
    return shortest


_split_chars = [" ", ",", "/", "\\"]


def _split_words(str):
    for ch in _split_chars:
        str = str.replace(ch, ch + " ")
    return str.split()


def _join_words(words):
    str = " ".join(words)
    for ch in _split_chars:
        str = str.replace(ch + " ", ch)
    return str


def caps(str):
    return _join_words(word[0].upper() + word[1:].lower() for word in _split_words(str))


def caps2(str):
    return _join_words(word[0].upper() + word[1:] for word in _split_words(str))


def lower(str):
    return str.lower()


def upper(str):
    return str.upper()


def replace(str, old, new):
    return str.replace(old, new)


def num(n, length):
    return str(_to_int(n)).zfill(_to_int(length))


def pad(str, len, char=" "):
    return str.rjust(_to_int(len), char)


def pad_right(str, len, char=" "):
    return str.ljust(_to_int(len), char)


def padcut(str, len, char=" "):
    len = _to_int(len)
    return str[:len].rjust(len, char)


def padcut_right(str, len, char=" "):
    len = _to_int(len)
    return str[len:].ljust(len, char)


def repeat(str, len):
    return str * _to_int(len)


def strchr(str, ch):
    try:
        return str.index(ch) + 1
    except ValueError:
        return ""


def strrchr(str, ch):
    try:
        return str.rindex(ch) + 1
    except ValueError:
        return ""


def strstr(str1, str2):
    return strchr(str1, str2)


def strrstr(str1, str2):
    return strrchr(str1, str2)


def substr(str1, start, end):
    return str1[_to_int(start) - 1 : _to_int(end)]


def trim(str):
    return str.strip()


def stripprefix(str, *args):
    if not args:
        args = ("the", "a")
    for prefix in args:
        if str.lower().startswith(prefix + " "):
            return str[len(prefix) + 1 :]
    return str


def swapprefix(str, *args):
    if not args:
        args = ("the", "a")
    for prefix in args:
        if str.lower().startswith(prefix + " "):
            return str[len(prefix) + 1 :] + ", " + str[: len(prefix)]
    return str


def char(num):
    return chr(_to_int(num))


def crlf():
    return "\n"


def tab(num=1):
    return "\t" * _to_int(num)


# Compiled regex pattern for year extraction (module-level for performance)
_YEAR_PATTERN = re.compile(r"(\d{4})")


def year(date_str):
    """Extract year from date string. Handles YYYY, YYYY-MM-DD, etc."""
    date_str = str(date_str).strip()
    if not date_str:
        return ""
    # Extract first 4 digits (year)
    match = _YEAR_PATTERN.match(date_str)
    return match.group(1) if match else date_str[:4] if len(date_str) >= 4 else date_str


def directory_path(path):
    return str(PurePosixPath(path).parent)


def directory(path, up=1):
    for iterations in range(_to_int(up)):
        path = directory_path(path)
    return PurePosixPath(path).name


def ext(path):
    return PurePosixPath(path).suffix


def filename(path):
    return PurePosixPath(path).stem


# These functions will return True if the first argument is True
for func in [
    left,
    right,
    cut,
    len_,
    insert,
    lower,
    upper,
    caps,
    caps2,
    num,
    pad,
    pad_right,
    padcut,
    padcut_right,
    repeat,
    replace,
    substr,
    trim,
    stripprefix,
    swapprefix,
    directory,
    directory_path,
    ext,
    filename,
    year,
]:
    Function.RegisterStringFunction(func, TEST_ARG(0))

# These functions will return True if the return value is True
for func in [strchr, strrchr, strstr, strrstr, longest, shortest]:
    Function.RegisterStringFunction(func, TEST_RETURN)

# These functions will never return True
for func in [
    char,
    crlf,
    tab,
]:
    Function.RegisterStringFunction(func, TEST_FALSE)


# -------------------------------------------------------------------------------
# Meta functions
# -------------------------------------------------------------------------------
def meta(tags, field, index=None):
    try:
        values = tags.get_string(field)
        if index is None:
            return TagTrue(", ".join(values))
        else:
            return TagTrue(values[_to_int(index)])
    except KeyError:
        return TagFalse()


def meta_num(tags, field):
    try:
        return TagTrue(str(len(tags.get_string(field))))
    except (KeyError, AttributeError):
        return TagFalse(str(0))


def meta_sep(tags, field, sep=", ", end_sep=None):
    if end_sep is None:
        end_sep = sep
    try:
        values = tags.get_string(field)
        return TagTrue(sep.join(values[:-2] + [end_sep.join(values[-2:])]))
    except KeyError:
        return TagFalse()


def meta_test(tags, *fields):
    for field in fields:
        try:
            tags.get(field)
        except KeyError:
            return TagFalse()
    return TagTrue()


for func in [meta, meta_num, meta_sep, meta_test]:
    Function.RegisterMetaFunction(func)


# -------------------------------------------------------------------------------
# Conditional functions
# -------------------------------------------------------------------------------


def _if_test(func):
    """
    A function decorator that calls the decorated function a number of times,
    providing already converted arguments to the function.

    e.g:
        @_if_test
        def _equals8(arg):
            return arg == 8

    Using this format string:
        $if($equals8($len(%<artist%>)),true,false)
    A song by Iron & Wine and Calexico should return
        ['false', 'true']
    """

    @functools.wraps(func)
    def __func(tags, *args):
        return utils.call_func(func, *(arg.format(tags) for arg in args))

    return __func


@_if_test
def _equal(arg1, arg2):
    return TagBool(_to_int(arg1) == _to_int(arg2))


@_if_test
def _longer(arg1, arg2):
    return TagBool(len(arg1) > len(arg2))


@_if_test
def _greater(n1, n2):
    return TagBool(_to_int(n1) > _to_int(n2))


@_if_test
def _strcmp(str1, str2):
    return TagBool(str1 == str2)


@_if_test
def _stricmp(str1, str2):
    return TagBool(str1.lower() == str2.lower())


@_if_test
def _and(*args):
    return TagBool(all(args))


@_if_test
def _or(*args):
    return TagBool(any(args))


@_if_test
def _not(value):
    return TagBool(not value)


@_if_test
def _xor(*args):
    return TagBool(sum(bool(a) for a in args) % 2 == 1)


def _test_conditions(tags, conditions, _then, _else=None):
    """
    An _if function helper.
    Tests all conditions (a list), returning a list composed of results, after
    formatting _then and _else arguments
    """
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


def _ifequal(tags, arg1, arg2, _then, _else=None):
    return _test_conditions(tags, _equal(tags, arg1, arg2), _then, _else)


def _ifgreater(tags, arg1, arg2, _then, _else=None):
    return _test_conditions(tags, _greater(tags, arg1, arg2), _then, _else)


def _iflonger(tags, arg1, arg2, _then, _else=None):
    return _test_conditions(tags, _longer(tags, arg1, arg2), _then, _else)


def _if2(tags, condition, _else):
    ret = []
    else_result = None
    for condition in utils._to_list(condition.format(tags)):
        if condition:
            ret.append(condition)
        else:
            if else_result is None:
                else_result = _else.format(tags)
            ret.append(else_result)
    return ret


def _if3(tags, *args):
    _else = args[-1]
    args = args[:-1]
    for a in args:
        a = a.format(tags)
        if any(utils._to_list(a)):
            return a
    return _else.format(tags)


def _select(tags, num, *args):
    num = _to_int(num.format(tags)) - 1
    try:
        return args[num].format(tags)
    except IndexError:
        return TagFalse()


for func in [
    _longer,
    _greater,
    _strcmp,
    _stricmp,
    _if,
    _if2,
    _if3,
    _ifequal,
    _ifgreater,
    _iflonger,
    _select,
    _and,
    _or,
    _not,
    _xor,
]:
    Function.RegisterConditionalFunction(func)
