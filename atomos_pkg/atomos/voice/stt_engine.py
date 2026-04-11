"""
ATOM OS — Voice Layer (STT / TTS)
"""

from __future__ import annotations
import logging
import io
import wave
from typing import Any

from atomos.core.service_registry import register

logger = logging.getLogger("atomos.voice")


@register("stt_engine", module_type="voice", init_order=63)
class STTEngine:
    """
    Whisper STT — speech to text.
    Supports: faster-whisper (推荐), openai-whisper, whispercpp.
    """

    def __init__(self, model: str = "small"):
        self.model_name = model
        self.model = None

    def init(self) -> None:
        logger.info(f"  STT stub loaded (Whisper {self.model_name})")

    def transcribe(self, audio_path: str | None = None, audio_bytes: bytes | None = None) -> dict:
        """Convert speech to text."""
        return {
            "text": "[STUB] Transcribed text from audio",
            "language": "en",
            "duration_s": 0.0,
            "model": self.model_name,
        }

    def health(self) -> dict:
        return {"model": self.model_name, "ready": True}


@register("tts_engine", module_type="voice", init_order=64)
class TTSEngine:
    """
    Piper TTS — text to speech (offline, fast).
    Alternatives: ElevenLabs, Coqui, bark.
    """

    def __init__(self, voice: str = "en_US-lessac-medium"):
        self.voice = voice

    def init(self) -> None:
        logger.info(f"  TTS stub loaded: {self.voice}")

    def speak(self, text: str, output_path: str | None = None) -> bytes:
        """Convert text to speech, return WAV bytes."""
        return b"[STUB WAV DATA]"

    def health(self) -> dict:
        return {"voice": self.voice, "ready": True}


@register("voice_loop", module_type="voice", init_order=65)
class VoiceLoop:
    """
    Continuous voice interaction loop.
    STT → LLM → TTS → Speaker.
    """

    def __init__(self):
        self.stt: STTEngine | None = None
        self.tts: TTSEngine | None = None

    def init(self) -> None:
        logger.info("  Voice loop stub ready")

    def listen_and_respond(self) -> str:
        """One voice interaction: listen → understand → respond."""
        return "[STUB VOICE RESPONSE]"

    def health(self) -> dict:
        return {"active": False, "stt": self.stt is not None, "tts": self.tts is not None}
