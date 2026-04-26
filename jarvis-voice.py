"""
OpenJarvis Voice Mode
- Window opens, shows countdown
- Speak during the recording time
- Jarvis answers in text (or controls your machine)
- Press Ctrl+C to quit

Desktop control: say "open Chrome", "close Notepad", "search for the weather", etc.
Regular Q&A: any other question is answered with text.
"""

import os
import sys
import time
import signal
import tempfile
import threading

import sounddevice as sd
import soundfile as sf
import numpy as np

os.environ["LITELLM_LOG"] = "ERROR"

# ---------------------------------------------------------------------------
# TTS — optional; activates when Groq Orpheus terms have been accepted
# ---------------------------------------------------------------------------
_TTS_ENABLED: bool | None = None  # None = not yet probed

def _try_speak(text: str) -> bool:
    """Speak *text* via Groq TTS if available. Returns True on success."""
    global _TTS_ENABLED
    if _TTS_ENABLED is False:
        return False  # already confirmed unavailable this session

    try:
        import pathlib
        src_path = str(pathlib.Path(__file__).parent / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("ERROR: GROQ_API_KEY not set.")
    input("Press Enter to close...")
    sys.exit(1)

from openai import OpenAI

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 6  # seconds to record each time

# ---------------------------------------------------------------------------
# Keywords that trigger desktop-control mode
# ---------------------------------------------------------------------------
_CONTROL_KEYWORDS = (
    "open ", "close ", "launch ", "start ", "click ", "type ", "press ",
    "search for", "go to ", "navigate to", "minimize", "maximize", "restore",
    "scroll ", "drag ", "copy", "paste", "undo", "redo",
    "volume up", "volume down", "mute", "screenshot", "take a screenshot",
    "show desktop", "switch to ", "focus on ",
    "write ", "enter ", "select all", "save ", "delete ",
)


def _is_control_command(text: str) -> bool:
    """Return True if the transcribed text looks like a machine-control command."""
    lower = text.lower().strip()
    return any(lower.startswith(kw) or kw in lower for kw in _CONTROL_KEYWORDS)


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------

def record_audio(seconds):
    """Record for a fixed number of seconds with countdown."""
    frames = []

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


# ---------------------------------------------------------------------------
# Speech-to-text (Groq Whisper)
# ---------------------------------------------------------------------------

def transcribe(audio):
    """Transcribe audio bytes using Groq Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        sf.write(tmp_path, audio, SAMPLE_RATE)
    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text"
            )
        text = result.strip() if isinstance(result, str) else str(result).strip()
        return text
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# LLM Q&A (Groq)
# ---------------------------------------------------------------------------

def ask(question):
    """Ask Groq LLM a question and return the text answer."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": question}],
        max_tokens=1024,
        temperature=0.7
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Desktop control (DesktopAgent)
# ---------------------------------------------------------------------------

def control_machine(goal: str) -> str:
    """Run the DesktopAgent to control the machine. Returns a summary."""
    try:
        # Add src to path so we can import openjarvis
        import importlib.util, pathlib
        src_path = str(pathlib.Path(__file__).parent / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        from openjarvis.agents.desktop_agent import DesktopAgent
        agent = DesktopAgent(
            api_key=GROQ_API_KEY,
            max_steps=15,
            step_delay=1.5,
            verbose=True,
        )
        return agent.run(goal)
    except Exception as exc:
        return f"Desktop control failed: {exc}"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("  OpenJarvis - Voice Mode")
    print("  Powered by Groq (Free)")
    print("  Q&A + Machine Control")
    print("=" * 55)
    print()
    print("  HOW TO USE:")
    print("  1. Wait for 'SPEAK NOW!'")
    print("  2. Speak your question or command")
    print("     - Question  ->  Jarvis answers in text")
    print("     - Command   ->  Jarvis controls your machine")
    print("  3. Press Ctrl+C to quit")
    print()
    print("  CONTROL EXAMPLES:")
    print("    'Open Chrome'")
    print("    'Search for the weather'")
    print("    'Close Notepad'")
    print("    'Type hello world in Notepad'")
    print()

    while True:
        try:
            print("-" * 55)
            input("  Press ENTER when ready to speak...")
            audio = record_audio(RECORD_SECONDS)

            if audio is None or np.max(np.abs(audio)) < 0.001:
                print("  No voice detected, try again.")
                continue

            print("  Transcribing...")
            question = transcribe(audio)

            if not question:
                print("  Could not understand, please try again.")
                continue

            print(f"\n  You said: \"{question}\"")

            if question.lower().strip() in ("exit", "quit", "stop", "bye"):
                print("\n  Goodbye!")
                break

            # Route: machine control vs. Q&A
            if _is_control_command(question):
                print("\n  [Desktop Control Mode] Jarvis is taking control...")
                result = control_machine(question)
                print(f"\n  Jarvis: {result}\n")
                _try_speak(result)
            else:
                print("\n  Jarvis is thinking...")
                answer = ask(question)
                print(f"\n  Jarvis: {answer}\n")
                _try_speak(answer)

        except (KeyboardInterrupt, SystemExit):
            print("\n\n  Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n  Error: {e}")
            print("  Trying again...\n")
            continue


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda sig, frame: (print("\n\n  Goodbye!"), os._exit(0)))
    main()
    input("\nPress Enter to close...")
