"""Gemini-powered story, character and cinematic shot planning."""
import time
import requests
from . import config
from .utils import clean_json, log


def _call(prompt, temperature=0.9, retries=3):
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env.")
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperature, "maxOutputTokens": 12000}}
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.post(config.GEMINI_URL, headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY}, json=payload, timeout=120)
            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                log(f"Rate limited by Gemini, waiting {wait}s...", "WARN")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log(f"Gemini call failed ({attempt + 1}/{retries}): {exc}", "WARN")
            time.sleep(5)
    raise RuntimeError(f"Gemini call failed after {retries} attempts: {last_err}")


def generate_script(topic, num_episodes, style):
    log("Writing first draft of the script...")
    prompt = f"""You are a viral short-form video scriptwriter for YouTube Shorts / Instagram Reels.
PREMISE: {topic}
Write a {num_episodes}-part serialized story. Each part should be roughly 150-200 spoken words.
Part 1 must hook immediately. Every non-final part ends with a genuine cliffhanger. The final part has a satisfying payoff.
Write natural spoken narration: short sentences, concrete details, present tense. No stage directions or speaker labels.
Output STRICT JSON ONLY: an array of exactly {num_episodes} objects with keys title, narration_script, scene_description, emotional_beat."""
    return _call(prompt)


def critique_script(script_text):
    log("Critiquing the draft...")
    prompt = f"""Review this serialized short-video script for hook, pacing, cliffhangers, payoff and spoken-naturalness. Give concrete weaknesses as bullets only.
SCRIPT:\n{script_text}"""
    return _call(prompt, temperature=0.7)


def revise_script(original, critique, num_episodes):
    log("Revising the script...")
    prompt = f"""Revise the script using the critique. Keep the story and character. Strengthen hook, pacing and cliffhangers.
Return STRICT JSON ONLY: an array of exactly {num_episodes} objects with keys title, narration_script, scene_description, emotional_beat.
ORIGINAL:\n{original}\nCRITIQUE:\n{critique}"""
    return _call(prompt, temperature=0.8)


def generate_character(topic):
    log("Designing the main character...")
    prompt = f"""Based on this premise: {topic}
Create one main character. physical_description must be precise and repeatable: age, skin tone, hair, build, face, clothing and defining feature. Appearance only.
Return STRICT JSON ONLY with character_name, age, physical_description, personality."""
    return _call(prompt, temperature=0.8)


def generate_scene_plan(narration, scene_description, count, character_name="Main character"):
    """Create chronological shot-level visual + motion plans."""
    log(f"Planning {count} cinematic shots from narration...")
    prompt = f"""You are a film director planning a vertical short video.
NARRATION:\n{narration}\n
ORIGINAL VISUAL IDEA:\n{scene_description}\n
Create exactly {count} chronological shots. Each shot must correspond to the next beat of the narration. Do not invent unrelated events.
Return STRICT JSON ONLY as an array. Each object MUST contain:
- visual_prompt: what is visible, including character, setting and action
- motion_prompt: natural movement for an image-to-video model, even if subtle
- shot_type: wide, medium, close, over_shoulder, low_angle, top_down
- camera: static, push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down, handheld
- emotion: one short emotion
- action: concrete action
- transition: cut, crossfade, fade, flash
- sound_effect: optional simple label such as footsteps, door_open, rain, phone, impact, none
- duration_weight: integer 1-5 indicating visual importance
Character reference name: {character_name}."""
    raw = clean_json(_call(prompt, temperature=0.45))
    if not isinstance(raw, list):
        raise ValueError("Scene planner did not return a list")
    return raw


def generate_caption(title, narration, day, total):
    prompt = f"""Write a social caption for part {day} of {total} titled \"{title}\". One or two teaser lines, then a follow-for-next-part line unless final, then exactly 12 hashtags. Plain text only.\n{narration[:900]}"""
    try:
        return _call(prompt, temperature=0.9).strip()
    except Exception as exc:
        log(f"Caption generation failed: {exc}", "WARN")
        return f"{title}\n\nPart {day} of {total}."


def build_story(topic, num_episodes, style):
    draft = generate_script(topic, num_episodes, style)
    critique = critique_script(draft)
    episodes = clean_json(revise_script(draft, critique, num_episodes))
    character = clean_json(generate_character(topic))
    if not isinstance(episodes, list):
        raise ValueError("Expected JSON array of episodes")
    log(f"Character locked: {character.get('character_name', '?')}", "OK")
    return {"topic": topic, "style": style, "character": character, "critique": critique, "episodes": episodes}
