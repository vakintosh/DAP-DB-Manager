"""Audio file format definitions and reading functions."""

from typing import Optional
import mutagen
from mutagen.asf import ASF
from mutagen.apev2 import APEv2File as APE
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3FileType as ID3
from mutagen.mp3 import EasyMP3 as MP3
from mutagen.oggvorbis import OggVorbis as Vorbis
from mutagen.oggopus import OggOpus as Opus
from mutagen.oggflac import OggFLAC
from mutagen.oggspeex import OggSpeex as Speex
from mutagen.trueaudio import TrueAudio
from mutagen.aiff import AIFF
from mutagen.wave import WAVE
from mutagen.wavpack import WavPack
from mutagen.mp4 import MP4
from mutagen.musepack import Musepack

from .core import Tag


FORMAT_MAPPING = {
    # Microsoft / Windows
    ".asf": ASF,
    ".wma": ASF,
    ".wav": WAVE,
    # MPEG / Apple
    ".mp3": MP3,
    ".mp4": MP4,
    ".m4a": MP4,
    ".m4b": MP4,
    ".aiff": AIFF,
    ".aif": AIFF,
    # Xiph.Org (Ogg container & friends)
    ".ogg": Vorbis,  # Default handler for .ogg, though could be Opus/FLAC
    ".opus": Opus,
    ".spx": Speex,
    ".flac": FLAC,
    # Other Lossless / Audiophile
    ".mpc": Musepack,
    ".wv": WavPack,
    ".tta": TrueAudio,
    ".ape": APE,  # Added .ape (supported by import APEv2File)
}

SUPPORTED_EXTENSIONS = set(FORMAT_MAPPING.keys())

_FALLBACK_PARSERS = [OggFLAC, ID3]

READ_OPTIONS = list(set(FORMAT_MAPPING.values())) + _FALLBACK_PARSERS


def read(filename: str, force_string: bool = False) -> Optional[Tag]:
    """
    Read audio file tags and return a Tag object.

    Args:
        filename: Path to the audio file
        force_string: If True, all fields will be returned as string lists

    Returns:
        Tag object if file has valid tags, None otherwise
    """
    # mutagen.File will iterate through options to sniff the correct format
    tags = mutagen.File(filename, options=READ_OPTIONS)

    if tags:
        return Tag(tags, force_string)
    else:
        return None
