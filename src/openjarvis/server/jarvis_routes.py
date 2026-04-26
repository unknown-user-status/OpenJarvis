"""OpenJarvis core API routes — chat, voice (STT), and TTS.

Endpoints
---------
POST /api/jarvis/chat
    Accept {text: str} → run plugin dispatch / LLM → return {response, mode}

POST /api/jarvis/voice
    Accept multipart audio file → Groq Whisper STT → dispatch → return
    {transcript, response, mode, audio_b64?}

POST /api/jarvis/tts
    Accept {text: str, voice?: str} → Groq Orpheus TTS → return audio/wav bytes

GET  /api/jarvis/health
    Quick health-check: {ok, tts_available, groq_key_set}
"""

from __future__ import annotations

import base64
import io
import logging
import os
import pathlib
import sys
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger("openjarvis.server.jarvis")

try:
    from fastapi import APIRouter, HTTPException, UploadFile, File
    from fastapi.responses import Response, JSONResponse
    from pydantic import BaseModel
except ImportError:
    raise ImportError("fastapi and pydantic are required")

jarvis_router = APIRouter(prefix="/api/jarvis", tags=["jarvis"])

# ---------------------------------------------------------------------------
# Bootstrap the plugin system once when the module is loaded
# ---------------------------------------------------------------------------

_PLUGINS_LOADED = False

def _ensure_plugins() -> None:
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED:
        return
    try:
        # Make sure src/ is on sys.path
        _src = str(pathlib.Path(__file__).parents[3])
        if _src not in sys.path:
            sys.path.insert(0, _src)
        custom_dir = pathlib.Path(__file__).parents[4] / "custom"
        from openjarvis.plugins import load_directory
        load_directory(custom_dir)
        _PLUGINS_LOADED = True
        logger.info("OpenJarvis plugins loaded from %s", custom_dir)
    except Exception as exc:
        logger.warning("Plugin loading failed: %s", exc)


# ---------------------------------------------------------------------------
# Routing helpers (mirrored from jarvis-voice.py)
# ---------------------------------------------------------------------------

_PLUGIN_TRIGGERS = (
    "time", "date", "day", "today",
    "news", "headlines", "top news",
    "weather",
    "note", "make a note", "write this down", "remember this",
    "read notes", "show notes", "my notes",
    "remember", "memorize", "what do you know", "my memory",
    "show memory", "forget", "recall",
    "joke", "tell a joke",
    "tell me about", "who is", "what is", "wikipedia", "wiki",
    "system", "cpu", "ram", "battery", "disk", "ip address",
    "where am i", "my location", "current location", "where is",
    "play", "youtube", "play music", "search youtube", "play on youtube",
    "search", "google", "web search", "search web", "look up",
    "find information",
    "calculate",
    "email", "send email",
    "open ", "launch", "start app",
    "list files", "show files", "read file", "find file", "disk usage",
    "disk space", "create file", "delete file", "rename file", "move file",
    "list desktop", "show desktop files", "organize desktop", "clean desktop",
    "set wallpaper", "wallpaper from url", "change wallpaper",
    "volume up", "volume down", "mute", "set volume",
    "brightness up", "brightness down",
    "minimize window", "maximize window", "fullscreen",
    "switch window", "lock screen",
    "close tab", "new tab", "next tab",
    "zoom in", "zoom out",
    "scroll up", "scroll down",
    "copy", "paste", "undo", "redo", "select all", "save file",
    "type text", "take screenshot", "capture screen",
    "remind me", "reminder", "set reminder", "set a reminder",
    "analyze screen", "what's on my screen", "look at screen",
    "screen analysis", "what do you see",
    "hello", "hi", "hey", "good morning", "good evening",
    "good afternoon", "goodbye", "bye",
)

_CONTROL_KEYWORDS = (
    "click on ", "double click on", "right click on", "drag ",
    "press key ", "key down ", "key up ",
    "focus on ", "switch to window", "close the window",
    "restore window", "go to website", "navigate to ",
)


def _classify(text: str) -> str:
    lower = text.lower().strip()
    if any(kw in lower for kw in _CONTROL_KEYWORDS):
        return "control"
    if any(lower.startswith(kw) or (kw.strip() in lower) for kw in _PLUGIN_TRIGGERS):
        return "plugin"
    return "qa"


def _dispatch_plugin(command: str, api_key: str) -> Optional[str]:
    try:
        from openjarvis.plugins import dispatch, JarvisContext
        ctx = JarvisContext(api_key=api_key)
        return dispatch(command, ctx)
    except Exception as exc:
        logger.warning("Plugin dispatch error: %s", exc)
        return None


