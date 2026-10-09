"""Audio layer — text-to-speech for answers, quizzes and study briefs.

Uses edge-tts (free, high-quality neural voices, no API key). Every spoken
artifact is cached on disk keyed by content hash, so repeated requests are
instant and the app works offline after first synthesis.

EchoScholar is audio-first: every tutor answer, quiz question, feedback
message and study brief can be listened to — the UI autoplays the audio and
the same content remains available as text for sighted and screen-reader users.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

AUDIO_DIR = Path(__file__).parent.parent / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_VOICE = "en-US-AriaNeural"
VOICES = {
    "en": "en-US-AriaNeural",
    "en-male": "en-US-GuyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ja-male": "ja-JP-KeitaNeural",
    "hi": "hi-IN-SwaraNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
}


def _key(text: str, voice: str) -> str:
    return hashlib.sha1(f"{voice}:{text}".encode("utf-8")).hexdigest()[:20]


async def _synth(text: str, voice: str, out: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out))


def synthesize(text: str, voice: str = DEFAULT_VOICE) -> Path:
    """Text -> mp3 file (cached). Returns the audio path."""
    text = text.strip()
    if not text:
        raise ValueError("empty text")
    out = AUDIO_DIR / f"{_key(text, voice)}.mp3"
    if not out.exists():
        asyncio.run(_synth(text, voice, out))
    return out


def _clean_for_speech(text: str) -> str:
    """Strip markdown/citation noise so the spoken version flows naturally."""
    import re

    t = text
    t = re.sub(r"\[u[0-9a-f]{8}\]", "", t)          # citation markers
    t = re.sub(r"`([^`]+)`", r"\1", t)               # inline code
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)         # bold
    t = re.sub(r"#+\s*", "", t)                      # headings
    t = re.sub(r"^\s*[-*]\s+", "", t, flags=re.M)    # bullets
    t = re.sub(r"NOT_COVERED:\s*", "", t)
    t = re.sub(r"https?://\S+", "link", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def answer_audio(answer_text: str, voice: str = DEFAULT_VOICE) -> Path:
    return synthesize(_clean_for_speech(answer_text), voice)


def brief_audio(
    learner_report: dict,
    topics: list[dict],
    *,
    student_name: str = "there",
    voice: str = DEFAULT_VOICE,
) -> Path:
    """Spoken study brief: greets, lists weak topics with key concepts, suggests next steps."""
    lines: list[str] = [f"Hi {student_name}, here is your study brief."]
    weak = learner_report.get("weak_topics", [])
    strong = learner_report.get("strong_topics", [])
    topic_by_name = {t["name"]: t for t in topics}

    if weak:
        lines.append(f"You have {len(weak)} topics that need attention.")
        for name in weak[:4]:
            t = topic_by_name.get(name, {})
            concepts = ", ".join(t.get("key_concepts", [])[:3])
            pct = int(learner_report["topics"].get(name, {}).get("mastery", 0.25) * 100)
            line = f"{name}: your estimated mastery is {pct} percent."
            if concepts:
                line += f" Focus on: {concepts}."
            lines.append(line)
    else:
        lines.append("No weak topics detected yet. Take a quiz so I can find gaps.")

    if strong:
        lines.append(f"Great work on: {', '.join(strong[:3])}.")

    lines.append("Open the quiz tab and pick one of these topics to start closing the gap.")
    return synthesize(" ".join(lines), voice)
