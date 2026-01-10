"""Configuration management for Rockbox Database Manager.

Handles saving and loading user preferences including format strings,
window positions, and last used directories.
"""

import copy
import tomllib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import psutil as psutil_module
    import tomli_w
else:
    try:
        import psutil as psutil_module
    except ImportError:
        psutil_module = None

    try:
        import tomli_w
    except ImportError:
        tomli_w = None


def get_optimal_cache_memory_mb() -> int:
    """Calculate optimal cache memory based on available system RAM.

    Formula:
    - Systems with < 4GB RAM: 256 MB (conservative)
    - Systems with 4-8GB RAM: 512 MB (balanced)
    - Systems with 8-16GB RAM: 1024 MB (generous)
    - Systems with > 16GB RAM: 2048 MB (maximum performance)

    Returns:
        Optimal cache memory in megabytes
    """
    if psutil_module is None:
        # Fallback if psutil not available
        return 512

    try:
        # Get total system memory in MB
        total_ram_mb = psutil_module.virtual_memory().total / (1024 * 1024)

        # Calculate based on tiers
        if total_ram_mb < 4096:  # < 4GB
            return 256
        elif total_ram_mb < 8192:  # 4-8GB
            return 512
        elif total_ram_mb < 16384:  # 8-16GB
            return 1024
        else:  # > 16GB
            return 2048
    except Exception:
        # Fallback on any error
        return 512


