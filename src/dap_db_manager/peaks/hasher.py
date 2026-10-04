"""Path normalization and 64-bit FNV-1a hashing for sidecar cache matching."""

FNV1A_64_OFFSET: int = 0xCBF29CE484222325
FNV1A_64_PRIME: int = 0x100000001B3
MASK_64: int = 0xFFFFFFFFFFFFFFFF


def normalize_path(path: str) -> str:
    """Normalize a track path: forward slashes, lowercase, stripped leading slash and whitespace.

    Args:
        path: File path string to normalize.

    Returns:
        Normalized relative path string in lowercase with forward slashes.
    """
    cleaned = path.strip().replace("\\", "/")
    cleaned = cleaned.lstrip("/")
    return cleaned.lower()


def fnv1a_64(data: bytes) -> int:
    """Compute 64-bit FNV-1a hash over raw bytes.

    Args:
        data: Byte sequence to hash.

    Returns:
        64-bit unsigned integer hash value.
    """
    val = FNV1A_64_OFFSET
    for byte in data:
        val ^= byte
        val = (val * FNV1A_64_PRIME) & MASK_64
    return val


def hash_track_path(path: str) -> str:
    """Return 16-character lowercase hex string for normalized path.

    Args:
        path: Track file path string.

    Returns:
        16-character lowercase hexadecimal hash.
    """
    normalized = normalize_path(path)
    h = fnv1a_64(normalized.encode("utf-8"))
    return f"{h:016x}"


def peaks_filename_for_path(path: str) -> str:
    """Return filename with .peaks extension for track path.

    Args:
        path: Track file path string.

    Returns:
        Peaks cache filename formatted as '<16-hex-hash>.peaks'.
    """
    return f"{hash_track_path(path)}.peaks"
