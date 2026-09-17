"""Scene artwork via Pollinations.ai."""
import time
import urllib.parse
import requests
from . import config
from .cinematic import infer_camera_from_text
from .utils import log

BASE = "https://image.pollinations.ai/prompt/"
NEGATIVES = "no text, no watermark, no signature, no letters, no logo, no captions, no distorted hands, no duplicate people"


def build_prompt(scene_description, character_description, style, framing="medium shot", visual_prompt=None):
    visual = visual_prompt or scene_description
    return (f"{visual}. Character identity anchor: {character_description}. {framing}. "
            f"Art style: {style}. Vertical 9:16 composition. Cinematic depth, strong foreground/background separation, natural lighting. {NEGATIVES}.")


def image_url(prompt, seed):
    encoded = urllib.parse.quote(prompt, safe="")
    return f"{BASE}{encoded}?width={config.IMAGE_W}&height={config.IMAGE_H}&seed={seed}&nologo=true&model=flux"


def fetch_scene_images(episode, character_description, style, out_dir, day, count=None, base_seed=None, force=False):
    count = count or config.IMAGES_PER_EPISODE
    base_seed = config.IMAGE_SEED if base_seed is None else base_seed
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts = episode.get("scene_plan") or []
    paths = []
    for i in range(count):
        plan = prompts[i] if i < len(prompts) else {}
        visual = plan.get("visual_prompt") if isinstance(plan, dict) else str(plan)
        camera = plan.get("camera") if isinstance(plan, dict) else None
        camera = camera or infer_camera_from_text(visual or episode.get("scene_description", ""), i)
        framing = plan.get("shot_type", "medium shot") if isinstance(plan, dict) else "medium shot"
        prompt = build_prompt(episode.get("scene_description", ""), character_description, style, framing=f"{framing}, {camera}", visual_prompt=visual)
        seed = base_seed + day * 1000 + i
        dest = out_dir / f"scene_{i + 1}.jpg"
        if dest.exists() and dest.stat().st_size > 10_000 and not force:
            paths.append(dest)
            continue
        for attempt in range(3):
            try:
                log(f"  generating image {i + 1}/{count} (seed {seed})...")
                r = requests.get(image_url(prompt, seed), timeout=180)
                r.raise_for_status()
                if len(r.content) < 10_000:
                    raise ValueError("response too small")
                dest.write_bytes(r.content)
                break
            except Exception as exc:  # noqa: BLE001
                log(f"  image attempt {attempt + 1}/3 failed: {exc}", "WARN")
                if attempt == 2:
                    raise RuntimeError(f"Could not generate image {i + 1} for episode {day}") from exc
                time.sleep(8)
        paths.append(dest)
        time.sleep(1)
    return paths
