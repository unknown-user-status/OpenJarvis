"""OpenJarvis core API routes — chat, voice (STT), TTS, and camera vision.

Endpoints
---------
POST /api/jarvis/chat
    Accept {text: str} → run plugin dispatch / LLM → return {response, mode}

POST /api/jarvis/voice
    Accept multipart audio file → Groq Whisper STT → dispatch → return
    {transcript, response, mode, audio_b64?}

POST /api/jarvis/tts
    Accept {text: str, voice?: str} → Groq Orpheus TTS → return audio/wav bytes

POST /api/jarvis/camera
    Accept {question?: str, image_b64?: str, tts?: bool, voice?: str}
    → capture webcam (or use provided image) → Ollama vision LLM → return
    {response, model, image_b64, audio_b64?}

GET  /api/jarvis/camera/models
    Return list of available Ollama vision models

GET  /api/jarvis/health
    Quick health-check: {ok, tts_available, groq_key_set, ollama_vision?}
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
    "goodbye", "bye",
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


_GREETINGS = {
    "hi", "hi jarvis", "hello", "hello jarvis", "hey", "hey jarvis",
    "good morning", "good afternoon", "good evening", "yo", "sup",
    "hi there", "hello there",
}

def _is_greeting(text: str) -> bool:
    return text.strip().lower().rstrip("!.,?") in _GREETINGS


def _llm_answer(question: str, api_key: str) -> tuple[str, int, int]:
    """Return (response_text, prompt_tokens, completion_tokens)."""
    # Short-circuit for pure greetings — no LLM call needed
    if _is_greeting(question):
        return "Hello! How are you? How can I help you today?", 0, 0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

        # Build memory-aware system prompt
        system_prompt = (
            "You are Jarvis, a friendly and helpful personal AI assistant. "
            "Give concise, helpful answers. Be accurate. Keep responses under 3 sentences "
            "unless the question genuinely needs more detail. "
            "The memory context below is for background only — do not volunteer it unless relevant."
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
        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        return resp.choices[0].message.content or "", prompt_tokens, completion_tokens
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
    prompt_tokens: int = 0
    completion_tokens: int = 0


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

    # Short-circuit greetings before classify/plugin/LLM
    if _is_greeting(text):
        response_text = "Hello! How are you? How can I help you today?"
        mode = "qa"
        prompt_tokens = 0
        completion_tokens = 0
    else:
        mode = _classify(text)
        response_text = ""
        prompt_tokens = 0
        completion_tokens = 0

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
            response_text, prompt_tokens, completion_tokens = _llm_answer(text, api_key)

    # Optional TTS
    audio_b64 = None
    if request.tts and response_text:
        try:
            wav_bytes = _synthesize_tts(response_text, api_key, voice=request.voice)
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except Exception as exc:
            logger.warning("TTS synthesis failed: %s", exc)

    return ChatResponse(
        response=response_text,
        mode=mode,
        audio_b64=audio_b64,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


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


# ---------------------------------------------------------------------------
# Camera / vision helpers
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Preference order: fastest CPU-friendly first
_VISION_MODEL_PREFERENCE = [
    "moondream",
    "minicpm-v:8b",
    "llava:7b",
    "llava",
    "llava:13b",
    "llava:34b",
]

_cached_vision_model: Optional[str] = None


def _list_ollama_models() -> List[str]:
    """Return list of model names from Ollama (empty if Ollama is not running)."""
    try:
        import httpx
        resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return []
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def _detect_vision_model() -> Optional[str]:
    """Return the best available Ollama vision model name."""
    global _cached_vision_model
    if _cached_vision_model:
        return _cached_vision_model
    available = _list_ollama_models()
    available_bases = {n.split(":")[0]: n for n in available}
    for pref in _VISION_MODEL_PREFERENCE:
        base = pref.split(":")[0]
        if pref in available:
            _cached_vision_model = pref
            return pref
        if base in available_bases:
            _cached_vision_model = available_bases[base]
            return _cached_vision_model
    return None


def _capture_webcam_frame(camera_index: int = 0) -> bytes:
    """Capture one JPEG frame from the webcam. Requires opencv-python."""
    try:
        import cv2  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="opencv-python not installed. Run: uv pip install opencv-python"
        )
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise HTTPException(status_code=503, detail=f"Cannot open camera {camera_index}")
    # Let auto-exposure settle
    for _ in range(5):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(status_code=500, detail="Failed to capture frame from webcam")
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return bytes(buf)


def _ollama_vision_query(image_bytes: bytes, question: str, model: str) -> str:
    """Ask Ollama vision model a question about an image."""
    try:
        import httpx
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": question,
                    "images": [b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512},
        }
        resp = httpx.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "No response from vision model.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ollama vision query failed: {exc}")


# ---------------------------------------------------------------------------
# OpenVINO NPU vision (lazy import — only used if installed)
# ---------------------------------------------------------------------------

def _get_openvino_vision():
    """Lazy import of openvino_vision module. Returns module or None."""
    try:
        from . import openvino_vision
        return openvino_vision
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Camera request/response models
# ---------------------------------------------------------------------------

class CameraRequest(BaseModel):
    question: str = "Describe what you see in this image."
    image_b64: Optional[str] = None   # if provided, skip webcam capture
    camera_index: int = 0
    tts: bool = False
    voice: str = "hannah"
    model: Optional[str] = None       # override auto-detected model
    backend: Optional[str] = None     # "npu", "ollama", or None (auto)


# ---------------------------------------------------------------------------
# Camera endpoints
# ---------------------------------------------------------------------------

@jarvis_router.get("/camera/models")
async def camera_models():
    """Return list of available vision backends and models."""
    # Ollama models
    all_models = _list_ollama_models()
    vision_models = [
        m for m in all_models
        if any(m.startswith(base) for base in [
            "moondream", "llava", "minicpm-v", "bakllava",
            "llava-llama3", "llava-phi3",
        ])
    ]
    detected_ollama = _detect_vision_model()

    # OpenVINO / NPU status
    ov = _get_openvino_vision()
    npu_status = ov.get_status() if ov else {
        "openvino_installed": False,
        "npu_present": False,
        "devices": [],
        "best_device": None,
        "model_ready": False,
        "model_dir": None,
        "active_device": None,
    }

    return {
        # Ollama backend
        "available": all_models,
        "vision_models": vision_models,
        "recommended": detected_ollama,
        "ollama_running": len(all_models) > 0,
        # OpenVINO / NPU backend
        "npu": npu_status,
        # Which backend will be used by default
        "active_backend": (
            "npu" if npu_status.get("model_ready") else
            "ollama" if detected_ollama else
            "none"
        ),
    }


@jarvis_router.get("/camera/npu")
async def camera_npu_status():
    """Return OpenVINO / Intel NPU status."""
    ov = _get_openvino_vision()
    if ov is None:
        return {
            "openvino_installed": False,
            "message": (
                "openvino-genai not installed. "
                "Run setup_openvino_npu.bat to enable NPU inference."
            ),
        }
    return ov.get_status()


@jarvis_router.post("/camera")
async def jarvis_camera(request: CameraRequest):
    """Capture webcam frame (or use provided image) and run vision inference.

    Backend selection (auto unless overridden via request.backend):
      1. NPU  — Intel AI Boost via OpenVINO GenAI (fastest, local, private)
      2. CPU  — Ollama moondream (fallback if NPU not set up)
    """
    api_key = os.environ.get("GROQ_API_KEY", "")

    # Get image bytes
    if request.image_b64:
        try:
            image_bytes = base64.b64decode(request.image_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image_b64 data")
    else:
        image_bytes = _capture_webcam_frame(request.camera_index)

    question = request.question.strip() or "Describe what you see in this image."
    answer: Optional[str] = None
    backend_used = "none"
    model_used = "unknown"

    # ---- Try OpenVINO NPU (unless user explicitly requested ollama) --------
    use_npu = request.backend in (None, "npu", "openvino")
    if use_npu:
        ov = _get_openvino_vision()
        if ov and ov.is_openvino_available() and ov.find_local_model():
            try:
                answer, device = ov.query(image_bytes, question)
                model_dir = ov.find_local_model()
                model_used = f"OpenVINO/{model_dir.name}" if model_dir else "OpenVINO"
                backend_used = f"npu:{device}"
                logger.info("Camera vision answered by OpenVINO on %s", device)
            except Exception as exc:
                logger.warning("OpenVINO inference failed, falling back to Ollama: %s", exc)

    # ---- Fallback: Ollama (CPU) --------------------------------------------
    if answer is None and request.backend != "npu":
        model = request.model or _detect_vision_model()
        if not model:
            raise HTTPException(
                status_code=503,
                detail=(
                    "No vision backend available. Options:\n"
                    "• Ollama: run 'ollama pull moondream'\n"
                    "• NPU:    run setup_openvino_npu.bat"
                ),
            )
        answer = _ollama_vision_query(image_bytes, question, model)
        model_used = model
        backend_used = "ollama:cpu"

    if answer is None:
        raise HTTPException(status_code=503, detail="No vision backend available.")

    # Encode image for display
    captured_b64 = base64.b64encode(image_bytes).decode("ascii")

    # Optional TTS
    audio_b64 = None
    if request.tts and answer and api_key:
        try:
            wav_bytes = _synthesize_tts(answer, api_key, voice=request.voice)
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        except Exception as exc:
            logger.debug("Camera TTS skipped: %s", exc)

    return JSONResponse({
        "response": answer,
        "model": model_used,
        "backend": backend_used,
        "image_b64": captured_b64,
        "audio_b64": audio_b64,
    })


__all__ = ["jarvis_router"]
