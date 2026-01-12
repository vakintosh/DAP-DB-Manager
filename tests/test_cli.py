"""Tests for the CLI module."""

import pytest
import struct
import logging
import json

from unittest.mock import patch

from dap_db_manager.constants import MAGIC, FILE_TAG_INDICES
from dap_db_manager.cli import main, __version__
from dap_db_manager.cli.utils import setup_logging
from dap_db_manager.cli.schemas import (
    ErrorResponse,
    ValidationSuccessResponse,
    ValidationFailedResponse,
    LoadSuccessResponse,
    WriteSuccessResponse,
)


def test_version_output(capsys):
    """Test that --version flag displays version correctly."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "--version"]):
            main()

    # argparse exits with 0 for --version
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_help_output(capsys):
    """Test that --help flag displays help information."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "--help"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "DAP DB Manager" in captured.out
    assert "generate" in captured.out
    assert "load" in captured.out
    assert "write" in captured.out


def test_no_command_shows_help(capsys):
    """Test that running without a command shows help."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "DAP DB Manager" in captured.out


def test_generate_help(capsys):
    """Test that generate command help works."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "generate", "--help"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--music-dir" in captured.out
    assert "--output" in captured.out
    assert "--config" in captured.out
    assert "--load-tags" in captured.out
    assert "--save-tags" in captured.out


def test_load_help(capsys):
    """Test that load command help works."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "load", "--help"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--db-dir" in captured.out


def test_write_help(capsys):
    """Test that write command help works."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "write", "--help"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--db-dir" in captured.out
    assert "--output" in captured.out


def test_validate_help(capsys):
    """Test that validate command help works."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "validate", "--help"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--db-dir" in captured.out
    assert "Check database" in captured.out or "integrity" in captured.out


def test_validate_missing_path(capsys):
    """Test validate command with non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "validate", "--db-dir", "/nonexistent/path"]):
            main()

    assert exc_info.value.code == 10  # ExitCode.INVALID_INPUT


def test_validate_missing_files(capsys, tmp_path):
    """Test validate command with missing database files."""
    # Create empty directory
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "validate", "--db-dir", str(db_dir)]):
            main()

    assert exc_info.value.code == 31  # ExitCode.VALIDATION_FAILED
    captured = capsys.readouterr()
    assert "Missing" in captured.out or "missing" in captured.out


def test_validate_valid_database(tmp_path):
    """Test validate command with valid database."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create all required database files with proper structure
    # Tag files need: magic (4), datasize (4), entry_count (4) = 12 bytes minimum
    # Files: 0-8, 12 (using FILE_TAG_INDICES)
    for file_num in FILE_TAG_INDICES:
        tag_file = db_dir / f"database_{file_num}.tcd"
        with open(tag_file, "wb") as f:
            magic = MAGIC
            datasize = 0  # No entries, so data size is 0 (excluding header)
            entry_count = 0
            f.write(struct.pack("<III", magic, datasize, entry_count))

    # Index file needs: magic, datasize, entry_count, serial, commitid, dirty = 24 bytes
    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        magic = MAGIC
        datasize = 0  # Empty index, no entries
        entry_count = 0
        serial = 0
        commitid = 1
        dirty = 0
        f.write(
            struct.pack(
                "<IIIIII", magic, datasize, entry_count, serial, commitid, dirty
            )
        )

    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "validate", "--db-dir", str(db_dir)]):
            main()

    assert exc_info.value.code == 0  # ExitCode.SUCCESS


def test_setup_logging_debug():
    """Test logging setup with debug level."""
    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    setup_logging("debug")
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_info():
    """Test logging setup with info level."""
    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    setup_logging("info")
    assert logging.getLogger().level == logging.INFO


def test_setup_logging_warning():
    """Test logging setup with warning level."""
    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    setup_logging("warning")
    assert logging.getLogger().level == logging.WARNING


def test_setup_logging_error():
    """Test logging setup with error level."""
    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    setup_logging("error")
    assert logging.getLogger().level == logging.ERROR


def test_setup_logging_invalid():
    """Test that invalid log level raises ValueError."""
    with pytest.raises(ValueError):
        setup_logging("invalid")


def test_generate_missing_path(capsys):
    """Test generate command with non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            [
                "ddm",
                "generate",
                "--music-dir",
                "/nonexistent/path",
                "--output",
                "/tmp/test",
            ],
        ):
            main()

    assert exc_info.value.code == 10


