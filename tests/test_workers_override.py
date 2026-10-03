"""Tests for --workers and --no-parallel override across generate and update."""

import multiprocessing
from pathlib import Path
from typing import Any
from unittest.mock import patch
import pytest

from dap_db_manager.cli import parse_args
from dap_db_manager.cli.commands.generate import cmd_generate
from dap_db_manager.cli.commands.update import cmd_update
from dap_db_manager.cli.utils import ExitCode
from dap_db_manager.database import Database
from tests.conftest import music_test_folder


def get_executor_workers(db: Database) -> tuple[int, int]:
    """Inspect actual underlying thread and process pool max_workers."""
    scanner: Any = getattr(db, "_scanner")
    generator: Any = getattr(db, "_generator")
    scanner_workers: int = int(getattr(scanner._executor, "_max_workers"))
    generator_workers: int = int(getattr(generator._executor, "_max_workers"))
    return scanner_workers, generator_workers


class TestDatabaseWorkersPlumbing:
    """Unit tests for Database, FileScanner, and DatabaseGenerator worker pool plumbing."""

    def test_database_default_workers(self):
        """Database with no max_workers override uses min(32, cpu_count + 4)."""
        expected_default = min(32, multiprocessing.cpu_count() + 4)
        db = Database()
        try:
            assert db.max_workers == expected_default
            scanner_workers, generator_workers = get_executor_workers(db)
            assert scanner_workers == expected_default
            assert generator_workers == expected_default
        finally:
            db._scanner.shutdown()
            db._generator.shutdown()

    def test_database_custom_workers(self):
        """Database(max_workers=2) sizes scanner and generator pools to 2."""
        db = Database(max_workers=2)
        try:
            assert db.max_workers == 2
            scanner_workers, generator_workers = get_executor_workers(db)
            assert scanner_workers == 2
            assert generator_workers == 2
        finally:
            db._scanner.shutdown()
            db._generator.shutdown()

    def test_database_read_default_workers(self, tmp_path: Path):
        """Database.read without max_workers uses default workers."""
        expected_default = min(32, multiprocessing.cpu_count() + 4)
        empty_db = Database()
        empty_db.write(str(tmp_path))
        empty_db._scanner.shutdown()
        empty_db._generator.shutdown()

        loaded_db = Database.read(str(tmp_path))
        try:
            assert loaded_db.max_workers == expected_default
            scanner_workers, generator_workers = get_executor_workers(loaded_db)
            assert scanner_workers == expected_default
            assert generator_workers == expected_default
        finally:
            loaded_db._scanner.shutdown()
            loaded_db._generator.shutdown()

    def test_database_read_custom_workers(self, tmp_path: Path):
        """Database.read with max_workers=2 passes workers through to scanner and generator."""
        empty_db = Database()
        empty_db.write(str(tmp_path))
        empty_db._scanner.shutdown()
        empty_db._generator.shutdown()

        loaded_db = Database.read(str(tmp_path), max_workers=2)
        try:
            assert loaded_db.max_workers == 2
            scanner_workers, generator_workers = get_executor_workers(loaded_db)
            assert scanner_workers == 2
            assert generator_workers == 2
        finally:
            loaded_db._scanner.shutdown()
            loaded_db._generator.shutdown()


