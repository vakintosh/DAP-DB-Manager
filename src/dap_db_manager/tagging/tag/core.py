"""Core Tag class for handling audio file metadata."""

import copy
from typing import Any, Dict, Callable, Optional
from warnings import warn

from mutagen.apev2 import APEv2File as APE
from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3 as MP3
from mutagen.flac import SeekPoint
from mutagen.apev2 import APEv2File

from .utils import conv_string_list, conv_default


class Tag:
    """
    Encapsulates a mutagen tag object so that property access is similar across
    formats. (what a chore!)
    The actual object can be accessed through self.tags.

    Available properties (a la foobar2000):
        album artist
        artist
        composer
        performer
        album
        discnumber
        totaldiscs
        title
        tracknumber
        totaltracks
        bitrate (bps)
        channels (1 or 2)
        samplerate (Hz)
        codec
        length (seconds, hopefully floating-point)
        replaygain_album_gain
        replaygain_album_peak
        replaygain_track_gain
        replaygain_track_peak
        path
        filesize (bytes)
        last_modified
    """

    field_map: Dict[Any, Dict[str, Dict[str, Optional[Callable]]]] = {}

    def __init__(self, tags: Any, force_string: bool = False):
        self.tags = tags
        self.force_string = force_string

    def __get_tags(self):
        return self.__tags

    def __set_tags(self, tags):
        self.__tags = tags
        self.update_mapping()

    tags = property(__get_tags, __set_tags)

    def update_mapping(self):
        """
        Updates self.tag_mapping to reflect the type of tags in self.tags
        """
        self.tag_mapping = self.field_map["default"].copy()
        try:
            self.tag_mapping.update(self.field_map[type(self.tags)])
        except KeyError:
            pass

    def __get_force_string(self):
        return self.__force_string

    def __set_force_string(self, force):
        self.__force_string = force
        if force:
            self.__getitem_func = self.get_string
        else:
            self.__getitem_func = self.get
        self.update_mapping()

    force_string = property(__get_force_string, __set_force_string)

    # __getitem__() is adaptable based on self.force_string
    # get() can be used to force the default conversion
    # get_string() can be used to force conversion to a list of strings

    def get(self, name: str) -> Any:
        try:
            return self.tag_mapping[name]["convert"](  # type: ignore[misc]
                self.tag_mapping[name]["getter"](self.tags)  # type: ignore[misc]
            )
        except KeyError:
            return self.tag_mapping["user_field"]["convert"](  # type: ignore[misc]
                self.tag_mapping["user_field"]["getter"](self.tags, name)  # type: ignore[misc]
            )

    def get_string(self, name: str) -> list:
        """Convert the items to a string list before returning."""
        return conv_string_list(self.get(name))

    def __getitem__(self, name: str) -> Any:
        return self.__getitem_func(name)

    def __setitem__(self, name: str, value: Any):
        try:
            self.tag_mapping[name]["setter"](self.tags, value)  # type: ignore[misc]
        except KeyError:
            self.tag_mapping["user_field"]["setter"](self.tags, name, value)  # type: ignore[misc]

    def __delitem__(self, name: str):
        try:
            self.tag_mapping[name]["deleter"](self.tags)  # type: ignore[misc]
        except KeyError:
            self.tag_mapping["user_field"]["deleter"](self.tags, name)  # type: ignore[misc]

    @classmethod
    def RegisterKey(
        cls,
        name: str,
        type: Any = "default",
        getter: Optional[Callable] = None,
        setter: Optional[Callable] = None,
        deleter: Optional[Callable] = None,
        convert: Optional[Callable] = None,
    ):
        if type not in cls.field_map:
            cls.field_map[type] = {}

        # Figure out the conversion function
        if type == "default":
            if not convert:
                pass
        else:
            if not convert:
                try:
                    convert = cls.field_map["default"][name]["convert"]
                except KeyError:
                    warning_text = (
                        f'No conversion is defined for field "{name}".  '
                        + f"Default conversion will be used for {repr(type)}"
                    )
                    warn(warning_text)
                    convert = conv_default

        cls.field_map[type][name] = {
            "getter": getter,
            "setter": setter,
            "deleter": deleter,
            "convert": convert,
        }

    @classmethod
    def RegisterInfoKey(
        cls,
        key: str,
        name: str,
        type: Any = "default",
        convert: Optional[Callable] = None,
    ):
        def getter(tags):
            return tags.info.__dict__[name]

        getter.__name__ = "info_getter(" + name + ")"
        cls.RegisterKey(key, type, getter, convert=convert)

    @classmethod
    def RegisterBasicKey(
        cls,
        key: str,
        name: str,
        type: Any = "default",
        convert: Optional[Callable] = None,
    ):
        def getter(tags):
            return tags[name]

        getter.__name__ = "field_getter(" + name + ")"

        def setter(tags, value):
            tags[name] = value

        setter.__name__ = "field_setter(" + name + ")"

        def deleter(tags):
            del tags[name]

        deleter.__name__ = "field_deleter(" + name + ")"

        cls.RegisterKey(key, type, getter, setter, deleter, convert)

    @classmethod
    def RegisterUserKey(cls, name_func: Callable, type: Any = "default"):
        """
        Register a default handler for unknown keys.
        Note that these functions take both a <tags> and a <name> argument
        instead of just the <tags> argument.
        <name_func> is a function that generates the proper key given a custom
        field name.
        """

        def user_field_getter(tags, name):
            return tags[name_func(name)]

        def user_field_setter(tags, name, value):
            tags[name_func(name)] = value

        def user_field_deleter(tags, name):
            del tags[name_func(name)]

        cls.RegisterKey(
            "user_field",
            type,
            user_field_getter,
            user_field_setter,
            user_field_deleter,
            conv_string_list,
        )

    def pprint(self):
        """Pretty print all tag fields."""
        offset = max(len(key) for key in self.tag_mapping)
        for key in self.tag_mapping:
            if key == "user_field":
                continue
            try:
                value = self[key]
                print(key.ljust(offset), type(value), value)
            except KeyError:
                print(key, "<NONE>")

    # ---------------------------------------------------------------------------
    # Pickling functions
    # ---------------------------------------------------------------------------
    def __getstate__(self):
        if isinstance(self.tags, MP3):
            # Methods of an instance (such as our own '__getattr_func') can't
            # be pickled, so we need to remove them. MP3 files have a few.
            tags_copy = copy.copy(self.tags)
            for func in ["load", "save", "delete"]:
                try:
                    # First we have to get rid of the reference that tags_copy is
                    # holding.
                    setattr(tags_copy.tags, func, None)
                    # Now we can delete it safely
                    delattr(tags_copy.tags, func)
                except (AttributeError, TypeError):
                    # In newer versions of mutagen, these might be properties
                    # that can't be deleted. Just skip them.
                    pass
            return tags_copy, self.force_string

        elif isinstance(self.tags, APE):
            # The APE info class is defined *inside* another class, and pickle
            # only works on objects that are defined at the top level of the
            # class. (sigh) We'll pickle the info as a dictionary.
            tags_copy = copy.copy(self.tags)
            tags_copy.info = copy.copy(self.tags.info.__dict__)
            return tags_copy, self.force_string

        elif (
            isinstance(self.tags, FLAC)
            and self.tags.seektable is not None
            and getattr(self.tags.seektable, "seekpoints", None) is not None
        ):
            # FLAC files have a table of seekpoints (tuples), which don't
            # unpickle very well. We'll pickle the seekpoints as actual
            # tuples.
            tags_copy = copy.copy(self.tags)
            tags_copy.seektable.seekpoints = [
                tuple(pt) for pt in tags_copy.seektable.seekpoints
            ]
            return tags_copy, self.force_string

        else:
            return self.tags, self.force_string

    def __setstate__(self, state):
        self.tags, self.force_string = state

        # The info is pickled as a dictionary for APE tags
        if isinstance(self.tags, APE):
            info = self.tags.info
            self.tags.info = object.__new__(APEv2File._Info)
            self.tags.info.__dict__.update(info)

        # The seektable.seekpoints are pickled as tuples for FLAC tags
        elif (
            isinstance(self.tags, FLAC)
            and self.tags.seektable is not None
            and getattr(self.tags.seektable, "seekpoints", None) is not None
        ):
            self.tags.seektable.seekpoints = [
                SeekPoint(*pt) for pt in self.tags.seektable.seekpoints
            ]

        elif isinstance(self.tags, MP3):
            for func in ["load", "save", "delete"]:
                try:
                    # Try to restore the methods if they were removed
                    if (
                        not hasattr(self.tags.tags, func)
                        or getattr(self.tags.tags, func) is None
                    ):
                        setattr(
                            self.tags.tags,
                            func,
                            getattr(self.tags.tags._EasyID3__id3, func),
                        )
                except (AttributeError, TypeError):
                    # In newer versions of mutagen, these might be properties
                    # that don't need restoration. Just skip them.
                    pass
