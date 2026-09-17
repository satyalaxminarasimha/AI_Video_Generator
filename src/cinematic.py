"""Cinematic shot planning helpers.

Turns LLM scene plans into deterministic camera/transition/motion presets.  The
renderer can use these plans without requiring a heavy video model.
"""
from . import config

CAMERA_PRESETS = {
    "wide": "wide establishing shot, slow drift",
    "medium": "medium shot, gentle push in",
    "close": "close-up, slow push in",
    "push_in": "slow cinematic push in",
    "pull_out": "slow cinematic pull out",
    "pan_left": "slow pan left",
    "pan_right": "slow pan right",
    "tilt_up": "slow tilt up",
    "tilt_down": "slow tilt down",
    "handheld": "subtle handheld camera movement",
    "shake": "brief impact camera shake",
    "static": "locked-off cinematic camera",
}

TRANSITIONS = {"cut", "crossfade", "fade", "flash"}


def normalize_shot(shot, index=0):
    """Return a safe, renderer-friendly shot dictionary."""
    shot = shot if isinstance(shot, dict) else {}
    emotion = str(shot.get("emotion", "neutral")).lower().strip()
    camera = str(shot.get("camera", "")).lower().strip()
    action = str(shot.get("action", "")).strip()
    transition = str(shot.get("transition", "")).lower().strip()

    if camera not in CAMERA_PRESETS:
        camera = ["wide", "medium", "close"][index % 3]
    if transition not in TRANSITIONS:
        transition = "cut" if index == 0 else "crossfade"

    defaults = {
        "shock": "push_in",
        "sad": "push_in",
        "happy": "pan_right",
        "tension": "handheld",
        "action": "handheld",
        "reveal": "pull_out",
        "romantic": "push_in",
    }
    if not shot.get("camera") and emotion in defaults:
        camera = defaults[emotion]

    return {
        "shot_type": shot.get("shot_type", camera),
        "camera": camera,
        "emotion": emotion or "neutral",
        "action": action,
        "transition": transition,
        "motion_prompt": str(shot.get("motion_prompt", action)).strip(),
        "duration": max(float(shot.get("duration", 0) or 0), 0),
        "sound_effect": str(shot.get("sound_effect", "")).strip().lower(),
    }


def normalize_shot_plan(raw, count):
    """Normalize a list of LLM shots and fill missing shots deterministically."""
    if not isinstance(raw, list):
        raw = []
    result = [normalize_shot(item, i) for i, item in enumerate(raw[:count])]
    while len(result) < count:
        result.append(normalize_shot({}, len(result)))
    return result


def infer_camera_from_text(text, index=0):
    """Cheap fallback for old projects that only have scene prompt strings."""
    text = (text or "").lower()
    if any(w in text for w in ("shocked", "surprised", "realizes", "reveal")):
        return "push_in"
    if any(w in text for w in ("running", "fight", "chases", "runs")):
        return "handheld"
    if any(w in text for w in ("sad", "crying", "tears")):
        return "push_in"
    return ["wide", "medium", "close"][index % 3]
