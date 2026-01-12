"""Pydantic schemas for JSON output validation.

This module defines the data structures for all JSON outputs from the CLI.
Using Pydantic ensures consistent, validated, and well-documented JSON responses.

All --json output from CLI commands now uses these Pydantic models which provide:
- Automatic type validation (e.g., entries must be >= 0)
- Consistent JSON structure across all commands
- Clear documentation of expected fields
- Runtime validation to catch programming errors early
- Exclude None values automatically for cleaner output

Commands using Pydantic validation:
- validate: ValidationSuccessResponse | ValidationFailedResponse | ErrorResponse
- load: LoadSuccessResponse | ErrorResponse
- generate: GenerateSuccessResponse | ErrorResponse
- write: WriteSuccessResponse | ErrorResponse
"""

from typing import Optional, Dict, List, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Base Response Models
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response for all commands.

    Attributes:
        status: Always "error" for error responses
        error: Machine-readable error code (e.g., "invalid_input", "data_error")
        message: Human-readable error message
    """

    status: Literal["error"] = "error"
    error: str = Field(
        description="Machine-readable error code",
        examples=["invalid_input", "invalid_config", "data_error", "write_failed"],
    )
    message: str = Field(description="Human-readable error description")


# ============================================================================
# Validate Command Responses
# ============================================================================


class ValidationFailedResponse(BaseModel):
    """Response when validation finds issues.

    Attributes:
        status: Always "invalid"
        errors: List of validation errors found
        warnings: Optional list of warnings (non-fatal issues)
        db_path: Path to the validated database
    """

    status: Literal["invalid"] = "invalid"
    errors: List[str] = Field(description="List of validation errors")
    warnings: Optional[List[str]] = Field(
        default=None, description="Optional warnings (non-fatal issues)"
    )
    db_path: str = Field(description="Path to validated database")


class ValidationSuccessResponse(BaseModel):
    """Response when validation passes.

    Attributes:
        status: Always "valid"
        db_path: Path to the validated database
        entries: Number of entries in the index
        warnings: Optional list of warnings (non-fatal issues)
        tag_counts: Optional counts for each tag file
    """

    status: Literal["valid"] = "valid"
    db_path: str = Field(description="Path to validated database")
    entries: int = Field(ge=0, description="Number of entries in the index")
    warnings: Optional[List[str]] = Field(
        default=None, description="Optional warnings (non-fatal issues)"
    )
    tag_counts: Optional[Dict[str, int]] = Field(
        default=None, description="Counts for each tag file"
    )


# ============================================================================
# Load Command Response
# ============================================================================


class LoadSuccessResponse(BaseModel):
    """Response for successful database load.

    Attributes:
        status: Always "success"
        db_path: Path to the loaded database
        entries: Number of entries in the index
        tag_counts: Counts for each tag file
    """

    status: Literal["success"] = "success"
    db_path: str = Field(description="Path to loaded database")
    entries: int = Field(ge=0, description="Number of entries in the index")
    tag_counts: Dict[str, int] = Field(description="Entry counts per tag file")


# ============================================================================
# Generate Command Responses
# ============================================================================


class GenerateSuccessResponse(BaseModel):
    """Response for successful database generation.

    Attributes:
        status: Either "success" or "completed_with_errors"
        input_dir: Path to source music directory
        output_dir: Path to output database directory
        tracks: Number of tracks in the database
        files_scanned: Total number of files scanned
        files_failed: Number of files that failed to process
        duration_ms: Generation time in milliseconds
        warning: Optional warning message (for high failure rates)

        Plus dynamic tag counts (artist, album, genre, etc.)
    """

    status: Literal["success", "completed_with_errors"]
    input_dir: str = Field(description="Path to source music directory")
    output_dir: str = Field(description="Path to output database directory")
    tracks: int = Field(ge=0, description="Number of tracks in the database")
    files_scanned: int = Field(ge=0, description="Total files scanned")
    files_failed: int = Field(ge=0, description="Files that failed to process")
    duration_ms: int = Field(ge=0, description="Generation time in milliseconds")
    warning: Optional[str] = Field(
        default=None, description="Warning message for high failure rates"
    )

    # Tag counts are added as extra fields
    artist: Optional[int] = Field(default=None, description="Artist tag count")
    album: Optional[int] = Field(default=None, description="Album tag count")
    genre: Optional[int] = Field(default=None, description="Genre tag count")
    title: Optional[int] = Field(default=None, description="Title tag count")
    filename: Optional[int] = Field(default=None, description="Filename tag count")
    composer: Optional[int] = Field(default=None, description="Composer tag count")
    comment: Optional[int] = Field(default=None, description="Comment tag count")
    albumartist: Optional[int] = Field(
        default=None, description="Album artist tag count"
    )
    grouping: Optional[int] = Field(default=None, description="Grouping tag count")

    model_config = {
        "extra": "allow"  # Allow additional fields for tag counts
    }


# ============================================================================
# Write Command Response
# ============================================================================


class WriteSuccessResponse(BaseModel):
    """Response for successful database write/copy.

    Attributes:
        status: Always "success"
        source: Path to source database
        destination: Path to destination database
        entries: Number of entries in the database
    """

    status: Literal["success"] = "success"
    source: str = Field(description="Path to source database")
    destination: str = Field(description="Path to destination database")
    entries: int = Field(ge=0, description="Number of entries")


# ============================================================================
# Update Command Response
# ============================================================================


class UpdateSuccessResponse(BaseModel):
    """Response for successful database update.

    Attributes:
        status: Always "success"
        db_path: Path to original database
        music_dir: Path to music directory scanned
        output_dir: Path where updated database was written
        original_entries: Total number of entries before update
        final_entries: Total number of entries after update (including deleted)
        active_entries: Number of active (non-deleted) entries
        deleted_entries: Number of deleted entries (marked but preserved)
        added: Number of new files added
        renamed: Number of files renamed/moved (statistics preserved)
        deleted: Number of files newly marked as deleted
        unchanged: Number of existing entries preserved
        failed: Number of files that failed to process
        duration_ms: Update duration in milliseconds
    """

    status: Literal["success"] = "success"
    db_path: str = Field(description="Path to original database")
    music_dir: str = Field(description="Path to music directory")
    output_dir: str = Field(description="Path to output database")
    original_entries: int = Field(ge=0, description="Original total entry count")
    final_entries: int = Field(ge=0, description="Final total entry count")
    active_entries: int = Field(ge=0, description="Active (non-deleted) entries")
    deleted_entries: int = Field(ge=0, description="Deleted entries (preserved)")
    added: int = Field(ge=0, description="New files added")
    renamed: int = Field(ge=0, description="Files renamed/moved (statistics preserved)")
    deleted: int = Field(ge=0, description="Files newly marked as deleted")
    unchanged: int = Field(ge=0, description="Existing entries preserved")
    failed: int = Field(ge=0, description="Files that failed to process")
    duration_ms: int = Field(ge=0, description="Update duration (ms)")


# ============================================================================
# Type Unions for Each Command
# ============================================================================

# All possible responses for each command
ValidateResponse = ValidationSuccessResponse | ValidationFailedResponse | ErrorResponse
LoadResponse = LoadSuccessResponse | ErrorResponse
GenerateResponse = GenerateSuccessResponse | ErrorResponse
WriteResponse = WriteSuccessResponse | ErrorResponse
UpdateResponse = UpdateSuccessResponse | ErrorResponse