def _llm_answer(question: str, api_key: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

        # Build memory-aware system prompt
        system_prompt = (
            "You are OpenJarvis, an advanced AI assistant. "
            "Give concise, helpful answers. Be accurate. Keep responses under 3 sentences "
            "unless the question genuinely needs more detail."
        )
        try:
            from openjarvis.memory.memory_manager import load_memory, format_memory_for_prompt
            mem = load_memory()
            mem_block = format_memory_for_prompt(mem)
            if mem_block:
                system_prompt += "\n\n" + mem_block
        except Exception:
            pass

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=512,
            temperature=0.7,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM error: %s", exc)
        raise


def _run_desktop(goal: str, api_key: str) -> str:
    try:
        from openjarvis.agents.desktop_agent import DesktopAgent
        agent = DesktopAgent(api_key=api_key, max_steps=15, step_delay=1.5, verbose=False)
        return agent.run(goal)
    except Exception as exc:
        return f"Desktop control failed: {exc}"


def _synthesize_tts(text: str, api_key: str, voice: str = "hannah") -> bytes:
    """Return WAV bytes for *text* using Groq Orpheus TTS."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    resp = client.audio.speech.create(
        model="canopylabs/orpheus-v1-english",
        voice=voice,
        input=text,
        response_format="wav",
    )
    return resp.content


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    text: str
    tts: bool = False        # if True, include base64 WAV in response
    voice: str = "hannah"


class ChatResponse(BaseModel):
    response: str
    mode: str                # 'plugin' | 'control' | 'qa'
    audio_b64: Optional[str] = None   # WAV base64 if tts=True


class TTSRequest(BaseModel):
    text: str
    voice: str = "hannah"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@jarvis_router.get("/health")
async def jarvis_health():
    api_key = os.environ.get("GROQ_API_KEY", "")
    tts_ok = False
    if api_key:
        try:
            from openjarvis.speech.groq_tts import GroqTTSBackend
            tts_ok = GroqTTSBackend(api_key=api_key).health()
        except Exception:
            pass
    return {"ok": True, "tts_available": tts_ok, "groq_key_set": bool(api_key)}


@jarvis_router.post("/chat", response_model=ChatResponse)
async def jarvis_chat(request: ChatRequest):
    """Process a text command and return Jarvis's response (+ optional TTS audio)."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not set")

    _ensure_plugins()
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    mode = _classify(text)
    response_text = ""

    if mode == "plugin":
        result = _dispatch_plugin(text, api_key)
        if result:
            response_text = result
        else:
            # plugin didn't match — fall through to LLM
            mode = "qa"

    if mode == "control":
        response_text = _run_desktop(text, api_key)

    if not response_text:
        mode = "qa"
        response_text = _llm_answer(text, api_key)

    # Optional TTS
    audio_b64 = None
    if request.tts and response_text:
        try:
            wav_bytes = _synthesize_tts(response_text, api_key, voice=request.voice)
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except Exception as exc:
            logger.debug("TTS synthesis skipped: %s", exc)

    return ChatResponse(response=response_text, mode=mode, audio_b64=audio_b64)


@jarvis_router.post("/voice")
async def jarvis_voice(audio: UploadFile = File(...), tts: bool = False, voice: str = "hannah"):
    """Accept audio → Whisper STT → dispatch → return JSON with optional TTS WAV."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not set")

    _ensure_plugins()

    # Save upload to temp file
    suffix = "." + (audio.filename or "audio.webm").rsplit(".", 1)[-1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    transcript = ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text",
            )
        transcript = result.strip() if isinstance(result, str) else str(result).strip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not transcript:
        return JSONResponse({"transcript": "", "response": "Could not understand audio.", "mode": "qa", "audio_b64": None})

    mode = _classify(transcript)
    response_text = ""

    if mode == "plugin":
        result = _dispatch_plugin(transcript, api_key)
        if result:
            response_text = result
        else:
            mode = "qa"

    if mode == "control":
        response_text = _run_desktop(transcript, api_key)

    if not response_text:
        mode = "qa"
        response_text = _llm_answer(transcript, api_key)

    audio_b64 = None
    if tts and response_text:
        try:
            wav_bytes = _synthesize_tts(response_text, api_key, voice=voice)
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except Exception as exc:
            logger.debug("TTS skipped: %s", exc)

    return JSONResponse({
        "transcript": transcript,
        "response": response_text,
        "mode": mode,
        "audio_b64": audio_b64,
    })


@jarvis_router.post("/tts")
async def jarvis_tts(request: TTSRequest):
    """Synthesize text to WAV bytes via Groq Orpheus TTS."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not set")
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    try:
        wav_bytes = _synthesize_tts(request.text, api_key, voice=request.voice)
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}")


__all__ = ["jarvis_router"]
