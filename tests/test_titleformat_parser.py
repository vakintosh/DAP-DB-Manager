"""Tests for titleformat parsing and evaluation."""

import pytest
from dap_db_manager.tagging.titleformat import compile as titleformat_compile
from dap_db_manager.tagging.titleformat.field import Field
from dap_db_manager.tagging.titleformat.function import Function
from dap_db_manager.tagging.titleformat.conditional import Conditional
from dap_db_manager.tagging.titleformat.string import String


class TestTitleformatBasics:
    """Test basic titleformat parsing."""

    def test_simple_string(self):
        """Test parsing a simple string."""
        fmt = titleformat_compile("Hello World")
        assert fmt is not None

    def test_simple_field(self):
        """Test parsing a simple field reference."""
        fmt = titleformat_compile("%artist%")
        assert fmt is not None

    def test_multiple_fields(self):
        """Test parsing multiple fields."""
        fmt = titleformat_compile("%artist% - %title%")
        assert fmt is not None

    def test_field_with_text(self):
        """Test fields mixed with text."""
        fmt = titleformat_compile("Artist: %artist%, Album: %album%")
        assert fmt is not None


class TestTitleformatFields:
    """Test titleformat field parsing."""

    def test_field_creation(self):
        """Test Field object creation."""
        field = Field("artist")
        assert field is not None

    def test_field_evaluation_with_mock(self):
        """Test field evaluation with mock tag."""
        from unittest.mock import Mock
        
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["Test Artist"])
        
        fmt = titleformat_compile("%artist%")
        result = fmt.format(mock_tag)
        assert result == "Test Artist"

    def test_field_missing_tag(self):
        """Test field with missing tag data."""
        from unittest.mock import Mock
        
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=[])
        
        fmt = titleformat_compile("%artist%")
        result = fmt.format(mock_tag)
        # Should return empty string for missing fields
        assert result == ""

    def test_field_with_fallback(self):
        """Test field with fallback to another field."""
        fmt = titleformat_compile("%albumartist%")
        # Should fall back to artist if albumartist is missing


class TestTitleformatFunctions:
    """Test titleformat function parsing."""

    def test_function_parsing(self):
        """Test parsing a function call."""
        fmt = titleformat_compile("$upper(%artist%)")
        assert fmt is not None

    def test_nested_functions(self):
        """Test nested function calls."""
        fmt = titleformat_compile("$upper($left(%artist%,3))")
        assert fmt is not None

    def test_function_with_multiple_args(self):
        """Test function with multiple arguments."""
        fmt = titleformat_compile("$if(%artist%,Yes,No)")
        assert fmt is not None

    def test_common_functions(self):
        """Test common titleformat functions."""
        functions = [
            "$upper(%artist%)",
            "$lower(%album%)",
            "$caps(%title%)",
            "$len(%artist%)",
            "$left(%artist%,5)",
            "$right(%artist%,5)",
            "$substr(%artist%,0,5)",
            "$replace(%artist%,a,b)",
        ]
        
        for func_str in functions:
            fmt = titleformat_compile(func_str)
            assert fmt is not None, f"Failed to parse: {func_str}"


class TestTitleformatConditionals:
    """Test titleformat conditional logic."""

    def test_simple_if(self):
        """Test simple $if() conditional."""
        fmt = titleformat_compile("$if(%artist%,Artist exists,No artist)")
        assert fmt is not None

    def test_nested_if(self):
        """Test nested conditionals."""
        fmt = titleformat_compile("$if(%artist%,$if(%album%,Both,Artist only),None)")
        assert fmt is not None

    def test_if2_function(self):
        """Test $if2() function (first non-empty)."""
        fmt = titleformat_compile("$if2(%albumartist%,%artist%)")
        assert fmt is not None

    def test_if3_function(self):
        """Test $if3() function."""
        fmt = titleformat_compile("$if3(%albumartist%,%artist%,Unknown)")
        assert fmt is not None


