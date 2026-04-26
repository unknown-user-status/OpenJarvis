"""Groq TTS backend — cloud-based voice synthesis via Groq Orpheus API.

Requires the canopylabs/orpheus-v1-english model terms to be accepted
at https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english

Falls back gracefully if the model is not available on the account.
"""

from __future__ import annotations

import os
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

_GROQ_TTS_MODEL = "canopylabs/orpheus-v1-english"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Available voices for Orpheus English
_VOICES = ["autumn", "diana", "hannah", "austin", "daniel", "troy"]


@TTSRegistry.register("groq_tts")
class GroqTTSBackend(TTSBackend):
    """Groq Orpheus TTS backend — cloud synthesis via Groq API."""

    backend_id = "groq_tts"

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = _GROQ_TTS_MODEL,
        voice: str = "hannah",
    ) -> None:
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._model = model
        self._default_voice = voice

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> TTSResult:
        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY not set")

        voice = voice_id or self._default_voice

        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package not installed")

        client = OpenAI(api_key=self._api_key, base_url=_GROQ_BASE_URL)

        resp = client.audio.speech.create(
            model=self._model,
            voice=voice,
            input=text,
            response_format=output_format,
        )

        audio_bytes = resp.content

        return TTSResult(
            audio=audio_bytes,
            format=output_format,
            voice_id=voice,
            metadata={"backend": "groq_tts", "model": self._model},
        )

    def available_voices(self) -> List[str]:
        return list(_VOICES)

    def health(self) -> bool:
        return bool(self._api_key)


def speak(text: str, *, api_key: str = "", voice: str = "hannah") -> bool:
    """Convenience function: synthesize *text* and play it via sounddevice.

    Returns True on success, False if TTS is unavailable (e.g. terms not
    accepted) so callers can fall back to text-only output.
    """
    api_key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return False

    try:
        import io
        import sounddevice as sd
        import soundfile as sf

        backend = GroqTTSBackend(api_key=api_key, voice=voice)
        result = backend.synthesize(text, output_format="wav")

        audio_buf = io.BytesIO(result.audio)
        data, samplerate = sf.read(audio_buf)
        sd.play(data, samplerate)
        sd.wait()
        return True

    except Exception as exc:
        # Common failure: terms not yet accepted (BadRequestError 400)
        import logging
        logging.getLogger(__name__).debug("Groq TTS unavailable: %s", exc)
        return False


__all__ = ["GroqTTSBackend", "speak"]
