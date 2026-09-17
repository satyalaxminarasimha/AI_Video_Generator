#!/usr/bin/env python3
"""AI Story -> cinematic vertical video pipeline."""
import argparse
import json
import sys
from pathlib import Path

from src import config, llm
from src.images import fetch_scene_images
from src.render import render_episode
from src.motion import generate_clip
from src.utils import log, require_binary, slugify
from src.voice import generate_voiceover


def load_or_build_story(project_dir, topic, episodes, style):
    story_path = project_dir / "story.json"
    if story_path.exists():
        return json.loads(story_path.read_text(encoding="utf-8"))
    story = llm.build_story(topic, episodes, style)
    project_dir.mkdir(parents=True, exist_ok=True)
    story_path.write_text(json.dumps(story, indent=2), encoding="utf-8")
    log(f"Story saved to {story_path}", "OK")
    return story


def ensure_scene_plans(story, count):
    """Upgrade old story.json files with shot-level cinematic plans."""
    changed = False
    character_name = story.get("character", {}).get("character_name", "Main character")
    for episode in story.get("episodes", []):
        plan = episode.get("scene_plan")
        if isinstance(plan, list) and len(plan) == count:
            continue
        raw = llm.generate_scene_plan(
            episode.get("narration_script", ""),
            episode.get("scene_description", ""),
            count,
            character_name,
        )
        episode["scene_plan"] = raw[:count]
        changed = True
    return changed


def write_readable_script(story, project_dir):
    lines = [f"TOPIC: {story['topic']}", ""]
    char = story.get("character", {})
    lines += ["CHARACTER", f"  Name: {char.get('character_name', '?')}",
              f"  Age: {char.get('age', '?')}",
              f"  Appearance: {char.get('physical_description', '?')}",
              f"  Personality: {char.get('personality', '?')}", "", "=" * 70, ""]
    for i, ep in enumerate(story["episodes"], start=1):
        lines += [f"PART {i}: {ep.get('title', '')}", f"  [{ep.get('emotional_beat', '')}]", "",
                  "  NARRATION:", "  " + ep.get("narration_script", "").replace("\n", "\n  "), "",
                  "  SCENE: " + ep.get("scene_description", ""), "",
                  f"  CINEMATIC SHOTS: {len(ep.get('scene_plan') or [])}", ""]
        for j, shot in enumerate(ep.get("scene_plan") or [], 1):
            if isinstance(shot, dict):
                lines.append(f"    {j}. {shot.get('shot_type','')} | {shot.get('camera','')} | {shot.get('emotion','')} | {shot.get('action','')}")
        lines += ["", "-" * 70, ""]
    (project_dir / "script.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate cinematic serialized story videos.")
    parser.add_argument("--topic")
    parser.add_argument("--resume")
    parser.add_argument("--episodes", type=int, default=config.NUM_EPISODES)
    parser.add_argument("--style", default=config.ART_STYLE)
    parser.add_argument("--images", type=int, default=config.IMAGES_PER_EPISODE)
    parser.add_argument("--voice", default=config.TTS_VOICE)
    parser.add_argument("--script-only", action="store_true")
    parser.add_argument("--font", default=config.CAPTION_FONT)
    parser.add_argument("--refresh-media", action="store_true", help="Regenerate images and final videos, keeping story/voice where possible.")
    parser.add_argument("--i2v", action="store_true", help="Use enabled local ComfyUI image-to-video workflow for scene clips.")
    args = parser.parse_args()

    require_binary("ffmpeg", "Install FFmpeg and add it to PATH.")
    require_binary("ffprobe", "FFprobe ships with FFmpeg.")
    if args.i2v:
        config.I2V_ENABLED = True

    if args.resume:
        project_dir = Path(args.resume)
        story_path = project_dir / "story.json"
        if not story_path.exists():
            log(f"No story.json in {project_dir}", "ERR")
            sys.exit(1)
        story = json.loads(story_path.read_text(encoding="utf-8"))
    elif args.topic:
        project_dir = config.OUTPUT_DIR / slugify(args.topic)
        story = load_or_build_story(project_dir, args.topic, args.episodes, args.style)
    else:
        parser.error("Provide either --topic or --resume.")

    if not args.script_only:
        if ensure_scene_plans(story, args.images):
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "story.json").write_text(json.dumps(story, indent=2), encoding="utf-8")
            log("Cinematic scene plans saved.", "OK")
    write_readable_script(story, project_dir)

    if args.script_only:
        log("Script saved. Review it, then resume the project.", "OK")
        return

    character_desc = story.get("character", {}).get("physical_description", "")
    style = story.get("style", args.style)
    episodes = story["episodes"]
    rendered = []

    for day, episode in enumerate(episodes, start=1):
        log(f"--- Part {day}/{len(episodes)}: {episode.get('title', '')} ---")
        ep_dir = project_dir / f"part{day}"
        final_path = ep_dir / f"part{day}.mp4"
        if final_path.exists() and final_path.stat().st_size > 100_000 and not args.refresh_media:
            rendered.append(final_path)
            continue

        images = fetch_scene_images(episode, character_desc, style, ep_dir, day, count=args.images, force=args.refresh_media)
        audio = generate_voiceover(episode["narration_script"], ep_dir / "voice.mp3", voice=args.voice)

        media = images
        if config.I2V_ENABLED:
            generated = []
            for i, image in enumerate(images, 1):
                shot = (episode.get("scene_plan") or [])[i - 1] if i - 1 < len(episode.get("scene_plan") or []) else {}
                clip = ep_dir / f"motion_{i}.mp4"
                if clip.exists() and clip.stat().st_size > 10_000 and not args.refresh_media:
                    generated.append(clip)
                    continue
                result = generate_clip(image, shot.get("motion_prompt", "subtle natural movement"), clip)
                generated.append(result or image)
            media = generated

        render_episode(media, audio, episode["narration_script"], final_path, font=args.font, scene_plan=episode.get("scene_plan"))
        caption = llm.generate_caption(episode.get("title", ""), episode["narration_script"], day, len(episodes))
        (ep_dir / "caption.txt").write_text(caption, encoding="utf-8")
        rendered.append(final_path)

    log(f"Done. {len(rendered)} videos ready in {project_dir}", "OK")
    for path in rendered:
        log(f"  {path}")


if __name__ == "__main__":
    main()
