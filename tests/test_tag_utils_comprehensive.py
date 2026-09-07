
import pytest
from dap_db_manager.tagging.tag.utils import (
    conv_string,
    conv_number,
    conv_string_list,
    conv_number_list,
    conv_default
)

class TestTagUtils:
    """Test suite for tag conversion utilities."""

    def test_conv_string(self):
        """Test conv_string."""
        assert conv_string("test") == "test"
        assert conv_string(["a", "b"]) == "a, b"
        assert conv_string(123) == "123"
        assert conv_string([1, 2]) == "1, 2"
        # Tuple
        assert conv_string(("x", "y")) == "x, y"

    def test_conv_number(self):
        """Test conv_number logic."""
        # Simple numbers
        assert conv_number(1) == 1
        assert conv_number(3.14) == 3.14
        
        # String numbers
        assert conv_number("123") == 123
        assert conv_number(" 456 ") == 456
        assert conv_number("-789") == -789
        assert conv_number("+12") == 12
        assert conv_number("1.5") == 1.5
        
        # Numbers with text suffix (common in tags like "123 bpm")
        assert conv_number("123 bpm") == 123
        assert conv_number("60dB") == 60
        assert conv_number("-9.5 dB") == -9.5
        
        # Lists (takes first valid number?)
        # Logic: conv_string(val) -> join -> then parse
        # ["1", "2"] -> "1, 2" -> "1" -> 1
        assert conv_number(["1", "2"]) == 1
        
        # Invalid
        assert conv_number("abc") == 0
        assert conv_number("") == 0
        
        # Sign handling
        assert conv_number("-") == 0
        assert conv_number("+.5") == 0.5 # or 0? 
        # Logic: sign="+", value=".5", i=0 ('.') -> 0 if not allowed?
        # allowed chars: "1234567890."
        # so "." is valid. value[:0] if . is not allowed?
        # wait value[:i]. find_first_not_of will return index of first non-digit/dot
        # ".5" -> all valid? yes.
        # But int(".5") fails. float(".5") works.
        
        # Complex cases
        assert conv_number("1,000") == 1 # comma is invalid char, stops there
        
    def test_conv_string_list(self):
        """Test conv_string_list."""
        assert conv_string_list("foo") == ["foo"]
        assert conv_string_list(["a", "b"]) == ["a", "b"]
        assert conv_string_list([1, 2]) == ["1", "2"]
        # Nested?
        # Logic: [conv_string(v) for v in value].
        # If value is ["a", ["b", "c"]], then conv_string(["b", "c"]) -> "b, c"
        assert conv_string_list(["a", ["b", "c"]]) == ["a", "b, c"]

    def test_conv_number_list(self):
        """Test conv_number_list."""
        assert conv_number_list("123") == [123]
        assert conv_number_list(["1", "2.5", "3a"]) == [1, 2.5, 3]
        assert conv_number_list(10) == [10]

    def test_conv_default(self):
        """Test conv_default."""
        # Numbers preserved
        assert conv_default(1) == 1
        assert conv_default(2.5) == 2.5
        
        # strings converted to string
        assert conv_default("foo") == "foo"
        
        # lists converted to string
        assert conv_default(["a", "b"]) == "a, b"

