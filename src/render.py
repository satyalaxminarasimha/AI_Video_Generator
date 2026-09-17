"""Cinematic FFmpeg renderer.

Features:
- variable scene durations from shot weights
- camera-specific Ken Burns movement
- cuts/fades between shots
- optional emotion-matched music
- optional timestamped sound effects from assets/sfx
- optional Whisper word-level captions
- 1080x1920 H.264/AAC output
"""
import subprocess
from pathlib import Path

from . import config
from .audiofx import find_sfx, pick_music
from .captions import build_captions, transcribe_words
from .cinematic import normalize_shot_plan
from .utils import audio_duration, log


def _camera_filter(idx, frames, camera):
    """Create a stable camera move over a still image."""
    scale = f"scale={config.IMAGE_W * 2}:{config.IMAGE_H * 2},setsar=1"
    camera = camera or "medium"
    if camera == "push_in":
        z = "min(zoom+0.0015,1.28)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif camera == "pull_out":
        z = "if(lte(zoom,1.0),1.28,max(1.001,zoom-0.0015))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif camera == "pan_left":
        z = "1.12"
        x = "iw/2-(iw/zoom/2)-(on/{f})*140".format(f=max(frames, 1))
        y = "ih/2-(ih/zoom/2)"
    elif camera == "pan_right":
        z = "1.12"
        x = "iw/2-(iw/zoom/2)+(on/{f})*140".format(f=max(frames, 1))
        y = "ih/2-(ih/zoom/2)"
    elif camera == "tilt_up":
        z = "1.10"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)-(on/{f})*100".format(f=max(frames, 1))
    elif camera == "tilt_down":
        z = "1.10"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)+(on/{f})*100".format(f=max(frames, 1))
    elif camera == "handheld":
        z = "1.10+0.015*sin(on*0.22)"
        x = "iw/2-(iw/zoom/2)+18*sin(on*0.13)"
        y = "ih/2-(ih/zoom/2)+14*cos(on*0.17)"
    elif camera == "static":
        z = "1.03"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:
        z = "min(zoom+0.001,1.16)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    return f"scale={config.IMAGE_W * 2}:{config.IMAGE_H * 2},setsar=1,zoompan=z='{z}':d={frames}:x='{x}':y='{y}':s={config.IMAGE_W}x{config.IMAGE_H}:fps={config.FPS},format=yuv420p"


def _scene_plan(episode, n):
    raw = episode.get("scene_plan") or []
    return normalize_shot_plan(raw, n)


def _scene_durations(plans, available):
    weights = [p.get("duration_weight", 1) or 1 for p in plans]
    total_weight = sum(weights)
    # Reserve a little time for scene changes while guaranteeing every scene a
    # visible duration. The narration duration remains the master clock.
    minimum = min(1.4, available / max(len(plans), 1))
    remaining = max(available - minimum * len(plans), 0.1)
    return [minimum + remaining * (w / total_weight) for w in weights]


