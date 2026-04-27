"""Camera / webcam vision plugin — capture a webcam frame and answer questions
using Ollama's local vision model (moondream2 by default, or llava:7b).

This plugin runs 100% locally — no cloud API key needed for vision.
Ollama must be running with a vision model pulled:
    ollama pull moondream2        # ~1.7 GB, fast on CPU
    ollama pull llava:7b          # ~4.5 GB, better quality

Usage triggers:
  look at camera / camera / webcam / what do you see through camera
  look at me / describe me / who am i
  camera analyze <question>
  camera what is <question>
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from openjarvis.plugins import plugin
except ImportError:
    # Allow standalone testing
    def plugin(trigger):  # type: ignore
        def decorator(fn):
            return fn
        return decorator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Priority order: moondream2 (fast, CPU-friendly) → llava:7b → llava
_VISION_MODEL_PREFERENCE = [
    "moondream2",
    "minicpm-v:8b",
    "llava:7b",
    "llava",
    "llava:13b",
    "llava:34b",
]
_detected_model: Optional[str] = None


def _detect_ollama_vision_model() -> Optional[str]:
    """Auto-detect which vision model is available in Ollama."""
    global _detected_model
    if _detected_model:
        return _detected_model
    try:
        import httpx
        resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3.0)
        if resp.status_code != 200:
            return None
        models = {m["name"].split(":")[0]: m["name"] for m in resp.json().get("models", [])}
        # Also include full names
        all_names = [m["name"] for m in resp.json().get("models", [])]
        for pref in _VISION_MODEL_PREFERENCE:
            base = pref.split(":")[0]
            if pref in all_names:
                _detected_model = pref
                return pref
            if base in models:
                _detected_model = models[base]
                return _detected_model
        return None
    except Exception as exc:
        logger.debug("Ollama detection failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Webcam capture
# ---------------------------------------------------------------------------

def _capture_webcam(camera_index: int = 0) -> bytes:
    """Capture one frame from the webcam and return JPEG bytes."""
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_index}")
        # Let camera warm up (auto-exposure stabilise)
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            raise RuntimeError("Failed to capture frame")
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return bytes(buf)
    except ImportError:
        # Fallback: try PIL + platform camera via pyautogui (no cv2)
        raise RuntimeError(
            "opencv-python is required for webcam capture. "
            "Install it: uv pip install opencv-python"
        )


# ---------------------------------------------------------------------------
# Ollama vision query
# ---------------------------------------------------------------------------

def _ask_ollama_vision(image_bytes: bytes, question: str, model: str) -> str:
    """Send image + question to Ollama vision model (moondream2 / llava)."""
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
            "options": {
                "temperature": 0.3,
                "num_predict": 256,
            },
        }
        resp = httpx.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "No response from vision model.")
    except Exception as exc:
        return f"Vision query failed: {exc}"


# ---------------------------------------------------------------------------
# Core handler
# ---------------------------------------------------------------------------

def _run_camera_vision(question: str, jarvis) -> None:
    """Capture webcam frame, send to Ollama vision model, speak result."""
    model = _detect_ollama_vision_model()
    if not model:
        jarvis.say(
            "No Ollama vision model found. Please install Ollama and run: "
            "ollama pull moondream2"
        )
        return

    jarvis.say("Opening your camera…")
    try:
        frame_bytes = _capture_webcam()
    except RuntimeError as exc:
        jarvis.say(str(exc))
        return

    jarvis.say(f"Got it — asking {model} to analyze the image…")
    answer = _ask_ollama_vision(frame_bytes, question, model)
    jarvis.say(answer)


# ---------------------------------------------------------------------------
# Plugin triggers
# ---------------------------------------------------------------------------

@plugin("look at camera")
def look_at_camera(jarvis, s):
    """Capture webcam and describe what the vision model sees."""
    question = s.strip() or "Describe what you see in this image."
    _run_camera_vision(question, jarvis)


@plugin("camera")
def camera_analyze(jarvis, s):
    """Capture webcam and answer a question. Usage: camera what is behind me?"""
    question = s.strip() or "Describe what you see in this image."
    _run_camera_vision(question, jarvis)


@plugin("webcam")
def webcam_analyze(jarvis, s):
    """Capture webcam frame. Usage: webcam what color is my shirt?"""
    question = s.strip() or "Describe what you see in this image."
    _run_camera_vision(question, jarvis)


@plugin("look at me")
def look_at_me(jarvis, s):
    """Analyze what the webcam sees of the user."""
    _run_camera_vision("Describe the person in front of the camera in detail.", jarvis)


@plugin("describe me")
def describe_me(jarvis, s):
    """Describe the user through the webcam."""
    _run_camera_vision("Please describe the person you see in this image.", jarvis)


@plugin("who am i")
def who_am_i(jarvis, s):
    """Look at camera and describe the user."""
    _run_camera_vision("Who or what do you see in this image? Describe in detail.", jarvis)


@plugin("what do you see through camera")
def what_through_camera(jarvis, s):
    """Look at the webcam and describe the scene."""
    _run_camera_vision("Describe everything you see in this image.", jarvis)


@plugin("camera analyze")
def camera_analyze_question(jarvis, s):
    """Analyze camera with a specific question. Usage: camera analyze is it dark in here?"""
    question = s.strip() or "Describe what you see."
    _run_camera_vision(question, jarvis)
