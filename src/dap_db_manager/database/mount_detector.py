"""Mount notation detection for Rockbox databases.

This module provides functionality to detect and analyze Rockbox's internal
mount notation (e.g., /<HDD0>, /<HDD1>, /<MMC0>) using multiple methods:

Detection Methods (in order of reliability):
1. Storage-based: Analyzes actual device partitions (SOURCE OF TRUTH)
   - Queries OS for partition information (diskutil on macOS, lsblk on Linux)
   - Counts accessible FAT32/exFAT partitions
   - Determines storage type (HDD vs MMC) from device target

2. Database-based: Analyzes existing Rockbox database paths
   - Reads database_4.tcd to extract path mount prefixes
   - Useful when device is not mounted but database is available

3. Fallback: Uses device type hints from rockbox-info.txt
   - Infers mount notation from Target field (ipod→HDD, sansa→MMC)
   - Least accurate, used only when other methods unavailable

Storage Type Mapping:
- HDD devices: /<HDD0>, /<HDD1>, ... (iPod, iRiver, Gigabeat, hard drives)
- MMC devices: /<MMC0>, /<MMC1>, ... (Sansa, Clip, Fuze, SD card devices)

Usage:
    # Analyze device storage (most accurate)
    mounts = MountDetector.detect_from_device_storage("/Volumes/IPOD")
    # Returns: ["/<HDD0>"] or ["/<HDD0>", "/<HDD1>"] for multi-partition

    # Analyze existing database
    mounts = MountDetector.detect_mounts("/path/to/.rockbox")

    # Get suggested notation
    notation = MountDetector.suggest_mount_notation("/Volumes/IPOD")
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..tagging.tag.tagfile import TagFile


# Rockbox mount notation patterns
# Examples: /<HDD0>, /<HDD1>, /<MMC0>, /<MMC1>
MOUNT_PATTERN = re.compile(r"^/<([A-Z]+\d+)>/")


class MountInfo:
    """Information about a detected mount point."""

    def __init__(self, notation: str, count: int, sample_paths: List[str]):
        """Initialize mount information.

        Args:
            notation: Mount notation (e.g., "/<HDD0>")
            count: Number of paths using this mount
            sample_paths: Sample paths using this mount
        """
        self.notation = notation
        self.count = count
        self.sample_paths = sample_paths[:5]  # Keep first 5 samples

    def __repr__(self):
        return f"MountInfo(notation={self.notation!r}, count={self.count})"

    def __str__(self):
        return f"{self.notation} ({self.count} files)"


class MountDetector:
    """Detects and analyzes Rockbox mount notation from existing databases."""

    @staticmethod
    def detect_from_device_storage(device_root: str) -> List[str]:
        """Detect mount notations by analyzing device storage structure.

        This is the source of truth - analyzes the actual device filesystem
        and partition structure to determine what Rockbox mount points exist.

        Args:
            device_root: Path to device root (e.g., /Volumes/IPOD)

        Returns:
            List of detected mount notations (e.g., ["/<HDD0>", "/<HDD1>"])
            Empty list if detection fails
        """
        import subprocess
        import platform

        device_path = Path(device_root)
        if not device_path.exists():
            logging.warning("Device root does not exist: %s", device_root)
            return []

        # Determine storage type (HDD vs MMC) from rockbox-info.txt
        storage_prefix = "HDD"  # Default
        rockbox_path = device_path / ".rockbox"
        info_file = rockbox_path / "rockbox-info.txt"

        if info_file.exists():
            try:
                content = info_file.read_text(errors="ignore")
                if "Target:" in content:
                    for line in content.split("\n"):
                        if line.startswith("Target:"):
                            target = line.split(":", 1)[1].strip().lower()
                            # SD card devices use MMC notation
                            if any(
                                x in target for x in ["sansa", "clip", "fuze", "e200"]
                            ):
                                storage_prefix = "MMC"
                            break
            except Exception as e:
                logging.debug("Failed to read rockbox-info.txt: %s", e)

        # Analyze partitions based on OS
        try:
            if platform.system() == "Darwin":  # macOS
                # Use diskutil to get device node
                result = subprocess.run(
                    ["diskutil", "info", str(device_root)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    # Extract device node (e.g., /dev/disk2s1)
                    device_node = None
                    for line in result.stdout.split("\n"):
                        if "Device Node:" in line:
                            device_node = line.split(":", 1)[1].strip()
                            break

                    if device_node:
                        # Get the base disk (e.g., /dev/disk2 from /dev/disk2s1)
                        import re

                        match = re.match(r"(/dev/disk\d+)", device_node)
                        if match:
                            base_disk = match.group(1)

                            # List all partitions on this disk
                            result = subprocess.run(
                                ["diskutil", "list", base_disk],
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )

                            if result.returncode == 0:
                                # Count FAT32/exFAT partitions (Rockbox-accessible)
                                fat_partitions = []
                                for line in result.stdout.split("\n"):
                                    if "disk" in line and (
                                        "FAT" in line or "DOS" in line
                                    ):
                                        # Extract partition identifier
                                        parts = line.split()
                                        for part in parts:
                                            if re.match(r"disk\d+s\d+", part):
                                                fat_partitions.append(part)

                                # Generate mount notations
                                mounts = []
                                for i, _ in enumerate(fat_partitions):
                                    mounts.append(f"/<{storage_prefix}{i}>")

                                if mounts:
                                    logging.info(
                                        "Detected %d partition(s): %s",
                                        len(mounts),
                                        ", ".join(mounts),
                                    )
                                    return mounts

            elif platform.system() == "Linux":
                # Use lsblk to analyze partitions
                # First, find the device from the mount point
                result = subprocess.run(
                    ["findmnt", "-n", "-o", "SOURCE", str(device_root)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    device_node = result.stdout.strip()

                    # Get the base device (e.g., /dev/sdb from /dev/sdb1)
                    import re

                    match = re.match(r"(/dev/[a-z]+)", device_node)
                    if match:
                        base_device = match.group(1)

                        # List all partitions with filesystem type
                        result = subprocess.run(
                            ["lsblk", "-n", "-o", "NAME,FSTYPE", base_device],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )

                        if result.returncode == 0:
                            # Count FAT/exFAT partitions
                            fat_partitions = []
                            for line in result.stdout.split("\n"):
                                if any(
                                    fs in line.lower()
                                    for fs in ["vfat", "fat32", "exfat", "fat16"]
                                ):
                                    fat_partitions.append(line.strip())

                            # Generate mount notations
                            mounts = []
                            for i, _ in enumerate(fat_partitions):
                                mounts.append(f"/<{storage_prefix}{i}>")

                            if mounts:
                                logging.info(
                                    "Detected %d partition(s): %s",
                                    len(mounts),
                                    ", ".join(mounts),
                                )
                                return mounts

            elif platform.system() == "Windows":
                # On Windows, typically one drive letter = one partition/volume
                # Check if the path is a drive root (e.g., E:\)
                import os

                drive = os.path.splitdrive(str(device_root))[0]

                if drive:
                    # Windows devices typically present as single volume
                    # even with iFlash boards (handled by firmware)
                    mounts = [f"/<{storage_prefix}0>"]
                    logging.info(
                        "Detected Windows drive %s: %s", drive, ", ".join(mounts)
                    )
                    return mounts

        except Exception as e:
            logging.debug("Failed to analyze device partitions: %s", e)

        # Fallback: single volume assumption
        logging.info("Defaulting to single volume: /<{storage_prefix}0>")
        return [f"/<{storage_prefix}0>"]

    @staticmethod
    def detect_from_rockbox_info(rockbox_dir: str) -> Optional[str]:
        """Try to detect mount notation from rockbox-info.txt or device structure.

        DEPRECATED: Use detect_from_device_storage() instead for accurate detection.
        This method only provides hints based on device type, not actual storage analysis.

        Args:
            rockbox_dir: Path to .rockbox directory or device root

        Returns:
            Detected mount notation (e.g., "/<HDD0>") or None if cannot detect
        """
        from pathlib import Path

        rockbox_path = Path(rockbox_dir)

        # If given .rockbox directory, go up to device root
        if rockbox_path.name == ".rockbox":
            device_root = rockbox_path.parent
        else:
            device_root = rockbox_path
            rockbox_path = device_root / ".rockbox"

        # Use the new accurate detection method
        mounts = MountDetector.detect_from_device_storage(str(device_root))
        return mounts[0] if mounts else None

    @staticmethod
    def suggest_mount_notation(rockbox_dir: Optional[str] = None) -> str:
        """Suggest a mount notation based on device storage analysis.

        This method analyzes the actual device partition structure to provide
        accurate mount notation, making it the source of truth over database-based
        detection.

        Args:
            rockbox_dir: Optional path to .rockbox directory or device root

        Returns:
            Suggested mount notation (defaults to "/<HDD0>")
        """
        if rockbox_dir:
            # Determine device root
            rockbox_path = Path(rockbox_dir)
            if rockbox_path.name == ".rockbox":
                device_root = str(rockbox_path.parent)
            else:
                device_root = rockbox_dir

            # Use storage-based detection (source of truth)
            mounts = MountDetector.detect_from_device_storage(device_root)
            if mounts:
                return mounts[0]

        # Default to most common mount notation for single-volume devices
        return "/<HDD0>"

    @staticmethod
    def detect_mounts(db_dir: str) -> Dict[str, MountInfo]:
        """Detect mount notations from existing database.

        Reads the path tagfile (database_4.tcd) and analyzes all paths
        to determine which Rockbox mount notations are in use.

        Args:
            db_dir: Path to .rockbox database directory

        Returns:
            Dictionary mapping mount notation to MountInfo objects
            Example: {"/<HDD0>": MountInfo(...), "/<HDD1>": MountInfo(...)}

        Raises:
            FileNotFoundError: If database path file doesn't exist
            ValueError: If path file is corrupted
        """
        db_path = Path(db_dir)
        path_file = db_path / "database_4.tcd"

        if not path_file.exists():
            raise FileNotFoundError(
                f"Database path file not found: {path_file}\n"
                f"Make sure {db_dir} contains a valid Rockbox database."
            )

        logging.info("Detecting mount notation from %s", path_file)

        # Read the path tagfile
        try:
            path_tagfile = TagFile.read(str(path_file), is_path=True)
        except Exception as e:
            raise ValueError(f"Failed to read database path file: {e}")

        # Analyze all paths
        mount_data: Dict[str, List[str]] = {}  # mount notation -> list of sample paths
        paths_without_mount = []

        for entry in path_tagfile.entries:
            path = entry.data

            # Try to extract mount notation
            match = MOUNT_PATTERN.match(path)
            if match:
                mount_name = match.group(1)  # e.g., "HDD0"
                mount_notation = f"/<{mount_name}>"

                if mount_notation not in mount_data:
                    mount_data[mount_notation] = []
                mount_data[mount_notation].append(path)
            else:
                # Path doesn't have mount notation
                paths_without_mount.append(path)

        # Create MountInfo objects
        mounts = {}
        for notation, paths in mount_data.items():
            mounts[notation] = MountInfo(
                notation=notation,
                count=len(paths),
                sample_paths=paths[:10],  # Keep first 10 samples
            )

        # Log results
        if mounts:
            logging.info("Detected %d mount point(s):", len(mounts))
            for mount_info in mounts.values():
                logging.info("  %s - %d files", mount_info.notation, mount_info.count)
                for sample in mount_info.sample_paths[:3]:
                    logging.debug("    Sample: %s", sample)
        else:
            logging.warning("No mount notation detected in database paths")

        if paths_without_mount:
            logging.info(
                "%d paths without mount notation (e.g., %s)",
                len(paths_without_mount),
                paths_without_mount[0] if paths_without_mount else "none",
            )

        return mounts

    @staticmethod
    def extract_mount_prefix(path: str) -> Tuple[Optional[str], str]:
        """Extract mount notation prefix from a path.

        Args:
            path: Path to analyze (e.g., "/<HDD0>/Music/Song.mp3")

        Returns:
            Tuple of (mount_notation, path_without_mount)
            Example: ("/<HDD0>", "/Music/Song.mp3")
            If no mount notation found: (None, original_path)
        """
        match = MOUNT_PATTERN.match(path)
        if match:
            mount_name = match.group(1)
            mount_notation = f"/<{mount_name}>"
            path_without_mount = path[len(mount_notation) :]
            return (mount_notation, path_without_mount)
        return (None, path)

    @staticmethod
    def get_primary_mount(db_dir: str) -> Optional[str]:
        """Get the primary (most common) mount notation from database.

        Args:
            db_dir: Path to .rockbox database directory

        Returns:
            Primary mount notation (e.g., "/<HDD0>") or None if no mounts detected
        """
        try:
            mounts = MountDetector.detect_mounts(db_dir)
            if not mounts:
                return None

            # Return the mount with the most files
            primary = max(mounts.values(), key=lambda m: m.count)
            return primary.notation
        except Exception as e:
            logging.error("Failed to detect primary mount: %s", e)
            return None

    @staticmethod
    def print_mount_summary(db_dir: str) -> None:
        """Print a human-readable summary of detected mounts.

        Args:
            db_dir: Path to .rockbox database directory
        """
        try:
            mounts = MountDetector.detect_mounts(db_dir)

            if not mounts:
                print("No Rockbox mount notation detected in database.")
                print("Paths appear to use simple format (e.g., /Music/...)")
                return

            print(f"\nDetected {len(mounts)} mount point(s):\n")

            for mount_info in sorted(
                mounts.values(), key=lambda m: m.count, reverse=True
            ):
                print(f"  {mount_info.notation}")
                print(f"    Files: {mount_info.count}")
                print("    Samples:")
                for sample in mount_info.sample_paths[:3]:
                    print(f"      {sample}")
                print()

            if len(mounts) > 1:
                print("⚠ Multiple mount points detected!")
                print(
                    "  This device has multi-volume storage (e.g., internal + SD card)"
                )
                print(
                    "  When updating the database, files will be mapped to the correct mount."
                )

        except FileNotFoundError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error detecting mounts: {e}")