def render_episode(image_paths, audio_path, narration_text, out_path, music_path=None, font=None, scene_plan=None):
    """Render an episode. image_paths may also contain generated .mp4/.webm clips."""
    image_paths = [Path(p).resolve() for p in image_paths]
    audio_path = Path(audio_path).resolve()
    out_path = Path(out_path).resolve()
    work_dir = out_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)

    duration = audio_duration(audio_path)
    total = duration + config.TAIL_SECONDS
    plans = normalize_shot_plan(scene_plan or [], len(image_paths))
    scene_durs = _scene_durations(plans, total)
    frame_counts = [max(2, int(round(d * config.FPS))) for d in scene_durs]
    actual_total = sum(frame_counts) / config.FPS
    total = duration + config.TAIL_SECONDS
    log(f"  cinematic render: {len(image_paths)} shots, narration {duration:.1f}s")

    words = []
    if config.WHISPER_ENABLED:
        try:
            words = transcribe_words(audio_path)
            if words:
                log("  using Whisper word-level caption timing", "OK")
        except Exception as exc:  # noqa: BLE001
            log(f"  Whisper unavailable, using estimated captions: {exc}", "WARN")
    ass_path = work_dir / "captions.ass"
    build_captions(narration_text, duration, ass_path, font=font or config.CAPTION_FONT, word_timings=words)

    # Build image inputs.
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for media in image_paths:
        if media.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".gif"}:
            cmd += ["-stream_loop", "-1", "-i", str(media)]
        else:
            cmd += ["-loop", "1", "-i", str(media)]
    cmd += ["-i", str(audio_path)]

    audio_idx = len(image_paths)
    music = music_path or pick_music((plans[0].get("emotion") if plans else "neutral"))
    music_idx = None
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]
        music_idx = audio_idx + 1

    # Optional SFX are added as individual inputs, then delayed to the shot start.
    sfx_inputs = []
    cursor = 0.0
    for plan, dur in zip(plans, scene_durs):
        sfx = find_sfx(plan.get("sound_effect"))
        sfx_inputs.append((sfx, cursor))
        if sfx:
            cmd += ["-i", str(sfx.resolve())]
        cursor += dur

    filters = []
    video_labels = []
    for i, (media, frames, plan, scene_dur) in enumerate(zip(image_paths, frame_counts, plans, scene_durs)):
        label = f"v{i}"
        if media.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".gif"}:
            filters.append(f"[{i}:v]trim=duration={scene_dur:.3f},setpts=PTS-STARTPTS,scale={config.IMAGE_W}:{config.IMAGE_H}:force_original_aspect_ratio=increase,crop={config.IMAGE_W}:{config.IMAGE_H},fps={config.FPS},format=yuv420p[{label}]")
        else:
            filters.append(f"[{i}:v]{_camera_filter(i, frames, plan.get('camera'))}[{label}]")
        # Fade to black only when requested. Most cuts remain clean and fast.
        if plan.get("transition") in {"fade", "flash"}:
            fade_d = min(config.CROSSFADE_SECONDS, scene_durs[i] / 3)
            st = max(scene_durs[i] - fade_d, 0)
            filters.append(f"[{label}]fade=t=out:st={st:.3f}:d={fade_d:.3f}[{label}f]")
            label = f"{label}f"
        video_labels.append(f"[{label}]")

    filters.append("".join(video_labels) + f"concat=n={len(video_labels)}:v=1:a=0[vcat]")
    filters.append("[vcat]subtitles=captions.ass[vout]")

    # Audio mix.
    audio_parts = ["[voice]"]
    filters.append(f"[{audio_idx}:a]volume=1.0,apad=pad_dur={config.TAIL_SECONDS}[voice]")
    if music_idx is not None:
        filters.append(f"[{music_idx}:a]volume={config.MUSIC_VOLUME},atrim=0:{total:.3f}[bg]")
        audio_parts.append("[bg]")

    next_idx = music_idx + 1 if music_idx is not None else audio_idx + 1
    for sfx, start in sfx_inputs:
        if sfx:
            idx = next_idx
            next_idx += 1
            delay = max(0, int(start * 1000))
            filters.append(f"[{idx}:a]volume=0.55,adelay={delay}|{delay},apad=pad_dur={total:.3f}[sfx{idx}]")
            audio_parts.append(f"[sfx{idx}]")

    filters.append("".join(audio_parts) + f"amix=inputs={len(audio_parts)}:duration=first:dropout_transition=0[aout]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", config.PRESET, "-crf", str(config.CRF),
        "-pix_fmt", "yuv420p", "-r", str(config.FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-t", f"{total:.3f}", "-movflags", "+faststart", out_path.name,
    ]

    proc = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True)
    if proc.returncode != 0:
        log("FFmpeg render failed", "ERR")
        print(proc.stderr[-5000:])
        raise RuntimeError("FFmpeg render failed")
    log(f"  rendered {out_path.name} ({out_path.stat().st_size / 1e6:.1f} MB)", "OK")
    return out_path