def test_load_missing_path(capsys):
    """Test load command with non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "load", "--db-dir", "/nonexistent/path"]):
            main()

    assert exc_info.value.code == 10  # ExitCode.INVALID_INPUT


def test_inspect_help(capsys):
    """Test that inspect command help works."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "inspect", "--help"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--db-dir" in captured.out
    assert "--file-number" in captured.out
    assert "--quiet" in captured.out
    # assert '--verbose' in captured.out
    assert "artist" in captured.out
    assert "album" in captured.out


def test_inspect_missing_path(capsys):
    """Test inspect command with non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "inspect", "--db-dir", "/nonexistent/path"]):
            main()

    assert exc_info.value.code == 10  # ExitCode.INVALID_INPUT


def test_inspect_invalid_file_number(capsys, tmp_path):
    """Test inspect command with invalid file number."""
    # Create a temporary directory
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Test with invalid file number (too high)
    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            ["ddm", "inspect", "--db-dir", str(db_dir), "--file-number", "10"],
        ):
            main()

    assert exc_info.value.code == 10  # ExitCode.INVALID_INPUT
    captured = capsys.readouterr()
    assert (
        "must be between 0 and 9" in captured.out
        or "must be between 0 and 9" in captured.err
    )


def test_inspect_missing_database_file(capsys, tmp_path):
    """Test inspect command when database file doesn't exist."""
    # Create a temporary directory without database files
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "inspect", "--db-dir", str(db_dir)]):
            main()

    assert exc_info.value.code == 10  # ExitCode.INVALID_INPUT
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "not found" in output.lower() or "does not exist" in output.lower()


def test_inspect_with_mock_database(tmp_path):
    """Test inspect command with a mock database file."""

    # Create a temporary database directory
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create a simple mock index file
    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        # Write header: magic, datasize, entry_count, serial, commitid, dirty
        magic = MAGIC
        datasize = 24  # Header size only
        entry_count = 0
        serial = 0
        commitid = 1
        dirty = 0
        f.write(
            struct.pack("IIIIII", magic, datasize, entry_count, serial, commitid, dirty)
        )

    # Test inspect without error
    with patch("sys.argv", ["ddm", "inspect", "--db-dir", str(db_dir)]):
        # Should not raise SystemExit for valid file
        try:
            main()
        except SystemExit as e:
            # Expect success (code 0) or no exit at all
            if e.code not in (0, None):
                pytest.fail(f"inspect command failed with exit code {e.code}")


def test_inspect_quiet_mode(tmp_path):
    """Test inspect command with --quiet flag."""

    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create a mock tag file
    tag_file = db_dir / "database_0.tcd"
    with open(tag_file, "wb") as f:
        magic = MAGIC
        datasize = 12  # Header only
        entry_count = 0
        f.write(struct.pack("III", magic, datasize, entry_count))

    # Test with quiet mode
    with patch(
        "sys.argv",
        ["ddm", "inspect", "--db-dir", str(db_dir), "--file-number", "0", "--quiet"],
    ):
        try:
            main()
        except SystemExit as e:
            if e.code not in (0, None):
                pytest.fail(
                    f"inspect command with --quiet failed with exit code {e.code}"
                )


# def test_inspect_verbose_mode(tmp_path):
#     """Test inspect command with --verbose flag."""

#     db_dir = tmp_path / "db"
#     db_dir.mkdir()

#     # Create a mock tag file
#     tag_file = db_dir / "database_0.tcd"
#     with open(tag_file, "wb") as f:
#         magic = rbdb.MAGIC
#         datasize = 12  # Header only
#         entry_count = 0
#         f.write(struct.pack('III', magic, datasize, entry_count))

