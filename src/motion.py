"""Optional local ComfyUI image-to-video adapter.

The main pipeline remains usable without ComfyUI. When enabled, a compatible
ComfyUI API workflow can turn each still into a short moving clip. The workflow
must contain these literal placeholders somewhere in its JSON values:
{image}, {prompt}, {duration}. The adapter polls the job and downloads the first
video/image-like output it finds.
"""
import json
import time
from pathlib import Path
import requests
from . import config
from .utils import log

VIDEO_KEYS = ("gifs", "videos", "video", "images")


def enabled():
    return bool(config.I2V_ENABLED and config.COMFYUI_URL and config.COMFYUI_WORKFLOW.exists())


def _find_media(history):
    for node in history.values():
        outputs = node.get("outputs", {}) if isinstance(node, dict) else {}
        for key in VIDEO_KEYS:
            items = outputs.get(key, [])
            if items:
                return items[0]
    return None


def generate_clip(image_path, motion_prompt, out_path, duration=None):
    if not enabled():
        return None
    workflow = config.COMFYUI_WORKFLOW.read_text(encoding="utf-8")
    workflow = workflow.replace("{image}", str(Path(image_path).resolve()).replace("\\", "/"))
    workflow = workflow.replace("{prompt}", motion_prompt or "subtle natural movement")
    workflow = workflow.replace("{duration}", str(duration or config.I2V_CLIP_SECONDS))
    try:
        payload = {"prompt": json.loads(workflow)}
        r = requests.post(config.COMFYUI_URL.rstrip("/") + "/prompt", json=payload, timeout=30)
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]
        log(f"  I2V queued: {prompt_id}")
        for _ in range(config.I2V_TIMEOUT_SECONDS):
            time.sleep(1)
            h = requests.get(config.COMFYUI_URL.rstrip("/") + f"/history/{prompt_id}", timeout=20)
            h.raise_for_status()
            history = h.json().get(prompt_id, {})
            media = _find_media(history)
            if not media:
                continue
            params = {
                "filename": media.get("filename", ""),
                "subfolder": media.get("subfolder", ""),
                "type": media.get("type", "output"),
            }
            data = requests.get(config.COMFYUI_URL.rstrip("/") + "/view", params=params, timeout=120)
            data.raise_for_status()
            if len(data.content) < 1000:
                continue
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data.content)
            log(f"  I2V clip ready: {out_path.name}", "OK")
            return out_path
        log("  I2V timed out; falling back to still-image animation", "WARN")
    except Exception as exc:  # noqa: BLE001
        log(f"  I2V failed; falling back to still-image animation: {exc}", "WARN")
    return None