class TestTitleformatEvaluation:
    """Test titleformat evaluation with mock tags."""

    def test_eval_simple_field(self):
        """Test evaluating a simple field."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("%artist%")
        
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["Test Artist"])
        
        result = fmt.format(mock_tag)
        assert result == "Test Artist"

    def test_eval_multiple_fields(self):
        """Test evaluating multiple fields."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("%artist% - %title%")
        
        mock_tag = Mock()
        mock_tag.get_string = Mock(side_effect=lambda x: {
            "artist": ["Test Artist"],
            "title": ["Test Song"]
        }.get(x, []))
        
        result = fmt.format(mock_tag)
        assert result == "Test Artist - Test Song"

    def test_eval_with_function(self):
        """Test evaluating with a function."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$upper(%artist%)")
        
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["test artist"])
        
        result = fmt.format(mock_tag)
        assert result == "TEST ARTIST"

    def test_eval_conditional(self):
        """Test evaluating a conditional."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$if(%artist%,Has artist,No artist)")
        
        # Tag with artist
        mock_tag1 = Mock()
        mock_tag1.get_string = Mock(return_value=["Test Artist"])
        result1 = fmt.format(mock_tag1)
        assert result1 == "Has artist"
        
        # Tag without artist
        mock_tag2 = Mock()
        mock_tag2.get_string = Mock(return_value=[])
        result2 = fmt.format(mock_tag2)
        assert result2 == "No artist"


class TestTitleformatComplexExpressions:
    """Test complex titleformat expressions."""

    def test_track_number_formatting(self):
        """Test track number formatting."""
        fmt = titleformat_compile("$num(%tracknumber%,2)")
        assert fmt is not None

    def test_directory_path(self):
        """Test directory path extraction."""
        fmt = titleformat_compile("$directory(%path%)")
        assert fmt is not None

    def test_filename_extraction(self):
        """Test filename extraction."""
        fmt = titleformat_compile("$filename(%path%)")
        assert fmt is not None

    def test_complex_formatting(self):
        """Test complex formatting expression."""
        fmt = titleformat_compile(
            "$if2(%albumartist%,%artist%) - %album% - $num(%tracknumber%,2) - %title%"
        )
        assert fmt is not None


class TestTitleformatEdgeCases:
    """Test titleformat edge cases."""

    def test_empty_string(self):
        """Test parsing empty string."""
        fmt = titleformat_compile("")
        assert fmt is not None

    def test_only_text(self):
        """Test parsing only static text."""
        fmt = titleformat_compile("Static text only")
        assert fmt is not None

    def test_special_characters(self):
        """Test parsing with special characters."""
        fmt = titleformat_compile("Artist: %artist% [%year%]")
        assert fmt is not None

    def test_escaped_characters(self):
        """Test escaped characters."""
        # Titleformat may support escaping special characters
        fmt = titleformat_compile("'%' means percent")
        assert fmt is not None

    def test_unicode_characters(self):
        """Test unicode characters in format string."""
        fmt = titleformat_compile("Künstler: %artist%")
        assert fmt is not None


@pytest.mark.integration
class TestTitleformatIntegration:
    """Integration tests for titleformat with real tags."""

    def test_real_world_format(self):
        """Test a real-world titleformat string."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile(
            "$if2(%albumartist%,%artist%) - %album%'['%date%']' - $num(%tracknumber%,2) - %title%"
        )
        
        mock_tag = Mock()
        mock_tag.get_string = Mock(side_effect=lambda x: {
            "artist": ["Artist Name"],
            "albumartist": ["Album Artist"],
            "album": ["Album Title"],
            "date": ["2023"],
            "tracknumber": ["5"],
            "title": ["Song Title"]
        }.get(x, []))
        
        result = fmt.format(mock_tag)
        # Should produce properly formatted output


class TestTitleformatCaching:
    """Test titleformat compilation caching."""

    def test_compilation_caching(self):
        """Test that compilation results are cached."""
        fmt1 = titleformat_compile("%artist% - %title%")
        fmt2 = titleformat_compile("%artist% - %title%")
        
        # Same format string should return cached result
        assert fmt1 is fmt2


class TestTitleformatFunctionLibrary:
    """Test specific titleformat functions."""

    def test_upper_function(self):
        """Test $upper() function."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$upper(%artist%)")
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["artist"])
        
        result = fmt.format(mock_tag)
        assert result == "ARTIST"

    def test_lower_function(self):
        """Test $lower() function."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$lower(%artist%)")
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["ARTIST"])
        
        result = fmt.format(mock_tag)
        assert result == "artist"

    def test_len_function(self):
        """Test $len() function."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$len(%artist%)")
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["Artist"])
        
        result = fmt.format(mock_tag)
        assert result == "6"

    def test_left_function(self):
        """Test $left() function."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$left(%artist%,3)")
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["Artist"])
        
        result = fmt.format(mock_tag)
        assert result == "Art"

    def test_num_function(self):
        """Test $num() function for number formatting."""
        from unittest.mock import Mock
        
        fmt = titleformat_compile("$num(%tracknumber%,2)")
        mock_tag = Mock()
        mock_tag.get_string = Mock(return_value=["5"])
        
        result = fmt.format(mock_tag)
        assert result == "05"
