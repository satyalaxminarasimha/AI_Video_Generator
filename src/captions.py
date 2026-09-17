"""ASS captions with optional word-level Whisper timing."""
import re
from . import config
from .voice import clean_for_speech

ASS_HEADER = """[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\nYCbCr Matrix: TV.601\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_lr},{margin_lr},{margin_v},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""


def chunk_text(text, words_per_chunk=None):
    words_per_chunk = words_per_chunk or config.CAPTION_WORDS_PER_CHUNK
    text = clean_for_speech(text)
    chunks = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = sentence.split()
        for i in range(0, len(words), words_per_chunk):
            piece = " ".join(words[i:i + words_per_chunk]).strip()
            if piece:
                chunks.append(piece)
    return chunks


def _ass_time(seconds):
    cs = max(0, int(round(seconds * 100)))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text):
    return text.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def transcribe_words(audio_path):
    """Return [(start, end, word)] using faster-whisper when enabled."""
    if not config.WHISPER_ENABLED:
        return []
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []
    model = WhisperModel(config.WHISPER_MODEL, device="auto", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), word_timestamps=True, vad_filter=True)
    words = []
    for segment in segments:
        for word in segment.words or []:
            token = word.word.strip()
            if token:
                words.append((float(word.start), float(word.end), token))
    return words


def build_captions(text, duration, out_path, font=None, lead_in=0.15, word_timings=None):
    font = font or config.CAPTION_FONT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = ASS_HEADER.format(w=config.IMAGE_W, h=config.IMAGE_H, font=font, size=config.CAPTION_FONTSIZE,
                              outline=config.CAPTION_OUTLINE, shadow=config.CAPTION_SHADOW,
                              margin_lr=config.CAPTION_MARGIN_LR, margin_v=config.CAPTION_MARGIN_V)
    cues = []
    if word_timings:
        words = word_timings
        step = config.CAPTION_WORDS_PER_CHUNK
        for i in range(0, len(words), step):
            group = words[i:i + step]
            start = max(0, group[0][0])
            end = min(duration, group[-1][1] + 0.08)
            cues.append((start, max(end, start + 0.15), " ".join(w[2] for w in group)))
    else:
        chunks = chunk_text(text)
        weights = [max(len(c), 1) for c in chunks]
        total_weight = sum(weights) or 1
        usable = max(duration - lead_in, 0.5)
        cursor = lead_in
        for chunk, weight in zip(chunks, weights):
            span = usable * weight / total_weight
            cues.append((cursor, cursor + span, chunk))
            cursor += span
    lines = [header]
    for start, end, chunk in cues:
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{_escape(chunk)}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path, cues
