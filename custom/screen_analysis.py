"""Screen analysis plugin — take a screenshot and answer questions about it using Groq vision.

Mirrors MK37's screen_processor.py but uses Groq's llama-4-scout vision model
(same model already used by the DesktopAgent).

Usage:
  analyze screen
  what's on my screen
  look at screen what browser is open
  analyze screen what time is it
"""

from __future__ import annotations

import base64
import io
import os
import sys
import pathlib

from openjarvis.plugins import plugin

_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def _capture_screen() -> bytes:
    """Capture the primary monitor and return raw PNG bytes."""
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(monitor)
            return mss.tools.to_png(shot.rgb, shot.size)
    except ImportError:
        # Fallback: pyautogui screenshot
        import pyautogui
        buf = io.BytesIO()
        pyautogui.screenshot().save(buf, format="PNG")
        return buf.getvalue()


def _resize_png(png_bytes: bytes, max_width: int = 1280) -> bytes:
    """Resize image to max_width to save tokens."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        w, h = img.size
        if w > max_width:
            ratio = max_width / w
            img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except ImportError:
        return png_bytes


def _ask_groq_vision(image_bytes: bytes, question: str, api_key: str) -> str:
    """Send image + question to Groq vision model and return the answer."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = "image/jpeg" if len(image_bytes) > 100 else "image/png"
    # Detect mime from bytes header
    if image_bytes[:4] == b"\x89PNG":
        mime = "image/png"

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": question},
                ],
            }
        ],
        max_tokens=512,
    )
    return response.choices[0].message.content or "I couldn't analyze the screen."


def _do_analysis(question: str, jarvis) -> None:
    api_key = _GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        jarvis.say("GROQ_API_KEY is not set — cannot analyze screen.")
        return

    jarvis.say("Capturing your screen…")
    try:
        png = _capture_screen()
    except Exception as exc:
        jarvis.say(f"Could not capture screen: {exc}")
        return

    try:
        img = _resize_png(png)
    except Exception:
        img = png

    jarvis.say("Analyzing…")
    try:
        answer = _ask_groq_vision(img, question, api_key)
        jarvis.say(answer)
    except Exception as exc:
        jarvis.say(f"Screen analysis failed: {exc}")


@plugin("analyze screen")
def analyze_screen(jarvis, s):
    """Capture and analyze the screen. Usage: analyze screen what's open?"""
    question = s.strip() or "Describe what you see on this screen."
    _do_analysis(question, jarvis)


@plugin("what's on my screen")
def whats_on_screen(jarvis, s):
    """Analyze the current screen contents"""
    _do_analysis("Describe what you see on this screen.", jarvis)


@plugin("look at screen")
def look_at_screen(jarvis, s):
    """Look at the screen and answer a question. Usage: look at screen what browser is open"""
    question = s.strip() or "Describe what you see on this screen."
    _do_analysis(question, jarvis)


@plugin("screen analysis")
def screen_analysis(jarvis, s):
    """Analyze the screen. Usage: screen analysis what text is visible?"""
    analyze_screen(jarvis, s)


@plugin("what do you see")
def what_do_you_see(jarvis, s):
    """Take a screenshot and describe what's visible"""
    _do_analysis("Describe everything you see on this screen.", jarvis)
