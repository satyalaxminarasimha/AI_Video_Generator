"""Small shared helpers."""
import json
import re
import shutil
import subprocess
import sys


def log(msg, level="INFO"):
    colors = {"INFO": "\033[36m", "OK": "\033[32m", "WARN": "\033[33m", "ERR": "\033[31m"}
    reset = "\033[0m"
    print(f"{colors.get(level, '')}[{level}]{reset} {msg}", flush=True)


def slugify(text, maxlen=50):
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-") or "story"


def clean_json(raw):
    """LLMs love wrapping JSON in markdown fences or adding commentary.

    Strip fences, then grab the outermost JSON object/array by bracket matching.
    """
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    # Find the first { or [ and match to its partner.
    start = None
    for i, ch in enumerate(text):
        if ch in "[{":
            start = i
            break
    if start is None:
        raise ValueError(f"No JSON found in model output:\n{raw[:500]}")

    opener = text[start]
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"Unbalanced JSON in model output:\n{raw[:500]}")


def require_binary(name, hint):
    if shutil.which(name) is None:
        log(f"'{name}' not found on PATH. {hint}", "ERR")
        sys.exit(1)


def audio_duration(path):
    """Return duration of an audio/video file in seconds via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def run(cmd, desc=""):
    """Run a subprocess, surfacing stderr properly on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log(f"Command failed: {desc or cmd[0]}", "ERR")
        print(proc.stderr[-3000:])
        raise RuntimeError(f"{desc or cmd[0]} failed")
    return proc
