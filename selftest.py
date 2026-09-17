#!/usr/bin/env python3
"""Offline self-test.

Validates everything that does NOT need the internet:
  - JSON cleaning against messy LLM output
  - caption chunking and SRT timing
  - the full FFmpeg render path (Ken Burns, concat, burned captions, audio mix)

It fabricates its own placeholder images and a synthesized tone for audio, so it
runs with no API keys and no network. If this passes, your FFmpeg setup is good
and the only remaining variables are your API key and your connection.

Usage:  python selftest.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from src.captions import build_captions, chunk_text
from src.render import render_episode
from src.utils import audio_duration, clean_json, log

NARRATION = (
    "They said he was nothing. A boy in torn shoes, counting coins on a bus he "
    "could barely afford. Every morning the same laughter followed him down the "
    "same hallway. He never answered. He never looked up. What none of them knew "
    "was that the building they worked in had been sold three weeks earlier. "
    "And the name on the deed was his."
)

PASSED, FAILED = [], []


def check(name, fn):
    try:
        fn()
        PASSED.append(name)
        log(f"PASS  {name}", "OK")
    except Exception as e:  # noqa: BLE001
        FAILED.append((name, e))
        log(f"FAIL  {name}: {e}", "ERR")


def test_clean_json_plain():
    data = clean_json('[{"title": "A"}]')
    assert data[0]["title"] == "A", data


def test_clean_json_fenced():
    raw = 'Sure! Here you go:\n```json\n[{"title": "B", "n": 2}]\n```\nHope that helps!'
    data = clean_json(raw)
    assert data[0]["n"] == 2, data


def test_clean_json_braces_in_strings():
    raw = '```\n[{"narration_script": "He said {nothing} at all [really]"}]\n```'
    data = clean_json(raw)
    assert "nothing" in data[0]["narration_script"], data


def test_clean_json_object():
    raw = 'Here is the character:\n{"character_name": "Arun", "age": 19}'
    data = clean_json(raw)
    assert data["character_name"] == "Arun", data


def test_chunking():
    chunks = chunk_text(NARRATION, words_per_chunk=5)
    assert len(chunks) > 5, f"expected several chunks, got {len(chunks)}"
    assert all(len(c.split()) <= 5 for c in chunks), "a chunk exceeded the word limit"
    # No chunk should straddle a sentence boundary.
    joined = " ".join(chunks)
    assert "nothing" in joined and "his" in joined


def test_caption_timing():
    with tempfile.TemporaryDirectory() as td:
        path, cues = build_captions(NARRATION, 30.0, Path(td) / "c.ass")
        assert cues, "no cues produced"
        assert cues[0][0] >= 0, "negative start time"
        last_end = cues[-1][1]
        assert 29.0 <= last_end <= 30.1, f"last cue ends at {last_end}, expected ~30"
        # Cues must be monotonic and non-overlapping.
        for a, b in zip(cues, cues[1:]):
            assert a[1] <= b[0] + 1e-6, f"overlapping cues: {a} then {b}"
        text = path.read_text(encoding="utf-8")
        assert "PlayResY: 1920" in text, "ASS is missing its resolution header"
        assert "Dialogue:" in text, "no dialogue lines written"


def make_placeholder_images(directory, count=3):
    from PIL import Image, ImageDraw

    palettes = [(28, 34, 56), (70, 40, 38), (22, 52, 48)]
    paths = []
    for i in range(count):
        img = Image.new("RGB", (1080, 1920), palettes[i % len(palettes)])
        d = ImageDraw.Draw(img)
        # Some structure so the Ken Burns motion is actually visible.
        for y in range(0, 1920, 120):
            d.line([(0, y), (1080, y + 60)], fill=(255, 255, 255), width=3)
        d.ellipse([340, 760, 740, 1160], outline=(255, 210, 120), width=14)
        d.text((80, 120), f"SCENE {i + 1}", fill=(255, 255, 255))
        p = directory / f"scene_{i + 1}.jpg"
        img.save(p, quality=92)
        paths.append(p)
    return paths


def make_test_audio(path, seconds=12):
    """Synthesize a quiet tone so we have a real audio track to mux."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
         "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
        check=True, capture_output=True,
    )
    return path


def test_full_render():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        images = make_placeholder_images(td, 3)
        audio = make_test_audio(td / "voice.mp3", seconds=12)
        out = td / "render" / "part1.mp4"

        render_episode(images, audio, NARRATION, out, music_path=None,
                       font="DejaVu Sans")

        assert out.exists(), "no output file produced"
        assert out.stat().st_size > 50_000, "output suspiciously small"

        dur = audio_duration(out)
        assert 12.0 <= dur <= 13.5, f"video is {dur:.2f}s, expected ~12.6s"

        # Confirm both streams exist and the video is the right shape.
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True, check=True,
        ).stdout
        assert "1080,1920" in probe.replace(" ", ""), f"wrong dimensions: {probe}"
        assert "audio" in probe, f"no audio stream: {probe}"


def test_render_with_music():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        images = make_placeholder_images(td, 2)
        audio = make_test_audio(td / "voice.mp3", seconds=8)
        music = make_test_audio(td / "music.mp3", seconds=4)  # shorter, must loop
        out = td / "render" / "part1.mp4"

        render_episode(images, audio, NARRATION, out, music_path=music,
                       font="DejaVu Sans")

        assert out.exists()
        dur = audio_duration(out)
        assert 8.0 <= dur <= 9.5, f"video is {dur:.2f}s, expected ~8.6s"


def main():
    log("Running offline self-test (no network or API keys needed)\n")

    check("clean_json: plain array", test_clean_json_plain)
    check("clean_json: markdown fences + commentary", test_clean_json_fenced)
    check("clean_json: braces inside strings", test_clean_json_braces_in_strings)
    check("clean_json: bare object", test_clean_json_object)
    check("captions: chunking", test_chunking)
    check("captions: ASS timing + resolution header", test_caption_timing)
    check("render: full pipeline (3 shots, captions, no music)", test_full_render)
    check("render: music bed looped and mixed", test_render_with_music)

    print()
    log(f"{len(PASSED)} passed, {len(FAILED)} failed",
        "OK" if not FAILED else "ERR")
    if FAILED:
        for name, err in FAILED:
            log(f"  {name}: {err}", "ERR")
        sys.exit(1)
    log("FFmpeg pipeline is working. Add your API key and run run.py.", "OK")


if __name__ == "__main__":
    main()
