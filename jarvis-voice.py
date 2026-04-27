"""
OpenJarvis Voice Mode  (v4 — Continuous Conversation)
======================================================
Changes from v3
---------------
* NO more "Press ENTER" — Jarvis listens continuously.
* Voice Activity Detection (VAD) using numpy energy — no extra packages.
  Automatically detects when you START and STOP talking.
* Persistent conversation history — Jarvis remembers everything you said
  in this session, making it feel like a real back-and-forth conversation.
* Full chat history sent to the LLM on every turn.
* Silence timeout: after 0.8 s of quiet after speech, recording ends.
* Wake-word optional — just speak naturally at any time.

Usage
-----
  python jarvis-voice.py            # starts listening immediately
  Say "exit", "quit", or "goodbye"  # to stop

Desktop control examples
-------------------------
  "Open Chrome"
  "Close Notepad"
  "Type hello world in Notepad"

Plugin command examples
------------------------
  "What time is it"
  "Show me the news"
  "Weather in Tokyo"
  "Play Bohemian Rhapsody on YouTube"
  "Note: Buy groceries tomorrow"
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
import threading
import queue

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

from openai import OpenAI  # noqa: E402

_GROQ = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# ── Audio settings ─────────────────────────────────────────────────────────────
SAMPLE_RATE   = 16000
CHANNELS      = 1
FRAME_MS      = 30          # VAD frame size in ms
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples per frame

# VAD thresholds (tune if mic is noisy)
ENERGY_THRESHOLD   = 0.015   # RMS above this = speech
SILENCE_TIMEOUT_S  = 0.9     # seconds of silence after speech to stop recording
PRE_ROLL_FRAMES    = 5       # frames of audio captured before speech detected (avoids clipping)
MAX_RECORD_S       = 30      # hard cap so it never hangs

# ── Conversation history ───────────────────────────────────────────────────────
# Each entry: {"role": "user"|"assistant", "content": str}
_HISTORY: list[dict] = []
_MAX_HISTORY = 20  # keep last N turns to avoid token overflow


# ── Plugin registry ─────────────────────────────────────────────────────────────

def _load_plugins() -> None:
    try:
        from openjarvis.plugins import load_directory
        load_directory(_CUSTOM)
    except Exception as exc:
        print(f"  [warning] Plugin loading failed: {exc}")


# ── TTS ──────────────────────────────────────────────────────────────────────
_TTS_ENABLED: bool | None = None


def _try_speak(text: str) -> bool:
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
        f"{greeting}! I am OpenJarvis — online and listening. "
        "Just speak naturally at any time. I will respond right away. "
        "Say 'goodbye' to stop."
    )
    _say(msg)


# ── VAD-based continuous recording ────────────────────────────────────────────

def _rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def record_until_silence() -> np.ndarray | None:
    """
    Record audio until the speaker stops talking.
    Returns a numpy float32 array, or None if no speech detected.

    Algorithm:
    1. Fill a pre-roll ring buffer of PRE_ROLL_FRAMES frames.
    2. When energy exceeds ENERGY_THRESHOLD → speech started.
    3. Keep recording until SILENCE_TIMEOUT_S of consecutive silence.
    4. Return pre-roll + speech audio.
    """
    audio_q: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())  # mono

    pre_roll: list[np.ndarray] = []
    speech_frames: list[np.ndarray] = []
    speech_started = False
    silent_frame_count = 0
    silence_frames_needed = int(SILENCE_TIMEOUT_S * 1000 / FRAME_MS)
    max_frames = int(MAX_RECORD_S * 1000 / FRAME_MS)
    total_frames = 0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=FRAME_SAMPLES,
        callback=callback,
    ):
        print("  >> Listening...", end="\r", flush=True)
        while True:
            try:
                frame = audio_q.get(timeout=2.0)
            except queue.Empty:
                break

            energy = _rms(frame)
            total_frames += 1

            if not speech_started:
                # Pre-roll buffer
                pre_roll.append(frame)
                if len(pre_roll) > PRE_ROLL_FRAMES:
                    pre_roll.pop(0)

                if energy > ENERGY_THRESHOLD:
                    speech_started = True
                    print("  >> Speech detected — recording...", end="\r", flush=True)
                    speech_frames.extend(pre_roll)
                    speech_frames.append(frame)
                    silent_frame_count = 0
            else:
                speech_frames.append(frame)
                if energy < ENERGY_THRESHOLD:
                    silent_frame_count += 1
                    if silent_frame_count >= silence_frames_needed:
                        print("  >> Done.                              ")
                        break
                else:
                    silent_frame_count = 0

            if total_frames >= max_frames:
                print("  >> Max recording time reached.")
                break

    if not speech_started or len(speech_frames) < 3:
        return None

    return np.concatenate(speech_frames, axis=0)


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


# ── LLM Q&A with conversation history ─────────────────────────────────────────

def _build_system_prompt() -> str:
    base = (
        "You are Jarvis, an advanced AI assistant — loyal, witty, and highly capable. "
        "You have persistent memory, can control computers, search the web, manage files, "
        "set reminders, play music, and much more. "
        "Keep responses concise and conversational — 1-3 sentences unless more is genuinely needed. "
        "You are talking to the user via voice, so do NOT use markdown, bullet points, or lists. "
        "Speak naturally as if in a real conversation. Address the user warmly."
    )
    try:
        from openjarvis.memory.memory_manager import load_memory, format_memory_for_prompt
        mem = load_memory()
        mem_block = format_memory_for_prompt(mem)
        if mem_block:
            return base + "\n\n" + mem_block
    except Exception:
        pass
    return base


def _llm_answer(question: str) -> str:
    global _HISTORY

    # Add user message to history
    _HISTORY.append({"role": "user", "content": question})

    # Trim history to avoid token overflow (keep last N entries)
    if len(_HISTORY) > _MAX_HISTORY:
        _HISTORY = _HISTORY[-_MAX_HISTORY:]

    messages = [{"role": "system", "content": _build_system_prompt()}] + _HISTORY

    response = _GROQ.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=256,
        temperature=0.7,
    )
    answer = response.choices[0].message.content or ""

    # Add assistant reply to history
    _HISTORY.append({"role": "assistant", "content": answer})

    return answer


# ── Routing logic ─────────────────────────────────────────────────────────────

_PLUGIN_TRIGGERS = (
    "time", "date", "day", "today",
    "news", "headlines", "top news",
    "weather",
    "note", "make a note", "write this down", "remember this", "read notes", "show notes", "my notes",
    "remember", "memorize", "what do you know", "my memory", "show memory", "forget", "recall",
    "joke", "tell a joke",
    "tell me about", "who is", "what is", "wikipedia", "wiki",
    "system", "cpu", "ram", "battery", "disk", "ip address",
    "where am i", "my location", "current location", "where is",
    "play", "youtube", "play music", "search youtube", "play on youtube",
    "search", "google", "web search", "search web", "look up", "find information",
    "calculate",
    "email", "send email",
    "open ", "launch", "start app",
    "list files", "show files", "read file", "find file", "disk usage", "disk space",
    "create file", "delete file", "rename file", "move file",
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
    "analyze screen", "what's on my screen", "look at screen", "screen analysis", "what do you see",
)

_CONTROL_KEYWORDS = (
    "click on ", "double click on", "right click on", "drag ",
    "press key ", "key down ", "key up ",
    "focus on ", "switch to window", "close the window",
    "restore window",
    "go to website", "navigate to ",
)


def _classify(text: str) -> str:
    lower = text.lower().strip()
    if any(kw in lower for kw in _CONTROL_KEYWORDS):
        return "control"
    if any(lower.startswith(kw) or (kw.strip() in lower) for kw in _PLUGIN_TRIGGERS):
        return "plugin"
    return "qa"


def _dispatch_plugin(command: str) -> str | None:
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


# ── Command handler ────────────────────────────────────────────────────────────

def _handle(command: str) -> None:
    lower = command.lower().strip()

    # Quit
    if lower in ("exit", "quit", "stop", "bye", "goodbye", "go offline", "offline"):
        farewell = "Alright, going offline. It was a pleasure talking with you. Goodbye!"
        _say(farewell)
        sys.exit(0)

    # Greeting — still respond but also add to history so Jarvis is aware
    if lower in _GREETINGS or lower.rstrip(".! ") in _GREETINGS:
        reply = random.choice(_GREET_RESPONSES)
        _HISTORY.append({"role": "user", "content": command})
        _HISTORY.append({"role": "assistant", "content": reply})
        _say(reply)
        return

    kind = _classify(command)

    if kind == "plugin":
        print("  [Plugin mode]")
        result = _dispatch_plugin(command)
        if result:
            # Also log plugin results in history so LLM knows what happened
            _HISTORY.append({"role": "user", "content": command})
            _HISTORY.append({"role": "assistant", "content": result})
            _say(result)
            return
        print("  [No plugin matched, falling back to Q&A]")

    if kind == "control":
        print("  [Desktop Control mode]")
        result = _control_machine(command)
        _HISTORY.append({"role": "user", "content": command})
        _HISTORY.append({"role": "assistant", "content": result})
        _say(result)
        return

    # Q&A with full conversation history
    print("  Jarvis is thinking...")
    answer = _llm_answer(command)
    _say(answer)


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  OpenJarvis — Voice Mode  (v4 — Continuous Conversation)")
    print("  Powered by Groq | LLaMA + Whisper + Orpheus TTS")
    print("=" * 60)
    print()
    print("  Just SPEAK — no button pressing needed.")
    print("  Jarvis listens, responds, then listens again.")
    print("  Conversation history is kept for natural back-and-forth.")
    print("  Say 'goodbye' to quit.")
    print()

    _load_plugins()
    _startup_greeting()

    while True:
        try:
            audio = record_until_silence()

            if audio is None:
                # No speech detected — just keep listening silently
                continue

            print("  Transcribing...")
            command = transcribe(audio)
            if not command:
                print("  Could not understand, listening again...")
                continue

            print(f"\n  You: \"{command}\"")
            _handle(command)

        except (KeyboardInterrupt, SystemExit):
            print("\n\n  Goodbye!")
            sys.exit(0)
        except Exception as exc:
            print(f"\n  Error: {exc}")
            print("  Continuing...\n")
            time.sleep(0.5)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: (print("\n\n  Goodbye!"), os._exit(0)))
    main()
    input("\nPress Enter to close...")