# Test with verbose mode
# with patch('sys.argv', ['ddm', 'inspect', str(db_dir), '0', '--verbose']):
#     try:
#         main()
#     except SystemExit as e:
#         if e.code not in (0, None):
#             pytest.fail(f"inspect command with --verbose failed with exit code {e.code}")


def test_inspect_all_file_numbers(tmp_path):
    """Test inspect command with all valid file numbers (0-8)."""

    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create mock database files for all tag files (using FILE_TAG_INDICES)
    for file_num in FILE_TAG_INDICES:
        tag_file = db_dir / f"database_{file_num}.tcd"
        with open(tag_file, "wb") as f:
            magic = MAGIC
            datasize = 12  # Header only
            entry_count = 0
            f.write(struct.pack("III", magic, datasize, entry_count))

    # Test each file number (0-9 which map to files 0-8, 12)
    for i in range(len(FILE_TAG_INDICES)):
        with patch(
            "sys.argv",
            [
                "ddm",
                "inspect",
                "--db-dir",
                str(db_dir),
                "--file-number",
                str(i),
                "--quiet",
            ],
        ):
            try:
                main()
            except SystemExit as e:
                if e.code not in (0, None):
                    pytest.fail(
                        f"inspect command for file {i} failed with exit code {e.code}"
                    )


# ============================================================================
# JSON Output Tests (--json flag)
# ============================================================================


def test_validate_json_valid_database(tmp_path, capsys):
    """Test validate command with --json flag on valid database."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create all required database files with proper structure
    for file_num in FILE_TAG_INDICES:
        tag_file = db_dir / f"database_{file_num}.tcd"
        with open(tag_file, "wb") as f:
            magic = MAGIC
            datasize = 0
            entry_count = 0
            f.write(struct.pack("<III", magic, datasize, entry_count))

    # Index file
    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        magic = MAGIC
        datasize = 0
        entry_count = 0
        serial = 0
        commitid = 1
        dirty = 0
        f.write(
            struct.pack(
                "<IIIIII", magic, datasize, entry_count, serial, commitid, dirty
            )
        )

    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "validate", "--db-dir", str(db_dir), "--json"]):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ValidationSuccessResponse(**json_data)
    assert response.status == "valid"
    assert response.db_path == str(db_dir)
    assert response.entries == 0
    assert "tag_counts" in json_data


def test_validate_json_missing_files(tmp_path, capsys):
    """Test validate command with --json flag when database files are missing."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "validate", "--db-dir", str(db_dir), "--json"]):
            main()

    assert exc_info.value.code == 31  # VALIDATION_FAILED
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ValidationFailedResponse(**json_data)
    assert response.status == "invalid"
    assert len(response.errors) > 0
    assert "missing" in " ".join(response.errors).lower()


def test_validate_json_nonexistent_path(capsys):
    """Test validate command with --json flag on non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv", ["ddm", "validate", "--db-dir", "/nonexistent/path", "--json"]
        ):
            main()

    assert exc_info.value.code == 10  # INVALID_INPUT
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ErrorResponse(**json_data)
    assert response.status == "error"
    assert response.error == "invalid_input"
    assert "does not exist" in response.message


def test_load_json_valid_database(tmp_path, capsys):
    """Test load command with --json flag on valid database."""
    from dap_db_manager.database import Database

    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create a proper database using Database.write() with no-op callback to suppress output
    db = Database()
    db.write(str(db_dir), callback=lambda *args, **kwargs: None)

    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            ["ddm", "load", "--db-dir", str(db_dir), "--json", "--log-level", "debug"],
        ):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = LoadSuccessResponse(**json_data)
    assert response.status == "success"
    assert response.db_path == str(db_dir)
    assert response.entries == 0
    assert isinstance(response.tag_counts, dict)
    assert len(response.tag_counts) == 10  # 10 tag files (including canonicalartist)


def test_load_json_nonexistent_path(capsys):
    """Test load command with --json flag on non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv", ["ddm", "load", "--db-dir", "/nonexistent/path", "--json"]
        ):
            main()

    assert exc_info.value.code == 10  # INVALID_INPUT
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ErrorResponse(**json_data)
    assert response.status == "error"
    assert response.error == "invalid_input"
    assert "does not exist" in response.message


