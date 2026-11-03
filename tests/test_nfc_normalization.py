"""Unicode NFC normalization of tag strings.

Rockbox (since upstream commit 81fcb10f8, shipped in 2026 builds with
utf8proc) normalizes title/artist/album/genre/composer/comment/albumartist/
grouping/... to NFC when its on-device scanner reads metadata.

File paths are out of scope here: the file scanner already normalizes them to
NFC (#33), so tag normalization in the generator leaves them alone.

DAP DB Manager must produce the same strings, otherwise a library containing
both decomposed (NFD, common on macOS) and precomposed (NFC) spellings of the
same name shows duplicate artists/albums, and databases built by DDM disagree
with entries the player adds on its own.
"""

import unicodedata

import pytest

from dap_db_manager.constants import FILE_TAGS
from dap_db_manager.database.generator import DatabaseGenerator, process_batch_task
from dap_db_manager.indexfile import IndexFile
from dap_db_manager.tagging.tag.tagfile import TagFile

NFC = "Beyonc\u00e9"  # precomposed é
NFD = "Beyonce\u0301"  # e + combining acute accent
assert NFC != NFD and unicodedata.normalize("NFC", NFD) == NFC

PATH_NFD = "/Music/Beyonce\u0301/Halo.mp3"


class FakeTags(dict):
    """Minimal stand-in for the cached Tag object titleformat expects."""

    def get_string(self, name):
        return [str(v) for v in self[name]]


def _entry(path=PATH_NFD, **tags):
    base = FakeTags(title=[NFD], length=["100"], tracknumber=["1"])
    base.update(tags)
    return {"path": path, "mtime": 0, "tags": base}


FORMATS = {
    "title": ("%title%", None),
    "artist": ("%artist%", "%artist%"),
    "album": ("%album%", None),
    "genre": ("%genre%", None),
    "composer": ("%composer%", None),
    "comment": ("%comment%", None),
    "album artist": ("%album artist%", None),
    "grouping": ("%grouping%", None),
    "canonicalartist": ("%artist%", None),
}


def _process(entries, multiple=()):
    return process_batch_task(entries, FORMATS, list(multiple))


class TestProcessBatchTaskNFC:
    def test_single_value_fields_are_nfc(self):
        res = _process(
            [
                _entry(
                    artist=[NFD],
                    album=[NFD],
                    genre=[NFD],
                    composer=[NFD],
                    comment=[NFD],
                    grouping=[NFD],
                    **{"album artist": [NFD]},
                )
            ]
        )[0]
        assert res["title_tag"] == NFC
        for field, data in res["fields"].items():
            assert data["value"] == NFC, field

    def test_sort_values_are_nfc(self):
        res = _process([_entry(artist=[NFD])])[0]
        assert res["fields"]["artist"]["sort"] == NFC

    def test_grouping_title_fallback_is_nfc(self):
        res = _process([_entry()])[0]  # no grouping -> falls back to title
        assert res["fields"]["grouping"]["value"] == NFC

    def test_multiple_value_fields_are_nfc(self):
        fmts = dict(FORMATS, artist=("%<artist>%", None))
        res = process_batch_task([_entry(artist=[NFD, "Jay-Z"])], fmts, ["artist"])[0]
        values = [item["value"] for item in res["multiple_fields"]["artist"]]
        assert values == [NFC, "Jay-Z"]

    def test_path_is_left_to_the_scanner(self):
        res = _process([_entry(artist=[NFD])])[0]
        assert res["path"] == PATH_NFD


class TestAssemblyDeduplicatesNFC:
    @pytest.fixture
    def generator(self):
        gen = DatabaseGenerator(max_workers=1)
        yield gen
        gen.shutdown()

    def test_nfd_and_nfc_spellings_share_one_tag_entry(self, generator):
        tagfiles = {field: TagFile() for field in FILE_TAGS}
        index = IndexFile(tagfiles=tagfiles)
        results = _process(
            [
                _entry(path="/Music/a.mp3", artist=[NFD], album=[NFD]),
                _entry(path="/Music/b.mp3", artist=[NFC], album=[NFC]),
            ]
        )
        for result in results:
            generator._assemble_entry(result, tagfiles, index, {})

        assert [e.data for e in tagfiles["artist"]] == [NFC]
        assert [e.data for e in tagfiles["album"]] == [NFC]
        assert index.count == 2


class TestNfcHelper:
    def test_plain_string(self):
        from dap_db_manager.utils import nfc

        assert nfc(NFD) == NFC
        assert type(nfc(NFD)) is str

    def test_already_nfc_returns_same_object(self):
        from dap_db_manager.utils import nfc

        assert nfc(NFC) is NFC

    def test_tagbool_keeps_truthiness(self):
        from dap_db_manager.tagging.titleformat.tagbool import TagFalse, TagTrue
        from dap_db_manager.utils import nfc

        t, f = nfc(TagTrue(NFD)), nfc(TagFalse(NFD))
        assert t == NFC and bool(t) is True
        assert f == NFC and bool(f) is False

    def test_containers_and_non_strings(self):
        from dap_db_manager.utils import nfc

        assert nfc([NFD, "x"]) == [NFC, "x"]
        assert nfc((NFD,)) == (NFC,)
        assert nfc(None) is None
        assert nfc(5) == 5
