import time
from pathlib import PurePosixPath, PureWindowsPath
from typing import Optional


def mtime_to_fat(mtime: float) -> int:
    """Convert from the mtime returned by os.stat to rockbox's mtime.

    Args:
        mtime: Modification time from os.stat()

    Returns:
        FAT format timestamp as integer (0 if date is before 1980)
    """
    year, month, day, hour, minute, second = time.localtime(mtime)[:-3]

    # FAT timestamps can only represent dates from 1980-2107
    # Return 0 for dates before 1980 (invalid FAT timestamps)
    if year < 1980:
        return 0

    year = year - 1980
    date = 0
    date |= year << 9
    date |= month << 5
    date |= day
    tim = 0
    tim |= hour << 11
    tim |= minute << 5
    tim |= second
    total = (date << 16) | tim
    return total


def fat_to_mtime(fat: int) -> float:
    """Convert from rockbox's mtime to the mtime returned by os.stat.

    Args:
        fat: FAT format timestamp

    Returns:
        Unix timestamp as float
    """
    date = fat >> 16
    tim = fat & 0x0000FFFF
    year = ((date >> 9) & 0x7F) + 1980
    month = (date >> 5) & 0x0F
    day = date & 0x1F
    hour = (tim >> 11) & 0x1F
    minute = (tim >> 5) & 0x3F
    second = tim & 0x1F
    t = time.mktime((year, month, day, hour, minute, second, -1, -1, -1))
    return t


def normalize_dap_path(
    path: Optional[str],
    dap_root: Optional[str] = None,
    mount_point: Optional[str] = None,
) -> Optional[str]:
    """Translate a local filesystem path into the path stored in the database.

    Rockbox stores paths as the device sees them, e.g. ``/<HDD0>/Music/Song.mp3``.
    When generating on a PC the local prefix has to be stripped and the device's
    mount notation prepended.

    Args:
        path: Local path to the file.
        dap_root: Local root to strip, e.g. ``/Volumes/DAP``. Matching is
            case-insensitive, because macOS and Windows filesystems are, and the
            casing a user types for a mount point is not guaranteed to match the
            casing the OS reports. The remainder of the path keeps its original
            case.
        mount_point: Device mount notation to prepend, e.g. ``/<HDD0>``.

    Returns:
        The normalized path, or ``None`` if ``path`` is empty or ``dap_root`` was
        given and ``path`` does not live under it. Callers treat ``None`` as
        "skip this file".
    """
    if not path:
        return None

    normalized = path.replace("\\", "/")

    if dap_root:
        root = str(dap_root).rstrip("/").rstrip("\\").replace("\\", "/")
        if root:
            if not normalized.lower().startswith(root.lower()):
                # Outside the DAP root; the caller cannot produce a device path.
                return None
            normalized = normalized[len(root) :]
    else:
        # No root to strip, so drop any drive letter or anchor instead:
        # "E:\Music\Song.mp3" -> "/Music/Song.mp3".
        path_obj = PureWindowsPath(path) if ":" in path else PurePosixPath(path)
        parts = path_obj.parts[1:] if path_obj.anchor else path_obj.parts
        normalized = str(PurePosixPath(*parts)) if parts else "/"

    if not normalized.startswith("/"):
        normalized = "/" + normalized

    if mount_point:
        normalized = mount_point.rstrip("/") + normalized

    return normalized
