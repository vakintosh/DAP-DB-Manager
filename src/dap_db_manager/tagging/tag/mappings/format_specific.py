"""Format-specific tag field mappings (ASF, MP4, APE, Musepack, WavPack,
raw-ID3 containers, Vorbis comments)."""

from mutagen.asf import ASF
from mutagen.mp4 import MP4
from mutagen.apev2 import APEv2File as APE
from mutagen.musepack import Musepack

from mutagen.wavpack import WavPack
from mutagen.wave import WAVE
from mutagen.aiff import AIFF
from mutagen.dsf import DSF
from mutagen.dsdiff import DSDIFF
from mutagen.flac import FLAC
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggspeex import OggSpeex
from mutagen.oggvorbis import OggVorbis

from ..core import Tag


def setup_format_specific_mappings():
    """Register format-specific field mappings."""

    # Info Fields (specific to certain formats)
    # ------------------------------------------
    for tag_type, tag_dict in {
        Musepack: {
            "replaygain_album_gain": "album_gain",
            "replaygain_album_peak": "album_peak",
            "replaygain_track_gain": "title_gain",
            "replaygain_track_peak": "title_peak",
        },
    }.items():
        for key, value in tag_dict.items():
            Tag.RegisterInfoKey(key, value, tag_type)

    # Standard Fields (format-specific mappings)
    # -------------------------------------------
    for tag_type, tag_dict in {
        ASF: {
            "artist": "Author",
            "album artist": "WM/AlbumArtist",
            "album": "WM/AlbumTitle",
            "date": "WM/Year",
            "discnumber": "WM/PartOfSet",
            "totaldiscs": "foobar2000/TOTALDISCS",
            "title": "Title",
            "tracknumber": "WM/TrackNumber",
            "totaltracks": "TotalTracks",
            "genre": "WM/Genre",
            "composer": "WM/Composer",
            # Rockbox reads the native content-group atom for tag 8 (grouping).
            # The foobar2000/GROUPING freeform key remains reachable via the
            # ASF_custom_field user-key fallback.
            "grouping": "WM/ContentGroupDescription",
            "performer": "foobar2000/PERFORMER",
            "comment": "Description",
        },
        MP4: {
            "artist": "\xa9ART",
            "album artist": "aART",
            "album": "\xa9alb",
            "date": "\xa9day",
            "title": "\xa9nam",
            "genre": "\xa9gen",
            "composer": "\xa9wrt",
            # Rockbox reads the native ©grp atom for tag 8 (grouping). The
            # ----:com.apple.iTunes:GROUPING freeform key remains reachable via
            # the MP4_custom_field user-key fallback.
            "grouping": "\xa9grp",
            "performer": "----:com.apple.iTunes:PERFORMER",
            "comment": "\xa9cmt",
            "replaygain_album_gain": "----:com.apple.iTunes:replaygain_album_gain",
            "replaygain_album_peak": "----:com.apple.iTunes:replaygain_album_peak",
            "replaygain_track_gain": "----:com.apple.iTunes:replaygain_track_gain",
            "replaygain_track_peak": "----:com.apple.iTunes:replaygain_track_peak",
        },
        APE: {
            "date": "Year",
        },
        Musepack: {
            "date": "Year",
        },
        WavPack: {
            "date": "Year",
        },
    }.items():
        for key, value in tag_dict.items():
            Tag.RegisterBasicKey(key, value, tag_type)

    # Discnumber / tracknumber splitting
    # -----------------------------------
    def from_tuple(key, index, default=0):
        """Helper to extract values from tuple fields."""

        def getter(tags):
            val = tags[key][0][index]
            if val == default:
                raise KeyError(key)
            return val

        def setter(tags, value):
            tags[key] = [tags[key][0][:index] + (value,) + tags[key][0][index + 1 :]]

        def deleter(tags):
            setter(tags, default)

        return getter, setter, deleter

    def split_string(key, sep, index):
        """Helper to split string fields."""
        # Index needs to be either 0 or 2 because we're using str.partition
        index = index if index == 0 else 2

        def getter(tags):
            val = str(tags[key]).partition(sep)[index]
            if val:
                return val
            else:
                raise KeyError

        def setter(tags, value):
            value = str(value)
            try:
                vals = list(str(tags[key]).partition(sep))
                vals[index] = value

                # If separator existed, keep it
                if vals[1]:
                    tags[key] = vals[0] + vals[1] + vals[2]
                else:
                    # Separator missing
                    if index == 0:
                        tags[key] = vals[0]
                    else:
                        tags[key] = vals[0] + sep + vals[2]
            except KeyError:
                if index == 0:
                    tags[key] = value

        def deleter(tags):
            if index == 0:
                del tags[key]
            else:
                tags[key] = str(tags[key]).partition(sep)[0]

        return getter, setter, deleter

    # MP4 tuple-based disc/track fields
    for tag_type, tag_dict in {
        MP4: {
            "disc": "disk",
            "track": "trkn",
        }
    }.items():
        for key, value in tag_dict.items():
            Tag.RegisterKey(key + "number", tag_type, *from_tuple(value, 0))
            Tag.RegisterKey("total" + key + "s", tag_type, *from_tuple(value, 1))

    # String-split based disc/track fields
    for tag_type, tag_dict in {
        APE: {
            "disc": "Disc",
            "track": "Track",
        },
        Musepack: {
            "disc": "Disc",
            "track": "Track",
        },
    }.items():
        for key, value in tag_dict.items():
            Tag.RegisterKey(key + "number", tag_type, *split_string(value, "/", 0))
            Tag.RegisterKey("total" + key + "s", tag_type, *split_string(value, "/", 1))

    def WAVE_date_getter(tags):
        # WAVE tags are mutagen.wave._WaveID3 which behave like ID3 dicts
        # We need to look inside the 'tags' attribute of the file object
        id3 = tags.tags
        for frame in ["TDRC", "TDOR", "TYER", "TYE"]:
            if frame in id3:
                return list(id3[frame])
        raise KeyError("date")

    def WAVE_date_setter(tags, value):
        id3 = tags.tags
        # Default to TDRC
        try:
            frame = id3["TDRC"]
            frame.text = value
        except KeyError:
            import mutagen.id3

            id3.add(mutagen.id3.TDRC(encoding=3, text=value))

    def WAVE_date_deleter(tags):
        id3 = tags.tags
        deleted = False
        for frame in ["TDRC", "TDOR", "TYER", "TYE"]:
            try:
                del id3[frame]
                deleted = True
            except KeyError:
                pass
        if not deleted:
            raise KeyError("date")

    # Raw-ID3 container mapping
    # ---------------------------
    # WAVE, AIFF, DSF and DSDIFF all carry a plain ID3 chunk rather than an
    # EasyID3 view, so their fields must be mapped to ID3 frames explicitly.
    # (Before this was shared, only WAVE had it: AIFF files were indexed as
    # <Untagged>.)
    tag_dict = {
        "artist": "TPE1",
        "album artist": "TPE2",
        "album": "TALB",
        # "date" handled by custom getter below
        "title": "TIT2",
        "genre": "TCON",
        "composer": "TCOM",
        "comment": "COMM::eng",
        "grouping": "TIT1",
    }

    for id3_container in (WAVE, AIFF, DSF, DSDIFF):
        for key, frame in tag_dict.items():
            Tag.RegisterBasicKey(key, frame, id3_container)

        Tag.RegisterKey(
            "date",
            id3_container,
            getter=WAVE_date_getter,
            setter=WAVE_date_setter,
            deleter=WAVE_date_deleter,
        )

        Tag.RegisterKey("tracknumber", id3_container, *split_string("TRCK", "/", 0))
        Tag.RegisterKey("totaltracks", id3_container, *split_string("TRCK", "/", 1))
        Tag.RegisterKey("discnumber", id3_container, *split_string("TPOS", "/", 0))
        Tag.RegisterKey("totaldiscs", id3_container, *split_string("TPOS", "/", 1))

    # Vorbis-comment "comment"
    # -------------------------
    # Rockbox (upstream ab64e2653) reads DESCRIPTION -- the Vorbis comment
    # spec's name for it, written by ffmpeg/SoX/beets/mutagen -- as the
    # comment. With both COMMENT and DESCRIPTION present, the first one in the
    # file wins. Writes/deletes keep targeting COMMENT.
    def vorbis_comment_getter(tags):
        for key, _ in tags.tags or ():
            lowered = key.lower()
            if lowered in ("comment", "description"):
                return tags[lowered]
        raise KeyError("comment")

    def vorbis_comment_setter(tags, value):
        tags["comment"] = value

    def vorbis_comment_deleter(tags):
        del tags["comment"]

    for vorbis_type in (FLAC, OggVorbis, OggOpus, OggFLAC, OggSpeex):
        Tag.RegisterKey(
            "comment",
            vorbis_type,
            getter=vorbis_comment_getter,
            setter=vorbis_comment_setter,
            deleter=vorbis_comment_deleter,
        )

    # Custom Fields (format-specific fallbacks)
    # -----------------------------------------
    def MP4_custom_field(name):
        return "----:com.apple.iTunes:" + name.upper()

    def ASF_custom_field(name):
        return "foobar2000/" + name.upper()

    Tag.RegisterUserKey(MP4_custom_field, MP4)
    Tag.RegisterUserKey(ASF_custom_field, ASF)