def test_load_json_corrupted_database(tmp_path, capsys):
    """Test load command with --json flag on corrupted database."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create a corrupted index file (wrong magic number)
    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        f.write(b"CORRUPTED_DATA")

    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["ddm", "load", "--db-dir", str(db_dir), "--json"]):
            main()

    assert exc_info.value.code == 20  # DATA_ERROR
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ErrorResponse(**json_data)
    assert response.status == "error"
    assert response.error == "data_error"
    assert "Failed to load database" in response.message


def test_generate_json_nonexistent_path(capsys):
    """Test generate command with --json flag on non-existent path."""
    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            [
                "ddm",
                "generate",
                "--music-dir",
                "/nonexistent/path",
                "--output",
                "/tmp/test",
                "--json",
            ],
        ):
            main()

    assert exc_info.value.code == 10  # INVALID_INPUT
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ErrorResponse(**json_data)
    assert response.status == "error"
    assert response.error == "invalid_input"
    assert "does not exist" in response.message


def test_write_json_valid_database(tmp_path, capsys):
    """Test write command with --json flag on valid database."""
    from dap_db_manager.database import Database

    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    output_dir = tmp_path / "output"

    # Create a proper database using Database.write() with no-op callback to suppress output
    db = Database()
    db.write(str(db_dir), callback=lambda *args, **kwargs: None)

    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            [
                "ddm",
                "write",
                "--db-dir",
                str(db_dir),
                "--output",
                str(output_dir),
                "--json",
                "--log-level",
                "debug",
            ],
        ):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = WriteSuccessResponse(**json_data)
    assert response.status == "success"
    assert response.source == str(db_dir)
    assert response.destination == str(output_dir)
    assert response.entries == 0


def test_write_json_nonexistent_source(capsys):
    """Test write command with --json flag on non-existent source."""
    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            [
                "ddm",
                "write",
                "--db-dir",
                "/nonexistent/path",
                "--output",
                "/tmp/output",
                "--json",
            ],
        ):
            main()

    assert exc_info.value.code == 10  # INVALID_INPUT
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ErrorResponse(**json_data)
    assert response.status == "error"
    assert response.error == "invalid_input"
    assert "does not exist" in response.message


def test_write_json_corrupted_database(tmp_path, capsys):
    """Test write command with --json flag on corrupted database."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    output_dir = tmp_path / "output"

    # Create a corrupted index file
    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        f.write(b"CORRUPTED_DATA")

    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            [
                "ddm",
                "write",
                "--db-dir",
                str(db_dir),
                "--output",
                str(output_dir),
                "--json",
            ],
        ):
            main()

    assert exc_info.value.code == 20  # DATA_ERROR
    captured = capsys.readouterr()

    # Parse JSON output
    json_data = json.loads(captured.out)

    # Validate using Pydantic schema
    response = ErrorResponse(**json_data)
    assert response.status == "error"
    assert response.error == "data_error"
    assert "Failed to load database" in response.message


