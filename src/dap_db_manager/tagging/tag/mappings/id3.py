"""ID3/MP3 specific tag field mappings and handling."""

import mutagen
import mutagen.id3
from mutagen.easyid3 import EasyID3


ID3_GENRES = [
    "Blues",
    "Classic Rock",
    "Country",
    "Dance",
    "Disco",
    "Funk",
    "Grunge",
    "Hip-Hop",
    "Jazz",
    "Metal",
    "New Age",
    "Oldies",
    "Other",
    "Pop",
    "R&B",
    "Rap",
    "Reggae",
    "Rock",
    "Techno",
    "Industrial",
    "Alternative",
    "Ska",
    "Death Metal",
    "Pranks",
    "Soundtrack",
    "Euro-Techno",
    "Ambient",
    "Trip-Hop",
    "Vocal",
    "Jazz+Funk",
    "Fusion",
    "Trance",
    "Classical",
    "Instrumental",
    "Acid",
    "House",
    "Game",
    "Sound Clip",
    "Gospel",
    "Noise",
    "AlternRock",
    "Bass",
    "Soul",
    "Punk",
    "Space",
    "Meditative",
    "Instrumental Pop",
    "Instrumental Rock",
    "Ethnic",
    "Gothic",
    "Darkwave",
    "Techno-Industrial",
    "Electronic",
    "Pop-Folk",
    "Eurodance",
    "Dream",
    "Southern Rock",
    "Comedy",
    "Cult",
    "Gangsta",
    "Top 40",
    "Christian Rap",
    "Pop/Funk",
    "Jungle",
    "Native American",
    "Cabaret",
    "New Wave",
    "Psychadelic",
    "Rave",
    "Showtunes",
    "Trailer",
    "Lo-Fi",
    "Tribal",
    "Acid Punk",
    "Acid Jazz",
    "Polka",
    "Retro",
    "Musical",
    "Rock & Roll",
    "Hard Rock",
    # Winamp extensions
    "Folk",
    "Folk-Rock",
    "National Folk",
    "Swing",
    "Fast Fusion",
    "Bebob",
    "Latin",
    "Revival",
    "Celtic",
    "Bluegrass",
    "Avantgarde",
    "Gothic Rock",
    "Progressive Rock",
    "Psychedelic Rock",
    "Symphonic Rock",
    "Slow Rock",
    "Big Band",
    "Chorus",
    "Easy Listening",
    "Acoustic",
    "Humour",
    "Speech",
    "Chanson",
    "Opera",
    "Chamber Music",
    "Sonata",
    "Symphony",
    "Booty Bass",
    "Primus",
    "Porn Groove",
    "Satire",
    "Slow Jam",
    "Club",
    "Tango",
    "Samba",
    "Folklore",
    "Ballad",
    "Power Ballad",
    "Rhythmic Soul",
    "Freestyle",
    "Duet",
    "Punk Rock",
    "Drum Solo",
    "A capella",
    "Euro-House",
    "Dance Hall",
    "Goa",
    "Drum & Bass",
    "Club-House",
    "Hardcore",
    "Terror",
    "Indie",
    "BritPop",
    "Negerpunk",
    "Polsk Punk",
    "Beat",
    "Christian Gangsta Rap",
    "Heavy Metal",
    "Black Metal",
    "Crossover",
    "Contemporary Christian",
    "Christian Rock",
    "Merengue",
    "Salsa",
    "Thrash Metal",
    "Anime",
    "Jpop",
    "Synthpop",
]


