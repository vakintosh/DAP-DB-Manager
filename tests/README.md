# Tests for DAP DB Manager

This directory contains unit tests for the core functionality.

## Running Tests

### Using UV (recommended)

```bash
# Install dev dependencies (includes pytest)
cd /path/to/dap-db-manager
uv sync --group dev

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_utils.py

# Run specific test class
uv run pytest tests/test_tagfile.py::TestTagFile

# Run specific test
uv run pytest tests/test_tagfile.py::TestTagFile::test_tagfile_creation
```

### Using pytest directly

```bash
# From project root
pytest

# With verbose output
pytest -v

# With coverage
pytest --cov=dap_db_manager --cov-report=html
```

## Test Structure

- `test_utils.py` - Tests for utility functions (time conversions)
- `test_tagfile.py` - Tests for TagFile and TagEntry classes
- `test_indexfile.py` - Tests for IndexFile and IndexEntry classes
- `test_database.py` - Tests for Database class and operations
- `conftest.py` - Pytest configuration and shared fixtures
- `test_cli.py` - Tests for command-line interface functions

## Writing New Tests

Follow these conventions:

1. **File naming**: `test_<module_name>.py`
2. **Class naming**: `Test<FeatureName>`
3. **Function naming**: `test_<what_it_tests>`
4. **Docstrings**: Every test should have a brief docstring

Example:

```python
class TestMyFeature:
    """Test MyFeature functionality."""

    def test_basic_operation(self):
        """Test that basic operation works."""
        result = my_function()
        assert result == expected_value
```

## Coverage

After running tests with coverage, open `htmlcov/index.html` in a browser to see detailed coverage report.

Target: 80%+ coverage for core modules.

## Continuous Integration

Tests should be run automatically on every commit via GitHub Actions (to be set up).
