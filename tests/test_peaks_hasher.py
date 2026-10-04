from dap_db_manager.peaks.hasher import (
    fnv1a_64,
    hash_track_path,
    normalize_path,
    peaks_filename_for_path,
)


def test_normalize_path_basic() -> None:
    assert (
        normalize_path("Music/Artist/Album/01-Track.mp3")
        == "music/artist/album/01-track.mp3"
    )
    assert (
        normalize_path(r"Music\Artist\Album\01-Track.mp3")
        == "music/artist/album/01-track.mp3"
    )
    assert (
        normalize_path("/Music/Artist/Album/01-Track.mp3")
        == "music/artist/album/01-track.mp3"
    )
    assert normalize_path("  music/artist/track.flac  ") == "music/artist/track.flac"


def test_normalize_path_multiple_leading_slashes() -> None:
    assert normalize_path("///music/artist/track.mp3") == "music/artist/track.mp3"
    assert normalize_path(r"\\\music\artist\track.mp3") == "music/artist/track.mp3"
    assert normalize_path(r" /\\/music/track.mp3 ") == "music/track.mp3"


def test_fnv1a_64_vectors() -> None:
    # Standard FNV-1a 64-bit test vectors
    assert fnv1a_64(b"") == 0xCBF29CE484222325
    assert fnv1a_64(b"a") == 0xAF63DC4C8601EC8C
    assert fnv1a_64(b"foobar") == 0x85944171F73967E8


def test_hash_track_path_format() -> None:
    h = hash_track_path("Music/Soulection/Show 600.mp3")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)
    assert peaks_filename_for_path("Music/Soulection/Show 600.mp3") == f"{h}.peaks"


def test_hash_track_path_normalization_consistency() -> None:
    h1 = hash_track_path("Music/Artist/Song.mp3")
    h2 = hash_track_path(r"  /Music\Artist\Song.mp3  ")
    assert h1 == h2
    assert peaks_filename_for_path("Music/Artist/Song.mp3") == f"{h1}.peaks"
