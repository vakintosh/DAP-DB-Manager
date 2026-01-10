"""Integration tests for CLI automation reliability.

Tests that RDBM behaves predictably in automated environments:
- Deterministic output (same input → same output)
- No side effects on input files
- Correct exit codes for different failure modes
"""

import subprocess
import shutil
import hashlib
import pytest
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB

# Test environment paths
TEST_ROOT = Path("./test_automation_env")
INPUT_DIR = TEST_ROOT / "input_music"
OUTPUT_DIR = TEST_ROOT / "output_db"


@pytest.fixture(scope="module")
def test_env():
    """Create a repeatable test environment with real MP3 files."""
    # Clean up any previous test runs
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)

    TEST_ROOT.mkdir()
    INPUT_DIR.mkdir()
    OUTPUT_DIR.mkdir()

    # Create directory structure
    artist_a_dir = INPUT_DIR / "Artist A" / "Album 1"
    artist_b_dir = INPUT_DIR / "Artist B" / "Album 1"
    artist_a_dir.mkdir(parents=True)
    artist_b_dir.mkdir(parents=True)

    # Use actual test files from music_test_folder if available, otherwise skip
    source_music = Path("music_test_folder")
    if source_music.exists():
        # Copy a real MP3 file and modify its tags
        source_files = list(source_music.rglob("*.mp3"))
        if source_files:
            source_mp3 = source_files[0]

            # Artist A - Track 1
            track1_path = artist_a_dir / "track1.mp3"
            shutil.copy2(source_mp3, track1_path)
            audio1 = MP3(track1_path, ID3=ID3)
            if audio1.tags is None:
                audio1.add_tags()
            audio1.tags.add(TIT2(encoding=3, text="Track One"))
            audio1.tags.add(TPE1(encoding=3, text="Artist A"))
            audio1.tags.add(TALB(encoding=3, text="Album 1"))
            audio1.save()

            # Artist B - Track 1
            track2_path = artist_b_dir / "track1.mp3"
            shutil.copy2(source_mp3, track2_path)
            audio2 = MP3(track2_path, ID3=ID3)
            if audio2.tags is None:
                audio2.add_tags()
            audio2.tags.add(TIT2(encoding=3, text="Track One"))
            audio2.tags.add(TPE1(encoding=3, text="Artist B"))
            audio2.tags.add(TALB(encoding=3, text="Album 1"))
            audio2.save()
        else:
            pytest.skip("No MP3 files found in music_test_folder")
    else:
        pytest.skip("music_test_folder not found - skipping integration tests")

    yield {
        "input_dir": INPUT_DIR,
        "output_dir": OUTPUT_DIR,
    }

    # Cleanup after all tests
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)


def hash_dir(directory: Path) -> str:
    """Calculate SHA256 of all files in directory to verify exact output match.

    Args:
        directory: Directory to hash

    Returns:
        SHA256 hexdigest of all files in directory
    """
    sha = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            # Hash filename and content
            sha.update(str(p.relative_to(directory)).encode())
            sha.update(p.read_bytes())
    return sha.hexdigest()


def run_rdbm(args: list, check: bool = False) -> subprocess.CompletedProcess:
    """Run RDBM command with uv.

    Args:
        args: Command arguments (e.g., ["generate", "--music-dir=/path"])
        check: Whether to check return code

    Returns:
        CompletedProcess instance
    """
    cmd = ["uv", "run", "rdbm"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
    )


def test_idempotence(test_env):
    """Test that running RDBM twice produces identical output.

    This ensures deterministic behavior for automation.
    """
    input_dir = test_env["input_dir"]
    output_dir = test_env["output_dir"]

    # Run 1
    result1 = run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            f"--output={output_dir}",
        ],
        check=True,
    )

    assert result1.returncode == 0, "First generation should succeed"
    hash1 = hash_dir(output_dir)

    # Run 2 (overwrite)
    result2 = run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            f"--output={output_dir}",
        ],
        check=True,
    )

    assert result2.returncode == 0, "Second generation should succeed"
    hash2 = hash_dir(output_dir)

    assert hash1 == hash2, (
        "Running twice should produce identical output (deterministic)"
    )


def test_readonly_input(test_env):
    """Test that RDBM never modifies input files.

    Critical for shared NAS environments.
    """
    input_dir = test_env["input_dir"]
    output_dir = test_env["output_dir"]

    # Hash input before generation
    input_hash_before = hash_dir(input_dir)

    # Run generation
    result = run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            f"--output={output_dir}",
        ],
        check=True,
    )

    assert result.returncode == 0, "Generation should succeed"

    # Hash input after generation
    input_hash_after = hash_dir(input_dir)

    assert input_hash_before == input_hash_after, (
        "Input directory must remain untouched (no side effects)"
    )


def test_exit_code_missing_input(test_env):
    """Test that missing input directory returns exit code 10."""
    output_dir = test_env["output_dir"]

    result = run_rdbm(
        [
            "generate",
            "--music-dir=/nonexistent/path",
            f"--output={output_dir}",
        ]
    )

    assert result.returncode == 10, (
        f"Expected exit code 10 (INVALID_INPUT) for missing input, got {result.returncode}"
    )


def test_exit_code_missing_output_parent(test_env):
    """Test that invalid output directory returns exit code 10."""
    input_dir = test_env["input_dir"]

    result = run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            "--output=/nonexistent/deeply/nested/path",
        ]
    )

    # Should fail to create deeply nested output path
    assert result.returncode in (10, 32), (
        f"Expected exit code 10 or 32 for invalid output path, got {result.returncode}"
    )


