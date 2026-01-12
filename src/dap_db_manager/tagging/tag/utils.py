"""Utility functions for tag conversion and manipulation."""

from typing import Any, Union, List


def conv_string(value: Any) -> str:
    """Convert a value to a comma-separated string."""
    if not isinstance(value, (list, tuple)):
        value = [value]
    return ", ".join(str(v) for v in value)


def conv_number(value: Any) -> Union[int, float]:
    """Convert a value to a number (int or float)."""
    if isinstance(value, (int, float)):
        return value
    value = conv_string(value)

    def find_first_not_of(str_val: str, chars: str) -> int:
        """Find the first character not in the given set."""
        for i, c in enumerate(str_val):
            if c not in chars:
                return i
        return len(str_val)

    # Chop to the last non-numeric value
    value = value.strip()
    sign = ""
    if value.startswith("-") or value.startswith("+"):
        sign = value[0]
        value = value[1:]
    i = find_first_not_of(value, "1234567890.")
    value = sign + value[:i]

    # Convert
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return 0


def conv_string_list(value: Any) -> List[str]:
    """Convert a value to a list of strings."""
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [conv_string(v) for v in value]


def conv_number_list(value: Any) -> List[Union[int, float]]:
    """Convert a value to a list of numbers."""
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [conv_number(v) for v in value]


def conv_default(value: Any) -> Union[int, float, str]:
    """Default conversion: preserve numbers, convert others to strings."""
    if isinstance(value, (int, float)):
        return value
    return conv_string(value)
