"""Voiceover via edge-tts (Microsoft Edge's neural voices).

Free, unlimited, runs entirely locally as a Python library. No API key, no
hosted microservice needed.
"""
import asyncio
import re

from . import config
from .utils import log


def clean_for_speech(text):
    """Strip anything that would be read aloud awkwardly."""
    text = re.sub(r"\*+", "", text)                 # markdown emphasis
    text = re.sub(r"\[[^\]]*\]", "", text)          # [stage directions]
    text = re.sub(r"\([^)]*\)", "", text)           # (parentheticals)
    text = re.sub(r"^\s*(narrator|voiceover)\s*:", "", text, flags=re.I | re.M)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _synthesize(text, out_path, voice, rate):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out_path))


def generate_voiceover(text, out_path, voice=None, rate=None):
    """Synthesize narration to an mp3. Returns the path."""
    try:
        import edge_tts  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "edge-tts is not installed. Run: pip install -r requirements.txt"
        ) from e

    voice = voice or config.TTS_VOICE
    rate = rate or config.TTS_RATE
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 5_000:
        log("  voiceover already exists, skipping")
        return out_path

    spoken = clean_for_speech(text)
    log(f"  synthesizing voiceover ({len(spoken)} chars, voice {voice})...")

    for attempt in range(3):
        try:
            asyncio.run(_synthesize(spoken, out_path, voice, rate))
            if out_path.exists() and out_path.stat().st_size > 5_000:
                return out_path
            raise RuntimeError("edge-tts produced an empty file")
        except Exception as e:  # noqa: BLE001
            log(f"  TTS attempt {attempt + 1}/3 failed: {e}", "WARN")

    raise RuntimeError(
        "Voiceover generation failed. edge-tts needs an internet connection "
        "to reach Microsoft's voice service."
    )
