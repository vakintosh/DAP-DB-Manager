import operator

# itertools.product doesn't exist in python 2.5
try:
    from itertools import product
except ImportError:
    # This code taken from the python 2.6 itertools manual
    def product(*args, **kwds):  # type: ignore[no-redef]
        # product('ABCD', 'xy') --> Ax Ay Bx By Cx Cy Dx Dy
        # product(range(2), repeat=3) --> 000 001 010 011 100 101 110 111
        pools = list(map(tuple, args)) * kwds.get("repeat", 1)
        result: list[list] = [[]]
        for pool in pools:
            result = [x + [y] for x in result for y in pool]
        for prod in result:
            yield tuple(prod)


def make_arg_list(*args):
    return zip(*product(*(_to_list(arg) for arg in args)))


def iter_arg_list(*args):
    return zip(*make_arg_list(*args))


def call_func(func, *args):
    result = list(map(func, *make_arg_list(*args)))
    assert isinstance(result, list)
    return result


def _to_list(obj):
    if not isinstance(obj, (list, tuple)):
        return [obj]
    else:
        return obj


def add(s1, s2):
    # This handles both strings and lists of strings
    return call_func(operator.add, _to_list(s1), _to_list(s2))