def setup_id3_mappings():
    """Register ID3/MP3 specific field mappings."""

    def RegisterAdaptableKey(name, key_finder, key_setter):
        """
        Register a key given a name, a function to look up the key in the id3
        dict, and a function to set the key if it is not already in the dict.
        """

        def getter(id3, key):
            return list(id3[key_finder(id3)])

        def setter(id3, key, value):
            try:
                frame = id3[key_finder(id3)]
            except KeyError:
                key_setter(id3, value)
            else:
                frame.text = value

        def deleter(id3, key):
            del id3[key_finder(id3)]

        EasyID3.RegisterKey(name, getter, setter, deleter)

    def find_txxx_field(id3, name):
        """Find a TXXX frame by name (case-insensitive)."""
        frame = "TXXX:" + name.upper()
        for k in id3:
            if k.upper() == frame:
                return k
        raise KeyError("TXXX:" + name)

    def new_txxx_field(id3, name, value):
        """Create a new TXXX frame."""
        enc = 0
        # Store 8859-1 if we can, per MusicBrainz spec.
        for v in value:
            if max(v) > "\x7f":
                enc = 3
        id3.add(mutagen.id3.TXXX(encoding=enc, text=value, desc=name))

    def RegisterFoobarTXXXKey(name, desc):
        """Same as the normal RegisterTXXXKey, but case-insensitive."""

        def finder(id3):
            return find_txxx_field(id3, name)

        def setter(id3, value):
            return new_txxx_field(id3, name, value)

        RegisterAdaptableKey(name, finder, setter)

    # Register the TXXX frames that foobar reads/writes
    for name in (
        "replaygain_album_gain",
        "replaygain_album_peak",
        "replaygain_track_gain",
        "replaygain_track_peak",
        "album artist",
        "performer",
    ):
        RegisterFoobarTXXXKey(name, name)

    # Register the comment field (anything that starts with COMM)
    # Foobar writes comment as COMM::'eng'. Others write it as COMM
    def comment_finder(id3):
        for k in id3:
            if k.startswith("COMM"):
                return k
        raise KeyError("COMM")

    def comment_setter(id3, value):
        id3.add(mutagen.id3.COMM(encoding=3, text=value))

    RegisterAdaptableKey("comment", comment_finder, comment_setter)

    # Rename keys as foobar uses them
    for key, frame in {"band": "TPE2"}.items():
        EasyID3.RegisterTextKey(key, frame)

    # foobar stores 'tracknumber' and 'totaltracks' in the tracknumber frame 'TRCK'
    # as such: %tracknumber[/%totaltracks%]
    # If the %tracknumber% is blank, %totaltracks% is stored under TXXX
    # (what a pain in the ass)
    # We need to define (extra) special behavior for this
    # Note that this is also true for discnumber / totaldiscs

    def RegisterNumberPair(number_name, total_name, frameid, txxxdesc):
        txxxframe = "TXXX:" + txxxdesc

        def number_getter(id3, key):
            return [t.partition("/")[0] for t in list(id3[frameid])]

        def total_getter(id3, key):
            # The frame stores "number[/total]". If the total is not in the
            # frame -- either because the frame is absent, or because it holds
            # a bare number -- it lives in the TXXX frame instead.
            try:
                sep, total = list(id3[frameid])[0].partition("/")[1:]
                if sep:
                    return [total]
            except KeyError:
                pass

            # Raises KeyError(txxxframe) if the total is stored nowhere.
            return list(id3[txxxframe])

        def number_setter(id3, key, number):
            if isinstance(number, (list, tuple)):
                number = number[0]
            number = str(number)

            # Get total and make the number/total string.
            # Side effect: if the total was stored in TXXX, this consolidates
            # it into the number frame and drops the TXXX frame. The value is
            # preserved; only its representation changes.
            try:
                text = number + "/" + total_getter(id3, key)[0]
                # Try to delete the TXXX:TOTALTRACKS frame if it exists
                try:
                    del id3[txxxframe]
                except KeyError:
                    pass
            except KeyError:
                text = number

            try:
                frame = id3[frameid]
                frame.text = [text]
            except KeyError:
                id3.add(mutagen.id3.Frames[frameid](encoding=3, text=text))

        def total_setter(id3, key, total):
            if isinstance(total, (list, tuple)):
                total = total[0]
            total = str(total)

            try:
                number = number_getter(id3, key)[0]
                frame = id3[frameid]
                assert len(frame.text) == 1
                frame.text = [number + "/" + total]
            except KeyError:
                new_txxx_field(id3, txxxdesc, [total])

        def number_deleter(id3, key):
            try:
                total = total_getter(id3, key)
                del id3[frameid]
                total_setter(id3, key, total)
            except KeyError:
                pass

        def total_deleter(id3, key):
            try:
                number = number_getter(id3, key)
                del id3[frameid]
            except KeyError:
                del id3[txxxframe]
            else:
                number_setter(id3, key, number)

        EasyID3.RegisterKey(number_name, number_getter, number_setter, number_deleter)
        EasyID3.RegisterKey(total_name, total_getter, total_setter, total_deleter)

    RegisterNumberPair("tracknumber", "totaltracks", "TRCK", "TOTALTRACKS")
    RegisterNumberPair("discnumber", "totaldiscs", "TPOS", "TOTALDISCS")

    # Handle date fallback (TDRC -> TDOR -> TYER -> TYE)
    # TDRC: Recording Time (v2.4)
    # TDOR: Original Release Time (v2.4)
    # TYER: Year (v2.3)
    # TYE: Year (v2.2)
    def RegisterDateKey():
        def getter(id3, key):
            for frame in ["TDRC", "TDOR", "TYER", "TYE"]:
                if frame in id3:
                    return list(id3[frame])
            raise KeyError(key)

        def setter(id3, key, value):
            # Default to TDRC
            try:
                frame = id3["TDRC"]
                frame.text = value
            except KeyError:
                id3.add(mutagen.id3.TDRC(encoding=3, text=value))

        def deleter(id3, key):
            deleted = False
            for frame in ["TDRC", "TDOR", "TYER", "TYE"]:
                try:
                    del id3[frame]
                    deleted = True
                except KeyError:
                    pass
            if not deleted:
                raise KeyError(key)

        EasyID3.RegisterKey("date", getter, setter, deleter)

    RegisterDateKey()

    # Register grouping (TIT1) to match Rockbox
    EasyID3.RegisterTextKey("grouping", "TIT1")

    # Fallback functions for EasyID3
    # -------------------------------
    # I'm not sure why it wants a <self> parameter here, but it seems to.
    def user_getter(self, id3, key):
        return list(id3[find_txxx_field(id3, key)])

    def user_setter(self, id3, key, value):
        try:
            frame = id3[find_txxx_field(id3, key)]
        except KeyError:
            new_txxx_field(id3, key, value)
        else:
            frame.text = value

    def user_deleter(self, id3, key):
        del id3[find_txxx_field(id3, key)]

    EasyID3.GetFallback = user_getter
    EasyID3.SetFallback = user_setter
    EasyID3.DelFallback = user_deleter
