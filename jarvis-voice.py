"""
OpenJarvis Voice Mode  (v2 — Advanced)
=======================================
Features
--------
* Greeting on startup with time-aware salutation
* Speak during 6-second recording window
* Smart routing:
    - Plugin commands (news, time, weather, note, wiki, youtube, …) → plugin system
    - Machine-control commands (open, click, type, …) → DesktopAgent
    - Everything else → Groq LLaMA Q&A
* Optional TTS via Groq Orpheus (auto-probed on first use)
* Press Ctrl+C or say "exit / quit / goodbye" to stop

Desktop control examples
-------------------------
  "Open Chrome"
  "Close Notepad"
  "Type hello world in Notepad"
  "Search for the weather"

Plugin command examples
------------------------
  "What time is it"
  "Tell me today's date"
  "Show me the news"
  "Tell me about black holes"
  "Note: Buy groceries tomorrow"
  "Where am I"
  "System info"
  "Play Bohemian Rhapsody on YouTube"
  "Weather in Tokyo"
  "Tell a joke"
"""

from __future__ import annotations

import os
import sys
import time
import signal
import random
import datetime
import tempfile
import pathlib

import sounddevice as sd
import soundfile as sf
import numpy as np

# Silence LiteLLM noise
os.environ["LITELLM_LOG"] = "ERROR"

# ── Path bootstrap ─────────────────────────────────────────────────────────────
_SRC = str(pathlib.Path(__file__).parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
_CUSTOM = str(pathlib.Path(__file__).parent / "custom")

# ── Groq API key check ─────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("ERROR: GROQ_API_KEY not set.")
    input("Press Enter to close...")
    sys.exit(1)

from openai import OpenAI  # noqa: E402  (after path bootstrap)

_GROQ = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 6

# ── Plugin registry ─────────────────────────────────────────────────────────────

def _load_plugins() -> None:
    """Import all custom plugins so their @plugin decorators register them."""
    try:
        from openjarvis.plugins import load_directory
        n = load_directory(_CUSTOM)
    except Exception as exc:
        print(f"  [warning] Plugin loading failed: {exc}")


# ── TTS ──────────────────────────────────────────────────────────────────────
_TTS_ENABLED: bool | None = None


def _try_speak(text: str) -> bool:
    """Speak *text* via Groq TTS if available. Returns True on success."""
    global _TTS_ENABLED
    if _TTS_ENABLED is False:
        return False
    try:
        from openjarvis.speech.groq_tts import speak
        ok = speak(text)
        if _TTS_ENABLED is None:
            _TTS_ENABLED = ok
            if ok:
                print("  [TTS enabled — Jarvis will speak responses]")
        return ok
    except Exception:
        _TTS_ENABLED = False
        return False


def _say(text: str) -> None:
    """Print and optionally speak text."""
    print(f"\n  Jarvis: {text}\n")
    _try_speak(text)


# ── Greeting ─────────────────────────────────────────────────────────────────

_GREET_RESPONSES = [
    "Always at your service, sir.",
    "I am ready, sir.",
    "Your wish is my command.",
    "How can I help you today?",
    "Online and ready, sir.",
]

_GREETINGS = {
    "hello jarvis", "jarvis", "wake up jarvis", "hey jarvis",
    "ok jarvis", "are you there", "you there", "hi jarvis",
    "good morning jarvis", "good evening jarvis", "good afternoon jarvis",
}


def _time_greeting() -> str:
    hour = datetime.datetime.now().hour
    if 0 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 18:
        return "Good afternoon"
    return "Good evening"


def _startup_greeting() -> None:
    greeting = _time_greeting()
    msg = (
        f"{greeting}! I am OpenJarvis — online and ready. "
        "You can ask me questions, control your machine, check the news, "
        "play YouTube videos, take notes, and much more. "
        "Press Enter when you are ready to speak."
    )
    _say(msg)


# ── Audio recording ───────────────────────────────────────────────────────────

def record_audio(seconds: int = RECORD_SECONDS) -> np.ndarray | None:
    frames: list[np.ndarray] = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    print(f"\n  >> Recording for {seconds} seconds... SPEAK NOW!")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        dtype="float32", callback=callback):
        for i in range(seconds, 0, -1):
            print(f"     {i}...", end="\r", flush=True)
            time.sleep(1)

    print("  >> Done recording.          ")
    if not frames:
        return None
    return np.concatenate(frames, axis=0)


# ── STT ──────────────────────────────────────────────────────────────────────

def transcribe(audio: np.ndarray) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        sf.write(tmp_path, audio, SAMPLE_RATE)
    try:
        with open(tmp_path, "rb") as f:
            result = _GROQ.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text",
            )
        text = result.strip() if isinstance(result, str) else str(result).strip()
        return text
    finally:
        os.unlink(tmp_path)


# ── LLM Q&A ──────────────────────────────────────────────────────────────────

def _llm_answer(question: str) -> str:
    response = _GROQ.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are OpenJarvis, an intelligent AI assistant. "
                    "Give concise, helpful answers. When answering factual questions "
                    "be accurate. Keep responses under 3 sentences unless more is needed."
                ),
            },
            {"role": "user", "content": question},
        ],
        max_tokens=512,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


# ── Routing logic ─────────────────────────────────────────────────────────────