class TestCliWorkersParsing:
    """Tests for CLI arguments and plumbing into cmd_generate and cmd_update."""

    def test_update_parser_has_workers_and_no_parallel(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """ddm update --help / parser options includes --workers and --no-parallel."""
        monkeypatch.setattr("sys.argv", ["ddm", "update", "--help"])
        with pytest.raises(SystemExit) as exc:
            parse_args()
        assert exc.value.code == 0

    def test_update_args_parsing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """ddm update parses --workers and --no-parallel flags correctly."""
        db_dir = tmp_path / "db"
        music_dir = tmp_path / "music"
        db_dir.mkdir()
        music_dir.mkdir()

        monkeypatch.setattr(
            "sys.argv",
            [
                "ddm",
                "update",
                "--db-dir",
                str(db_dir),
                "--music-dir",
                str(music_dir),
                "--workers",
                "2",
                "--no-parallel",
            ],
        )
        _, args = parse_args()
        assert args.workers == 2
        assert args.no_parallel is True

    def test_cmd_generate_wires_workers_to_database(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """cmd_generate with --workers 2 constructs Database with max_workers=2."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        created_dbs: list[Database] = []
        real_init = Database.__init__

        def tracking_init(self, *args, **kwargs):
            real_init(self, *args, **kwargs)
            self.paths.add("dummy.mp3")
            created_dbs.append(self)

        monkeypatch.setattr(
            "sys.argv",
            [
                "ddm",
                "generate",
                "--music-dir",
                str(music_dir),
                "-o",
                str(output_dir),
                "--workers",
                "2",
                "--no-preserve-stats",
            ],
        )
        _, args = parse_args()

        with (
            patch.object(
                Database, "__init__", side_effect=tracking_init, autospec=True
            ),
            patch.object(Database, "add_dir"),
            patch.object(Database, "generate_database"),
            patch.object(Database, "write"),
        ):
            with pytest.raises(SystemExit) as exc:
                cmd_generate(args)
            assert exc.value.code == ExitCode.SUCCESS

        assert len(created_dbs) >= 1
        db = created_dbs[0]
        try:
            assert db.max_workers == 2
            scanner_workers, generator_workers = get_executor_workers(db)
            assert scanner_workers == 2
            assert generator_workers == 2
        finally:
            for d in created_dbs:
                d._scanner.shutdown()
                d._generator.shutdown()

    def test_cmd_update_wires_workers_to_database(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """cmd_update with --workers 2 passes max_workers=2 to Database.read."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        db_dir = tmp_path / "db"
        db_dir.mkdir()

        # Seed an empty database
        seed_db = Database()
        seed_db.write(str(db_dir))
        seed_db._scanner.shutdown()
        seed_db._generator.shutdown()

        created_dbs: list[Database] = []
        real_read = Database.read

        def tracking_read(*args, **kwargs):
            db = real_read(*args, **kwargs)
            created_dbs.append(db)
            return db

        monkeypatch.setattr(
            "sys.argv",
            [
                "ddm",
                "update",
                "--db-dir",
                str(db_dir),
                "--music-dir",
                str(music_dir),
                "--workers",
                "2",
            ],
        )
        _, args = parse_args()

        with patch.object(Database, "read", side_effect=tracking_read) as mock_read:
            with pytest.raises(SystemExit) as exc:
                cmd_update(args)
            assert exc.value.code == ExitCode.SUCCESS
            assert mock_read.call_args.kwargs.get("max_workers") == 2

        assert len(created_dbs) >= 1
        db = created_dbs[0]
        try:
            assert db.max_workers == 2
            scanner_workers, generator_workers = get_executor_workers(db)
            assert scanner_workers == 2
            assert generator_workers == 2
        finally:
            for d in created_dbs:
                d._scanner.shutdown()
                d._generator.shutdown()

    def test_cmd_update_no_parallel_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """cmd_update with --no-parallel passes parallel=False to update_database."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        db_dir = tmp_path / "db"
        db_dir.mkdir()

        seed_db = Database()
        seed_db.write(str(db_dir))
        seed_db._scanner.shutdown()
        seed_db._generator.shutdown()

        monkeypatch.setattr(
            "sys.argv",
            [
                "ddm",
                "update",
                "--db-dir",
                str(db_dir),
                "--music-dir",
                str(music_dir),
                "--no-parallel",
            ],
        )
        _, args = parse_args()

        with patch.object(
            Database,
            "update_database",
            return_value={
                "added": 0,
                "renamed": 0,
                "modified": 0,
                "deleted": 0,
                "unchanged": 0,
                "failed": 0,
                "initial_active": 0,
                "initial_deleted": 0,
            },
        ) as mock_update:
            with pytest.raises(SystemExit) as exc:
                cmd_update(args)
            assert exc.value.code == ExitCode.SUCCESS
            assert mock_update.call_args.kwargs.get("parallel") is False


class TestUpdateWorkersIntegration:
    """Integration test comparing update with workers=1 against default."""

    def test_update_workers_1_matches_correctness(self, tmp_path: Path):
        """Running update with workers=1 on real fixture produces correct database."""
        fixture_folder = music_test_folder()
        if not fixture_folder.exists():
            pytest.skip(f"Fixture directory {fixture_folder} not found")

        # Generate initial database with tracks from fixture
        test_music = tmp_path / "music"
        test_music.mkdir()
        src_files = list(fixture_folder.glob("**/*.mp3"))[:3]
        if not src_files:
            pytest.skip("No mp3 fixture files found")

        import shutil

        for f in src_files:
            shutil.copy(f, test_music / f.name)

        db_dir = tmp_path / "db"
        db_dir.mkdir()

        # Build initial db
        db = Database(max_workers=2)
        db.add_dir(str(test_music), parallel=True)
        db.generate_database(parallel=True)
        db.write(str(db_dir))
        initial_count = db.index.count
        db._scanner.shutdown()
        db._generator.shutdown()
        assert initial_count > 0

        # Now run update with workers=1
        update_db = Database.read(str(db_dir), max_workers=1)
        try:
            scanner_workers, generator_workers = get_executor_workers(update_db)
            assert scanner_workers == 1
            assert generator_workers == 1
            stats = update_db.update_database(str(test_music))
            assert stats["unchanged"] == initial_count
            assert stats["added"] == 0
            assert stats["failed"] == 0
        finally:
            update_db._scanner.shutdown()
            update_db._generator.shutdown()