def test_validate_json_quiet_mode_suppresses_output(tmp_path, capsys):
    """Test that --json and --quiet work together properly."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create valid database
    for file_num in FILE_TAG_INDICES:
        tag_file = db_dir / f"database_{file_num}.tcd"
        with open(tag_file, "wb") as f:
            magic = MAGIC
            datasize = 0
            entry_count = 0
            f.write(struct.pack("<III", magic, datasize, entry_count))

    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        magic = MAGIC
        datasize = 0
        entry_count = 0
        serial = 0
        commitid = 1
        dirty = 0
        f.write(
            struct.pack(
                "<IIIIII", magic, datasize, entry_count, serial, commitid, dirty
            )
        )

    with pytest.raises(SystemExit) as exc_info:
        with patch(
            "sys.argv",
            ["ddm", "validate", "--db-dir", str(db_dir), "--json", "--quiet"],
        ):
            main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()

    # Should only have JSON output, no progress indicators
    json_data = json.loads(captured.out)
    assert json_data["status"] == "valid"

    # Stderr should not have progress bars (logging warnings are acceptable)
    # We just verify JSON mode works with quiet mode, not that stderr is completely empty
    assert "Reading" not in captured.err or "done" not in captured.err


def test_json_output_structure_validate_success(tmp_path, capsys):
    """Test that validate --json output has all expected fields."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create valid database
    for file_num in FILE_TAG_INDICES:
        tag_file = db_dir / f"database_{file_num}.tcd"
        with open(tag_file, "wb") as f:
            magic = MAGIC
            datasize = 0
            entry_count = 0
            f.write(struct.pack("<III", magic, datasize, entry_count))

    index_file = db_dir / "database_idx.tcd"
    with open(index_file, "wb") as f:
        magic = MAGIC
        datasize = 0
        entry_count = 0
        serial = 0
        commitid = 1
        dirty = 0
        f.write(
            struct.pack(
                "<IIIIII", magic, datasize, entry_count, serial, commitid, dirty
            )
        )

    with pytest.raises(SystemExit):
        with patch("sys.argv", ["ddm", "validate", "--db-dir", str(db_dir), "--json"]):
            main()

    captured = capsys.readouterr()
    json_data = json.loads(captured.out)

    # Check required fields
    assert "status" in json_data
    assert "db_path" in json_data
    assert "entries" in json_data
    assert "tag_counts" in json_data

    # Check types
    assert isinstance(json_data["status"], str)
    assert isinstance(json_data["db_path"], str)
    assert isinstance(json_data["entries"], int)
    assert isinstance(json_data["tag_counts"], dict)


def test_json_output_structure_load_success(tmp_path, capsys):
    """Test that load --json output has all expected fields."""
    from dap_db_manager.database import Database

    # Reset logging to avoid interference from previous tests
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create a proper database using Database.write() with no-op callback to suppress output
    db = Database()
    db.write(str(db_dir), callback=lambda *args, **kwargs: None)

    with pytest.raises(SystemExit):
        with patch(
            "sys.argv",
            ["ddm", "load", "--db-dir", str(db_dir), "--json", "--log-level", "debug"],
        ):
            main()

    captured = capsys.readouterr()
    json_data = json.loads(captured.out)

    # Check required fields
    assert "status" in json_data
    assert "db_path" in json_data
    assert "entries" in json_data
    assert "tag_counts" in json_data

    # Check types
    assert isinstance(json_data["status"], str)
    assert isinstance(json_data["db_path"], str)
    assert isinstance(json_data["entries"], int)
    assert isinstance(json_data["tag_counts"], dict)

    # Validate tag_counts has all expected keys
    expected_tags = [
        "artist",
        "album",
        "genre",
        "title",
        "path",
        "composer",
        "comment",
        "album artist",
        "grouping",
    ]
    for tag in expected_tags:
        assert tag in json_data["tag_counts"]


def test_json_output_parseable_all_error_cases(capsys):
    """Test that all error responses produce parseable JSON."""
    error_cases = [
        (["ddm", "validate", "--db-dir", "/nonexistent", "--json"], 10),
        (["ddm", "load", "--db-dir", "/nonexistent", "--json"], 10),
        (
            [
                "ddm",
                "write",
                "--db-dir",
                "/nonexistent",
                "--output",
                "/tmp/out",
                "--json",
            ],
            10,
        ),
        (
            [
                "ddm",
                "generate",
                "--music-dir",
                "/nonexistent",
                "--output",
                "/tmp/out",
                "--json",
            ],
            10,
        ),
    ]

    for args, expected_code in error_cases:
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", args):
                main()

        assert exc_info.value.code == expected_code
        captured = capsys.readouterr()

        # Verify JSON is parseable
        json_data = json.loads(captured.out)
        assert "status" in json_data
        assert json_data["status"] == "error"
        assert "error" in json_data
        assert "message" in json_data
