"""Default tag field mappings that work across all formats."""

import os
from ..core import Tag
from ..utils import conv_string_list, conv_number_list


def setup_default_mappings():
    """Register default field mappings for all audio formats."""

    # File information
    # -----------------
    def get_path(tags):
        return tags.filename

    def get_filesize(tags):
        return os.stat(get_path(tags)).st_size

    def get_modified(tags):
        return os.stat(get_path(tags)).st_mtime

    def get_codec(tags):
        return tags.mime

    Tag.RegisterKey("path", getter=get_path, convert=conv_string_list)
    Tag.RegisterKey("filesize", getter=get_filesize, convert=conv_number_list)
    Tag.RegisterKey("last_modified", getter=get_modified, convert=conv_number_list)
    Tag.RegisterKey("codec", getter=get_codec, convert=conv_string_list)

    # Default info field mappings
    # ----------------------------
    # The defaults need to go in before everything else so their conversion
    # functions are used as default. Individual codecs *can* override these
    # conversions, but I can't see why.
    # All fields will return a list of either numbers or strings

    for key, value in {
        "bitrate": "bitrate",
        "channels": "channels",
        "length": "length",
        "samplerate": "sample_rate",
    }.items():
        Tag.RegisterInfoKey(key, value, convert=conv_number_list)

    # Default basic field mappings
    # -----------------------------
    for name, conv in {
        "artist": conv_string_list,
        "album artist": conv_string_list,
        "album": conv_string_list,
        "date": conv_string_list,
        "discnumber": conv_number_list,
        "totaldiscs": conv_number_list,
        "title": conv_string_list,
        "tracknumber": conv_number_list,
        "totaltracks": conv_number_list,
        "genre": conv_string_list,
        "composer": conv_string_list,
        "performer": conv_string_list,
        "comment": conv_string_list,
        "replaygain_album_gain": conv_number_list,
        "replaygain_album_peak": conv_number_list,
        "replaygain_track_gain": conv_number_list,
        "replaygain_track_peak": conv_number_list,
    }.items():
        Tag.RegisterBasicKey(name, name, convert=conv)

    # Custom Fields (fallbacks)
    # --------------------------
    def default_custom_field(name):
        return name

    Tag.RegisterUserKey(default_custom_field, "default")
