"""Central configuration. Reads .env, then environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
MUSIC_DIR = ASSETS_DIR / "music"
SFX_DIR = ASSETS_DIR / "sfx"


def _load_dotenv():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

NUM_EPISODES = int(os.environ.get("NUM_EPISODES", "5"))
ART_STYLE = os.environ.get(
    "ART_STYLE",
    "cinematic illustrated digital painting, warm dramatic lighting, semi-realistic, muted film grain, high detail",
)

IMAGES_PER_EPISODE = int(os.environ.get("IMAGES_PER_EPISODE", "8"))
IMAGE_SEED = int(os.environ.get("IMAGE_SEED", "42"))
IMAGE_W, IMAGE_H = 1080, 1920

TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-GuyNeural")
TTS_RATE = os.environ.get("TTS_RATE", "+8%")

FPS = int(os.environ.get("FPS", "25"))
MUSIC_VOLUME = float(os.environ.get("MUSIC_VOLUME", "0.10"))
CAPTION_FONTSIZE = int(os.environ.get("CAPTION_FONTSIZE", "68"))
CAPTION_OUTLINE = int(os.environ.get("CAPTION_OUTLINE", "5"))
CAPTION_SHADOW = int(os.environ.get("CAPTION_SHADOW", "2"))
CAPTION_MARGIN_LR = int(os.environ.get("CAPTION_MARGIN_LR", "90"))
CAPTION_MARGIN_V = int(os.environ.get("CAPTION_MARGIN_V", "380"))
CAPTION_FONT = os.environ.get("CAPTION_FONT", "DejaVu Sans")
CAPTION_WORDS_PER_CHUNK = int(os.environ.get("CAPTION_WORDS_PER_CHUNK", "5"))

# Cinematic rendering
TAIL_SECONDS = float(os.environ.get("TAIL_SECONDS", "0.6"))
CROSSFADE_SECONDS = float(os.environ.get("CROSSFADE_SECONDS", "0.20"))
CRF = int(os.environ.get("VIDEO_CRF", "20"))
PRESET = os.environ.get("VIDEO_PRESET", "medium")

# Optional word-level captions. Install faster-whisper separately to enable.
WHISPER_ENABLED = os.environ.get("WHISPER_ENABLED", "0") == "1"
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")

# Optional local ComfyUI image-to-video adapter. Disabled by default.
I2V_ENABLED = os.environ.get("I2V_ENABLED", "0") == "1"
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
COMFYUI_WORKFLOW = Path(os.environ.get("COMFYUI_WORKFLOW", str(ROOT / "workflows" / "i2v_workflow.json")))
I2V_CLIP_SECONDS = float(os.environ.get("I2V_CLIP_SECONDS", "4"))
I2V_TIMEOUT_SECONDS = int(os.environ.get("I2V_TIMEOUT_SECONDS", "180"))