def test_exit_code_success(test_env):
    """Test that successful generation returns exit code 0."""
    input_dir = test_env["input_dir"]
    output_dir = test_env["output_dir"]

    result = run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            f"--output={output_dir}",
        ],
        check=True,
    )

    assert result.returncode == 0, "Successful generation should return 0"


def test_validate_exit_codes(test_env):
    """Test validate command exit codes."""
    input_dir = test_env["input_dir"]
    output_dir = test_env["output_dir"]

    # Generate database first
    run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            f"--output={output_dir}",
        ],
        check=True,
    )

    # Validate existing database (should succeed with 0)
    result_valid = run_rdbm(["validate", "--db-dir", str(output_dir)])
    assert result_valid.returncode == 0, (
        f"Validating valid database should return 0, got {result_valid.returncode}"
    )

    # Validate non-existent database (should fail with 10)
    result_missing = run_rdbm(["validate", "--db-dir", "/nonexistent/db"])
    assert result_missing.returncode == 10, (
        f"Validating missing database should return 10, got {result_missing.returncode}"
    )


def test_no_hidden_dependencies(test_env):
    """Test that RDBM doesn't rely on current working directory or env vars."""
    input_dir = test_env["input_dir"]
    output_dir = test_env["output_dir"]

    # Run from a different directory
    result = subprocess.run(
        [
            "uv",
            "run",
            "rdbm",
            "generate",
            f"--music-dir={input_dir.absolute()}",
            f"--output={output_dir.absolute()}",
        ],
        cwd="/tmp",  # Run from a completely different directory
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "RDBM should work regardless of current working directory (no implicit cwd usage)"
    )


def test_output_isolation(test_env):
    """Test that RDBM only writes to the specified output directory."""
    input_dir = test_env["input_dir"]
    output_dir = test_env["output_dir"]

    # Track what exists before
    before_files = set(TEST_ROOT.rglob("*"))

    # Run generation
    run_rdbm(
        [
            "generate",
            f"--music-dir={input_dir}",
            f"--output={output_dir}",
        ],
        check=True,
    )

    # Track what exists after
    after_files = set(TEST_ROOT.rglob("*"))

    # New files should only be in output_dir
    new_files = after_files - before_files
    for f in new_files:
        assert output_dir in f.parents or f == output_dir, (
            f"File {f} created outside output directory! RDBM must not create files elsewhere."
        )


if __name__ == "__main__":
    """Allow running as standalone script for quick testing."""
    import sys

    # Create test environment
    print("Setting up test environment...")

    # Use pytest's fixture manually
    class TestEnv:
        def __init__(self):
            if TEST_ROOT.exists():
                shutil.rmtree(TEST_ROOT)

            TEST_ROOT.mkdir()
            INPUT_DIR.mkdir()
            OUTPUT_DIR.mkdir()

            artist_a_dir = INPUT_DIR / "Artist A" / "Album 1"
            artist_b_dir = INPUT_DIR / "Artist B" / "Album 1"
            artist_a_dir.mkdir(parents=True)
            artist_b_dir.mkdir(parents=True)

            # Use actual test files from music_test_folder if available
            source_music = Path("music_test_folder")
            if not source_music.exists():
                print(" Warning: music_test_folder not found - tests may not work")
                sys.exit(1)

            source_files = list(source_music.rglob("*.mp3"))
            if not source_files:
                print(" Warning: No MP3 files found in music_test_folder")
                sys.exit(1)

            source_mp3 = source_files[0]

            # Artist A - Track 1
            track1_path = artist_a_dir / "track1.mp3"
            shutil.copy2(source_mp3, track1_path)
            audio1 = MP3(track1_path, ID3=ID3)
            if audio1.tags is None:
                audio1.add_tags()
            audio1.tags.add(TIT2(encoding=3, text="Track One"))
            audio1.tags.add(TPE1(encoding=3, text="Artist A"))
            audio1.tags.add(TALB(encoding=3, text="Album 1"))
            audio1.save()

            # Artist B - Track 1
            track2_path = artist_b_dir / "track1.mp3"
            shutil.copy2(source_mp3, track2_path)
            audio2 = MP3(track2_path, ID3=ID3)
            if audio2.tags is None:
                audio2.add_tags()
            audio2.tags.add(TIT2(encoding=3, text="Track One"))
            audio2.tags.add(TPE1(encoding=3, text="Artist B"))
            audio2.tags.add(TALB(encoding=3, text="Album 1"))
            audio2.save()

            self.env = {
                "input_dir": INPUT_DIR,
                "output_dir": OUTPUT_DIR,
            }

    test_env_obj = TestEnv()
    env = test_env_obj.env

    try:
        print("\n1. Testing Exit Codes...")
        test_exit_code_missing_input(env)
        print("   ✅ Missing input returns code 10")

        test_exit_code_success(env)
        print("   ✅ Success returns code 0")

        print("\n2. Testing Input Safety...")
        test_readonly_input(env)
        print("   ✅ Input directory untouched")

        print("\n3. Testing Idempotence...")
        test_idempotence(env)
        print("   ✅ Output is deterministic")

        print("\n4. Testing Output Isolation...")
        test_output_isolation(env)
        print("   ✅ Only writes to output directory")

        print("\n5. Testing Validation...")
        test_validate_exit_codes(env)
        print("   ✅ Validate command works correctly")

        print("\n6. Testing No Hidden Dependencies...")
        test_no_hidden_dependencies(env)
        print("   ✅ Works from any directory")

        print("\n" + "=" * 60)
        print("✅ ALL AUTOMATION TESTS PASSED")
        print("=" * 60)
        print("\nRDBM is reliable and ready for automation!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)