# Keywords whose presence routes to the PLUGIN system first
_PLUGIN_TRIGGERS = (
    "time", "date", "day", "today", "news", "headlines", "weather",
    "note", "remember", "write down", "make a note", "read notes", "show notes", "my notes",
    "joke", "tell a joke", "tell me about", "who is", "what is", "wikipedia", "wiki",
    "system", "cpu", "ram", "battery", "disk", "ip address",
    "where am i", "my location", "current location", "where is",
    "play", "youtube", "play music", "search youtube",
    "calculate", "email", "send email",
    "open ", "launch", "start app",
)

# Keywords that route specifically to desktop-control (DesktopAgent)
_CONTROL_KEYWORDS = (
    "click ", "double click", "right click", "drag ", "scroll ",
    "type ", "hotkey ", "press key", "key down", "key up",
    "take screenshot", "take a screenshot", "capture the screen",
    "minimize ", "maximize ", "restore window", "close window",
    "focus on ", "switch to ", "switch window",
    "volume up", "volume down", "mute ",
    "show desktop", "copy", "paste", "select all", "undo", "redo",
    "go to ", "navigate to ",
)


def _classify(text: str) -> str:
    """Return 'plugin', 'control', or 'qa'."""
    lower = text.lower().strip()

    # Desktop control (low-level machine ops)
    if any(kw in lower for kw in _CONTROL_KEYWORDS):
        return "control"

    # Plugin commands
    if any(lower.startswith(kw) or (kw.strip() in lower) for kw in _PLUGIN_TRIGGERS):
        return "plugin"

    return "qa"


def _dispatch_plugin(command: str) -> str | None:
    """Try the plugin system and return output, or None if no match."""
    try:
        from openjarvis.plugins import dispatch, JarvisContext
        ctx = JarvisContext(api_key=GROQ_API_KEY)
        result = dispatch(command, ctx)
        return result
    except Exception as exc:
        return f"Plugin error: {exc}"


def _control_machine(goal: str) -> str:
    try:
        from openjarvis.agents.desktop_agent import DesktopAgent
        agent = DesktopAgent(api_key=GROQ_API_KEY, max_steps=15, step_delay=1.5, verbose=True)
        return agent.run(goal)
    except Exception as exc:
        return f"Desktop control failed: {exc}"


# ── Main loop ─────────────────────────────────────────────────────────────────

def _handle(command: str) -> None:
    lower = command.lower().strip()

    # Quit
    if lower in ("exit", "quit", "stop", "bye", "goodbye", "go offline", "offline"):
        farewell = "Alright, going offline. It was a pleasure working with you, sir. Goodbye!"
        _say(farewell)
        sys.exit(0)

    # Greeting
    if lower in _GREETINGS or lower.rstrip(".! ") in _GREETINGS:
        _say(random.choice(_GREET_RESPONSES))
        return

    kind = _classify(command)

    if kind == "plugin":
        print("  [Plugin mode] Dispatching to plugin system...")
        result = _dispatch_plugin(command)
        if result:
            _say(result)
            return
        # If plugin didn't match, fall through to Q&A
        print("  [No plugin matched, falling back to Q&A]")

    if kind == "control":
        print("  [Desktop Control mode] Jarvis is taking control...")
        result = _control_machine(command)
        _say(result)
        return

    # Q&A (also fallback)
    print("  Jarvis is thinking...")
    answer = _llm_answer(command)
    _say(answer)


def main() -> None:
    print("=" * 60)
    print("  OpenJarvis — Advanced Voice Mode  (v2)")
    print("  Powered by Groq (Free) | LLaMA + Whisper + Orpheus TTS")
    print("=" * 60)
    print()
    print("  Capabilities:")
    print("    News / Headlines     →  'Show me the news'")
    print("    Time & Date          →  'What time is it'")
    print("    Weather              →  'Weather in London'")
    print("    Notes                →  'Note: Call dentist at 3pm'")
    print("    Wikipedia            →  'Tell me about quantum physics'")
    print("    YouTube              →  'Play Bohemian Rhapsody'")
    print("    Apps & websites      →  'Open Chrome'")
    print("    System info          →  'System status'")
    print("    Location             →  'Where am I'")
    print("    Email                →  'Send email'")
    print("    Jokes                →  'Tell me a joke'")
    print("    Machine control      →  'Click the start button'")
    print("    General Q&A          →  Anything else")
    print()
    print("  Say 'exit' or 'goodbye' to quit.")
    print()

    _load_plugins()
    _startup_greeting()

    while True:
        try:
            print("-" * 60)
            input("  Press ENTER when ready to speak...")
            audio = record_audio()

            if audio is None or np.max(np.abs(audio)) < 0.001:
                print("  No voice detected, try again.")
                continue

            print("  Transcribing...")
            command = transcribe(audio)
            if not command:
                print("  Could not understand. Please try again.")
                continue

            print(f"\n  You said: \"{command}\"")
            _handle(command)

        except (KeyboardInterrupt, SystemExit):
            print("\n\n  Goodbye!")
            sys.exit(0)
        except Exception as exc:
            print(f"\n  Error: {exc}")
            print("  Trying again...\n")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: (print("\n\n  Goodbye!"), os._exit(0)))
    main()
    input("\nPress Enter to close...")
