# AI Story Video — Cinematic Edition

Turns one story premise into a serialized set of vertical videos.

## Pipeline

```text
Premise
  -> Gemini story + critique + revision
  -> character identity anchor
  -> chronological cinematic shot plan
  -> Pollinations scene images
  -> edge-tts narration
  -> optional Whisper word timestamps
  -> camera-aware cinematic animation
  -> optional image-to-video via local ComfyUI
  -> emotion-aware music + optional SFX
  -> ASS captions
  -> FFmpeg 1080x1920 MP4
```

## What was improved

- **Shot-level planning:** Gemini now creates visual prompts, motion prompts, camera direction, emotion, action, transition, sound-effect label and duration weight for every shot.
- **Better visual variety:** wide/medium/close/over-shoulder/low-angle/top-down shot types and camera presets are supported.
- **Dynamic timing:** important shots receive more screen time instead of every image getting an equal duration.
- **Cinematic camera motion:** push-in, pull-out, pan, tilt, handheld and static presets replace the single repeating zoom pattern.
- **Better captions:** optional faster-whisper word timestamps can replace character-count estimation.
- **Sound design:** put matching files such as `rain.wav`, `door_open.wav`, `footsteps.wav` and `impact.wav` in `assets/sfx/` and they are placed automatically.
- **Emotion-aware music:** music filenames can contain an emotion such as `sad.mp3`, `tension.mp3` or `happy.mp3`.
- **Optional true motion:** a local ComfyUI image-to-video adapter is included. The default renderer remains lightweight and works without it.
- **Resume/refresh:** existing story, images, voice and final videos remain reusable.
- **Secrets and generated files:** `.gitignore` excludes `.env`, virtual environments and generated media.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install FFmpeg and make sure both commands work:

```powershell
ffmpeg -version
ffprobe -version
```

Copy `.env.example` to `.env` and add your Gemini API key.

## Generate

Script only:

```powershell
python run.py --topic "A poor boy is treated badly until he reveals a secret" --script-only
```

Normal cinematic render:

```powershell
python run.py --topic "A poor boy is treated badly until he reveals a secret" --images 8
```

Resume an existing project:

```powershell
python run.py --resume "output\your-story-slug"
```

Regenerate images and video while keeping the story/voice when possible:

```powershell
python run.py --resume "output\your-story-slug" --images 8 --refresh-media
```

## Optional Whisper captions

Install:

```powershell
pip install faster-whisper
```

Then set:

```text
WHISPER_ENABLED=1
WHISPER_MODEL=base
```

The first run may download the selected Whisper model.

## Optional true image-to-video motion

The project includes a generic local ComfyUI adapter because different ComfyUI installations use different I2V models and custom nodes.

1. Install and run ComfyUI locally.
2. Export an **API-format workflow JSON** into `workflows/i2v_workflow.json`.
3. Put these literal placeholders into the workflow where appropriate:
   - `{image}` — input image
   - `{prompt}` — motion prompt
   - `{duration}` — clip duration
4. Configure `.env`:

```text
I2V_ENABLED=1
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW=workflows/i2v_workflow.json
I2V_CLIP_SECONDS=4
I2V_TIMEOUT_SECONDS=180
```

Then run:

```powershell
python run.py --resume "output\your-story-slug" --images 8 --i2v
```

If ComfyUI or the workflow fails, the pipeline falls back to the normal still-image cinematic renderer.

> Note: the I2V adapter is intentionally model-agnostic. A ComfyUI workflow must be exported with nodes that accept the image and prompt and save a video-compatible output.

## Optional sound effects

Put short files in `assets/sfx/`:

```text
assets/sfx/
  footsteps.wav
  door_open.wav
  rain.wav
  phone.wav
  impact.wav
```

The Gemini shot plan selects labels such as `rain`, `door_open`, and `impact`; the renderer searches for matching filenames and places them at the start of the corresponding shot.

## Music

Put music in `assets/music/`. Emotion-aware matching is based on the filename. Examples:

```text
sad.mp3
tension.mp3
happy.mp3
reveal.mp3
```

If no matching emotion exists, the first available music track is used.

## Testing

The offline self-test does not require Gemini, Pollinations, edge-tts, Whisper or ComfyUI:

```powershell
python selftest.py
```

A healthy result is:

```text
8 passed, 0 failed
```

## Important limitation

Without I2V, characters are still represented by generated images. The renderer creates cinematic camera motion, dynamic timing, captions and sound design. **Actual walking, lip movement, facial motion and body animation require an image-to-video model**, which can be enabled through the optional ComfyUI adapter.