def get_config_dir() -> Path:
    """Get the configuration directory.

    Returns:
        Path to config directory (~/.rdbm on all platforms)
    """
    config_dir = Path.home() / ".rdbm"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the full path to the config file."""
    return get_config_dir() / ".rdbm_config.toml"


class Config:
    """Configuration manager for application settings."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "window": {
            "width": 800,
            "height": 600,
            "x": -1,  # -1 means let system decide
            "y": -1,
        },
        "paths": {
            "last_music_dir": "",
            "last_output_dir": "",
            "last_tags_file": "",
        },
        "database": {
            # Database version: 16 (only supported version)
            # Version 16 is for recent Rockbox builds
            "version": 16,
            # Rockbox mount notation (e.g., "/<HDD0>", "/<MMC0>")
            # Auto-detected on first generate/update if not set
            # Set to empty string for no mount notation
            "mount_notation": "",
            # Tracks whether mount notation has been auto-detected/configured
            # Used to trigger automatic detection on first run
            "mount_notation_configured": False,
        },
        "performance": {
            # Maximum memory usage for tag cache in megabytes
            # Set to None for automatic detection based on system RAM
            # Manual values: 256-2048 MB recommended
            # Auto-detection: 256MB (<4GB RAM), 512MB (4-8GB), 1024MB (8-16GB), 2048MB (>16GB)
            "tag_cache_memory_mb": None,  # Auto-detect by default
        },
        "formats": {
            # Default format strings for each field
            "artist": "%artist%",
            "album": "%album%",
            "genre": "%genre%",
            "composer": "%composer%",
        },
        "sort_formats": {
            # Default sort format strings
            "artist": "",
            "album": "",
            "genre": "",
            "composer": "",
        },
    }

    def __init__(self):
        """Initialize configuration manager."""
        self.config_path = get_config_path()
        self.data: Dict[str, Any] = copy.deepcopy(
            self.DEFAULT_CONFIG
        )  # Deep copy to avoid modifying class default
        self._dirty = False  # Track if config has been modified
        self.load()

    def load(self) -> bool:
        """Load configuration from file.

        Returns:
            True if loaded successfully, False if file doesn't exist or error occurred
        """
        if not self.config_path.exists():
            return False

        try:
            with open(self.config_path, "rb") as f:
                loaded_data = tomllib.load(f)
                # Merge with defaults (in case new keys were added)
                self._merge_config(self.data, loaded_data)
            self._dirty = False  # Config is clean after loading
            return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False

    def save(self, force: bool = False) -> bool:
        """Save configuration to file.

        Args:
            force: If True, save even if config hasn't been modified

        Returns:
            True if saved successfully, False otherwise
        """
        if not force and not self._dirty:
            # No changes to save
            return True

        if tomli_w is None:
            print("Warning: TOML writer not available, config not saved")
            return False

        try:
            # Filter out None values that TOML can't serialize
            config_to_save = self._filter_none_values(self.data)
            with open(self.config_path, "wb") as f:
                tomli_w.dump(config_to_save, f)
            self._dirty = False  # Clear dirty flag after successful save
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _filter_none_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively filter out None values from config dict for TOML serialization.

        TOML doesn't support None/null values, so we filter them out.
        When loading, missing values will revert to defaults.
        """
        filtered = {}
        for key, value in data.items():
            if value is None:
                continue
            elif isinstance(value, dict):
                filtered_dict = self._filter_none_values(value)
                if filtered_dict:  # Only include non-empty dicts
                    filtered[key] = filtered_dict
            else:
                filtered[key] = value
        return filtered

    def is_dirty(self) -> bool:
        """Check if configuration has been modified.

        Returns:
            True if config has unsaved changes, False otherwise
        """
        return self._dirty

    # Window settings
    def get_window_size(self) -> Tuple[int, int]:
        """Get saved window size."""
        return (self.data["window"]["width"], self.data["window"]["height"])

    def set_window_size(self, width: int, height: int) -> None:
        """Save window size."""
        self.data["window"]["width"] = width
        self.data["window"]["height"] = height
        self._dirty = True

    def get_window_position(self) -> Tuple[int, int]:
        """Get saved window position."""
        return (self.data["window"]["x"], self.data["window"]["y"])

    def set_window_position(self, x: int, y: int) -> None:
        """Save window position."""
        self.data["window"]["x"] = x
        self.data["window"]["y"] = y
        self._dirty = True

    # Path settings
    def get_last_music_dir(self) -> str:
        """Get last used music directory."""
        return str(self.data["paths"]["last_music_dir"])

    def set_last_music_dir(self, path: str) -> None:
        """Save last used music directory."""
        self.data["paths"]["last_music_dir"] = path
        self._dirty = True

    def get_last_output_dir(self) -> str:
        """Get last used output directory."""
        return str(self.data["paths"]["last_output_dir"])

    def set_last_output_dir(self, path: str) -> None:
        """Save last used output directory."""
        self.data["paths"]["last_output_dir"] = path
        self._dirty = True

    def get_last_tags_file(self) -> str:
        """Get last used tags file."""
        return str(self.data["paths"]["last_tags_file"])

    def set_last_tags_file(self, path: str) -> None:
        """Save last used tags file."""
        self.data["paths"]["last_tags_file"] = path
        self._dirty = True

    # Format settings
    def get_format(self, field: str) -> str:
        """Get format string for a field."""
        return str(self.data["formats"].get(field, f"%{field}%"))

    def set_format(self, field: str, format_str: str) -> None:
        """Save format string for a field."""
        self.data["formats"][field] = format_str
        self._dirty = True

    def get_sort_format(self, field: str) -> str:
        """Get sort format string for a field."""
        return str(self.data["sort_formats"].get(field, ""))

    def set_sort_format(self, field: str, format_str: str) -> None:
        """Save sort format string for a field."""
        self.data["sort_formats"][field] = format_str
        self._dirty = True

    def get_all_formats(self) -> Dict[str, str]:
        """Get all format strings."""
        formats: Dict[str, str] = self.data["formats"].copy()
        return formats

    def get_all_sort_formats(self) -> Dict[str, str]:
        """Get all sort format strings."""
        formats: Dict[str, str] = self.data["sort_formats"].copy()
        return formats

    # Database settings
    def get_database_version(self) -> int:
        """Get database version (16 only).

        Returns:
            Database version number (defaults to 16 if not configured)
        """
        return int(self.data.get("database", {}).get("version", 16))

    def set_database_version(self, version: int) -> None:
        """Set database version.

        Args:
            version: Database version (16 only)
        """
        if "database" not in self.data:
            self.data["database"] = {}
        self.data["database"]["version"] = version
        self._dirty = True

    def get_mount_notation(self) -> str:
        """Get Rockbox mount notation.

        Returns:
            Mount notation string (e.g., "/<HDD0>") or empty string if not set
        """
        return str(self.data.get("database", {}).get("mount_notation", ""))

    def set_mount_notation(self, notation: str) -> None:
        """Set Rockbox mount notation and mark as configured.

        Args:
            notation: Mount notation (e.g., "/<HDD0>", "/<MMC0>") or empty string
        """
        if "database" not in self.data:
            self.data["database"] = {}
        self.data["database"]["mount_notation"] = notation
        self.data["database"]["mount_notation_configured"] = True
        self._dirty = True

    def is_mount_notation_configured(self) -> bool:
        """Check if mount notation has been configured.

        Returns:
            True if mount notation has been set (manually or auto-detected)
        """
        return bool(
            self.data.get("database", {}).get("mount_notation_configured", False)
        )

    def auto_detect_mount_notation(
        self, device_path: str, callback=None
    ) -> Optional[str]:
        """Automatically detect and configure mount notation from device.

        Args:
            device_path: Path to device root or .rockbox directory
            callback: Optional callback for logging messages

        Returns:
            Detected mount notation or None if detection failed
        """
        from .database.mount_detector import MountDetector

        try:
            if callback:
                callback("Auto-detecting Rockbox mount notation...")

            # Use storage-based detection (source of truth)
            mounts = MountDetector.detect_from_device_storage(device_path)

            if mounts:
                notation = mounts[0]  # Primary mount
                self.set_mount_notation(notation)
                self.save()

                if callback:
                    callback(f"✓ Detected mount notation: {notation}")
                    if len(mounts) > 1:
                        callback(f"  Additional mounts: {', '.join(mounts[1:])}")
                    callback(f"  Saved to config: {get_config_path()}")

                return notation
            else:
                if callback:
                    callback(
                        "⚠ Could not detect mount notation - using default /<HDD0>"
                    )
                # Set default and mark as configured
                self.set_mount_notation("/<HDD0>")
                self.save()
                return "/<HDD0>"

        except Exception as e:
            if callback:
                callback(f"⚠ Mount detection failed: {e}")
                callback("  Using default /<HDD0>")
            # Set default and mark as configured to avoid retrying
            self.set_mount_notation("/<HDD0>")
            self.save()
            return "/<HDD0>"

    # Performance settings
    def get_tag_cache_memory(self) -> int:
        """Get maximum tag cache memory in MB.

        If not explicitly configured (None), automatically calculates
        based on available system RAM.

        Returns:
            Maximum memory in megabytes
        """
        configured_value = self.data.get("performance", {}).get("tag_cache_memory_mb")

        # If None or not set, auto-detect
        if configured_value is None:
            return get_optimal_cache_memory_mb()

        return int(configured_value)

    def set_tag_cache_memory(self, memory_mb: int) -> None:
        """Set maximum tag cache memory.

        Args:
            memory_mb: Maximum memory in megabytes (recommended: 256-2048)

        Raises:
            ValueError: If memory_mb is less than 100
        """
        if memory_mb < 100:
            raise ValueError("Cache memory must be at least 100 MB")
        if "performance" not in self.data:
            self.data["performance"] = {}
        self.data["performance"]["tag_cache_memory_mb"] = memory_mb
        self._dirty = True
