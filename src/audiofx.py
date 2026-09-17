"""Optional sound-effect and emotion-based music helpers.

No assets are required. If assets/music or assets/sfx contain matching files,
the renderer uses them; otherwise it silently falls back to narration only.
"""
from pathlib import Path
import re

from . import config

EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg"}


def _files(directory):
    if not directory.exists():
        return []
    return [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS]


def pick_music(emotion="neutral"):
    tracks = _files(config.MUSIC_DIR)
    if not tracks:
        return None
    emotion = re.sub(r"[^a-z0-9]+", "_", (emotion or "neutral").lower())
    tagged = [p for p in tracks if emotion in p.stem.lower()]
    return tagged[0] if tagged else tracks[0]


def find_sfx(name):
    if not name:
        return None
    wanted = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not wanted:
        return None
    for p in _files(config.SFX_DIR):
        stem = re.sub(r"[^a-z0-9]+", "_", p.stem.lower()).strip("_")
        if stem == wanted or wanted in stem:
            return p
    return None
