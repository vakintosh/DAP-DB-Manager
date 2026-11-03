"""DSD (DSF/DFF) support and ID3-in-container formats (AIFF/WAVE/DSF/DFF).

Rockbox upstream f4c7e8b59 (in 2026-10 builds) added DSF/DFF playback and
indexes ``.dsf``/``.dff`` files in its database scan, so DDM must index them
too. Both store tags as a raw ID3 chunk -- like AIFF and WAVE -- which needs
explicit frame mappings (EasyID3 names do not apply).
"""

import shutil
import struct
import subprocess

import pytest
from mutagen.aiff import AIFF
from mutagen.dsdiff import DSDIFF
from mutagen.dsf import DSF
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.id3 import COMM, TALB, TCOM, TCON, TDRC, TIT1, TIT2, TPE1, TPE2, TPOS, TRCK

from dap_db_manager.tagging.tag import SUPPORTED_EXTENSIONS, read

_DATA = b"\x69" * 4096  # one 4096-byte block of DSD "silence", 1 channel


def _write_dsf(path):
    fmt = struct.pack(
        "<4sQIIIIIIQII", b"fmt ", 52, 1, 0, 1, 1, 2822400, 1, len(_DATA) * 8, 4096, 0
    )
    data = struct.pack("<4sQ", b"data", 12 + len(_DATA)) + _DATA
    total = 28 + len(fmt) + len(data)
    path.write_bytes(struct.pack("<4sQQQ", b"DSD ", 28, total, 0) + fmt + data)
    return DSF


def _chunk(ck_id, body):
    return (
        ck_id + struct.pack(">Q", len(body)) + body + (b"\0" if len(body) % 2 else b"")
    )


def _write_dff(path):
    prop = (
        b"SND "
        + _chunk(b"FS  ", struct.pack(">I", 2822400))
        + _chunk(b"CHNL", struct.pack(">H", 1) + b"SLFT")
        + _chunk(b"CMPR", b"DSD " + b"\x0enot compressed\0")
    )
    body = (
        b"DSD "
        + _chunk(b"FVER", struct.pack(">I", 0x01050000))
        + _chunk(b"PROP", prop)
        + _chunk(b"DSD ", _DATA)
    )
    path.write_bytes(_chunk(b"FRM8", body))
    return DSDIFF


def _write_aiff(path):
    # 1 channel, 8 frames of 16-bit silence
    comm = struct.pack(">hIh", 1, 8, 16) + b"\x40\x0e\xac\x44" + b"\0" * 6  # 44100 Hz
    ssnd = struct.pack(">II", 0, 0) + b"\0" * 16
    form = b"AIFF" + b"COMM" + struct.pack(">I", len(comm)) + comm
    form += b"SSND" + struct.pack(">I", len(ssnd)) + ssnd
    path.write_bytes(b"FORM" + struct.pack(">I", len(form)) + form)
    return AIFF


FRAMES = [
    TIT2(encoding=3, text="Halo"),
    TPE1(encoding=3, text="Beyonce"),
    TALB(encoding=3, text="I Am... Sasha Fierce"),
    TPE2(encoding=3, text="Beyonce"),
    TCON(encoding=3, text="Pop"),
    TCOM(encoding=3, text="Ryan Tedder"),
    COMM(encoding=3, lang="eng", desc="", text="A comment"),
    TIT1(encoding=3, text="My Group"),
    TRCK(encoding=3, text="3/12"),
    TPOS(encoding=3, text="1/2"),
    TDRC(encoding=3, text="2008"),
]

EXPECTED = {
    "title": ["Halo"],
    "artist": ["Beyonce"],
    "album": ["I Am... Sasha Fierce"],
    "album artist": ["Beyonce"],
    "genre": ["Pop"],
    "composer": ["Ryan Tedder"],
    "comment": ["A comment"],
    "grouping": ["My Group"],
    "tracknumber": ["3"],
    "discnumber": ["1"],
    "date": ["2008"],
}


@pytest.fixture(
    params=[("t.dsf", _write_dsf), ("t.dff", _write_dff), ("t.aiff", _write_aiff)]
)
def tagged_file(request, tmp_path):
    name, writer = request.param
    path = tmp_path / name
    cls = writer(path)
    audio = cls(str(path))
    audio.add_tags()
    for frame in FRAMES:
        audio.tags.add(frame)
    audio.save()
    return path


def test_dsd_extensions_are_supported():
    assert {".dsf", ".dff"} <= SUPPORTED_EXTENSIONS


def test_all_text_fields_are_read(tagged_file):
    tag = read(str(tagged_file))
    assert tag is not None, f"{tagged_file.name} not recognized"
    got = {field: tag.get_string(field) for field in EXPECTED}
    assert got == EXPECTED


def test_length_and_bitrate_are_read(tagged_file):
    tag = read(str(tagged_file))
    assert float(tag.get_string("length")[0]) > 0
    assert int(float(tag.get_string("bitrate")[0])) > 0


# --- Vorbis-comment DESCRIPTION as comment (Rockbox upstream ab64e2653) -----
#
# Rockbox reads DESCRIPTION as the comment in Vorbis comments (what ffmpeg,
# SoX, beets and mutagen write); when both COMMENT and DESCRIPTION exist, the
# first one in the file wins.

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is not installed"
)


def _make_vorbis_file(path, codec_args):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "0.1",
            *codec_args,
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(
    params=[
        ("t.flac", ["-c:a", "flac"], FLAC),
        ("t.ogg", ["-c:a", "vorbis", "-strict", "-2", "-ac", "2"], OggVorbis),
    ],
    ids=["flac", "ogg"],
)
def vorbis_file(request, tmp_path):
    name, args, cls = request.param
    path = tmp_path / name
    _make_vorbis_file(path, args)

    def with_comments(pairs):
        audio = cls(str(path))
        audio.delete()
        audio = cls(str(path))
        if audio.tags is None:
            audio.add_tags()
        for key, value in pairs:
            audio.tags.append((key, value))
        audio.save()
        return read(str(path))

    return with_comments


@requires_ffmpeg
@pytest.mark.parametrize(
    "pairs, expected",
    [
        ([("COMMENT", "c")], ["c"]),
        ([("DESCRIPTION", "d")], ["d"]),
        ([("DESCRIPTION", "d"), ("COMMENT", "c")], ["d"]),
        ([("COMMENT", "c"), ("DESCRIPTION", "d")], ["c"]),
    ],
    ids=["comment", "description", "description-first", "comment-first"],
)
def test_vorbis_comment_falls_back_to_description(vorbis_file, pairs, expected):
    tag = vorbis_file([("TITLE", "t"), *pairs])
    assert tag.get_string("comment") == expected


@requires_ffmpeg
def test_vorbis_comment_missing_raises_keyerror(vorbis_file):
    tag = vorbis_file([("TITLE", "t")])
    with pytest.raises(KeyError):
        tag.get_string("comment")
