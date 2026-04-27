"""
OpenJarvis Voice Mode  (v5 — Always On, Human-Like)
====================================================
How it works
------------
1.  Jarvis is ALWAYS listening in STANDBY mode.
2.  When it hears your voice (above the energy threshold) it records until
    you stop talking (silence for ~0.9 s), then transcribes + responds.
3.  No wake word, no button pressing — just talk.
4.  Full conversation history is kept so every reply has context.
5.  Full machine control: keyboard, mouse, open/close apps, type text,
    screenshot, volume, brightness, windows, clipboard, web, files, etc.
6.  Say "shutdown jarvis" (or "exit"/"quit"/"goodbye") to stop.

VAD tuning
----------
If Jarvis triggers on background noise, increase ENERGY_THRESHOLD (e.g. 0.025).
If it misses quiet speech, lower it (e.g. 0.010).
Run the script once to see the "ambient noise" level printed at startup.
"""

from __future__ import annotations

import os, sys, time, signal, random, datetime, tempfile, pathlib, queue
import subprocess, webbrowser, threading, shutil

import sounddevice as sd
import soundfile  as sf
import numpy      as np
import pyautogui

os.environ["LITELLM_LOG"] = "ERROR"
pyautogui.FAILSAFE = False   # disable corner-move abort so Jarvis can control freely

# ── Paths ──────────────────────────────────────────────────────────────────────
_ROOT   = pathlib.Path(__file__).parent
_SRC    = str(_ROOT / "src")
_CUSTOM = str(_ROOT / "custom")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# ── API key ────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("ERROR: GROQ_API_KEY environment variable not set.")
    input("Press Enter to close...")
    sys.exit(1)

from openai import OpenAI
_GROQ = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# ── Audio constants ─────────────────────────────────────────────────────────────
SAMPLE_RATE        = 16_000
CHANNELS           = 1
FRAME_MS           = 20                            # ms per VAD chunk
FRAME_SAMPLES      = int(SAMPLE_RATE * FRAME_MS / 1000)   # 320 samples
ENERGY_THRESHOLD   = 0.018   # RMS — raise if false-triggers on noise
SILENCE_TIMEOUT_S  = 1.0     # stop recording after this much silence
PRE_ROLL_FRAMES    = 8       # frames kept before speech (avoids clipping)
MAX_RECORD_S       = 45      # absolute cap per utterance

# ── Conversation history ───────────────────────────────────────────────────────
_HISTORY: list[dict] = []
_MAX_HISTORY = 30


# ══════════════════════════════════════════════════════════════════════════════
# MACHINE CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def _open_app(name: str) -> str:
    """Try to open an application or file by name."""
    name_lower = name.lower().strip()
    # Common Windows app shortcuts
    aliases = {
        "chrome":       "chrome",
        "google chrome":"chrome",
        "firefox":      "firefox",
        "notepad":      "notepad",
        "notepad++":    "notepad++",
        "calculator":   "calc",
        "calc":         "calc",
        "file explorer":"explorer",
        "explorer":     "explorer",
        "paint":        "mspaint",
        "word":         "winword",
        "excel":        "excel",
        "powerpoint":   "powerpnt",
        "outlook":      "outlook",
        "teams":        "teams",
        "discord":      "discord",
        "spotify":      "spotify",
        "vlc":          "vlc",
        "cmd":          "cmd",
        "command prompt":"cmd",
        "powershell":   "powershell",
        "task manager": "taskmgr",
        "control panel":"control",
        "settings":     "ms-settings:",
        "snipping tool":"snippingtool",
        "vs code":      "code",
        "vscode":       "code",
        "visual studio code": "code",
    }
    cmd = aliases.get(name_lower, name_lower)
    try:
        if cmd.startswith("ms-"):
            os.startfile(cmd)
        else:
            subprocess.Popen(cmd, shell=True)
        return f"Opening {name}."
    except Exception as e:
        return f"Could not open {name}: {e}"


def _close_app(name: str) -> str:
    """Kill a process by name."""
    try:
        import psutil
        killed = []
        for proc in psutil.process_iter(["name", "pid"]):
            if name.lower() in proc.info["name"].lower():
                proc.kill()
                killed.append(proc.info["name"])
        if killed:
            return f"Closed: {', '.join(set(killed))}."
        return f"No running process found matching '{name}'."
    except Exception as e:
        return f"Error closing {name}: {e}"


def _take_screenshot(save_path: str | None = None) -> str:
    """Take a screenshot and save it."""
    try:
        path = save_path or str(pathlib.Path.home() / "Desktop" / f"screenshot_{int(time.time())}.png")
        img = pyautogui.screenshot()
        img.save(path)
        return f"Screenshot saved to {path}."
    except Exception as e:
        return f"Screenshot failed: {e}"


def _type_text(text: str) -> str:
    time.sleep(0.4)
    pyautogui.typewrite(text, interval=0.04)
    return f"Typed: {text}"


def _press_key(key: str) -> str:
    try:
        pyautogui.press(key.lower().strip())
        return f"Pressed {key}."
    except Exception as e:
        return f"Key press failed: {e}"


def _hotkey(*keys: str) -> str:
    try:
        pyautogui.hotkey(*[k.lower().strip() for k in keys])
        return f"Hotkey {'+'.join(keys)} pressed."
    except Exception as e:
        return f"Hotkey failed: {e}"


def _click(x: int | None = None, y: int | None = None, button: str = "left") -> str:
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
        return "Clicked."
    except Exception as e:
        return f"Click failed: {e}"


def _scroll(direction: str, amount: int = 3) -> str:
    clicks = amount if direction.lower() == "up" else -amount
    pyautogui.scroll(clicks)
    return f"Scrolled {direction}."


def _set_volume(level: int) -> str:
    """Set system volume 0-100 on Windows."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100)), None)
        return f"Volume set to {level}%."
    except Exception:
        # Fallback: nircmd or powershell
        try:
            pct = max(0, min(100, level))
            subprocess.run(
                f'powershell -c "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"',
                shell=True, capture_output=True
            )
            # Use nircmd if available
            if shutil.which("nircmd"):
                subprocess.run(f"nircmd setvolume 0 {int(pct * 655.35)} {int(pct * 655.35)}", shell=True)
                return f"Volume set to {pct}%."
            return f"Volume control: set to {pct}% (approximate)."
        except Exception as e2:
            return f"Could not set volume: {e2}"


def _volume_up() -> str:
    for _ in range(5):
        pyautogui.press("volumeup")
    return "Volume increased."


def _volume_down() -> str:
    for _ in range(5):
        pyautogui.press("volumedown")
    return "Volume decreased."


def _mute() -> str:
    pyautogui.press("volumemute")
    return "Muted."


def _open_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url} in browser."


def _web_search(query: str) -> str:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Searching Google for: {query}"


def _get_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or "(clipboard is empty)"
    except Exception:
        return "Could not read clipboard."


def _set_clipboard(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Copied to clipboard."
    except Exception as e:
        return f"Clipboard write failed: {e}"


def _list_running_apps() -> str:
    try:
        import psutil
        names = sorted({p.name() for p in psutil.process_iter(["name"]) if p.name()})
        return "Running: " + ", ".join(names[:20]) + ("..." if len(names) > 20 else "")
    except Exception as e:
        return f"Could not list apps: {e}"


def _minimize_all() -> str:
    pyautogui.hotkey("win", "d")
    return "All windows minimised."


def _lock_screen() -> str:
    pyautogui.hotkey("win", "l")
    return "Screen locked."


def _new_tab() -> str:
    pyautogui.hotkey("ctrl", "t")
    return "New tab opened."


def _close_tab() -> str:
    pyautogui.hotkey("ctrl", "w")
    return "Tab closed."


def _copy() -> str:
    pyautogui.hotkey("ctrl", "c")
    return "Copied."


def _paste() -> str:
    pyautogui.hotkey("ctrl", "v")
    return "Pasted."


def _undo() -> str:
    pyautogui.hotkey("ctrl", "z")
    return "Undone."


def _save() -> str:
    pyautogui.hotkey("ctrl", "s")
    return "Saved."


def _select_all() -> str:
    pyautogui.hotkey("ctrl", "a")
    return "Selected all."


def _alt_tab() -> str:
    pyautogui.hotkey("alt", "tab")
    return "Switched window."


def _run_machine_command(text: str) -> str | None:
    """
    Interpret a machine-control sentence and execute it.
    Returns a result string, or None if no command matched.
    """
    t = text.lower().strip()

    # ── App open / close ──
    for kw in ("open ", "launch ", "start "):
        if t.startswith(kw):
            return _open_app(text[len(kw):].strip())
    for kw in ("close ", "kill ", "terminate "):
        if t.startswith(kw):
            return _close_app(text[len(kw):].strip())

    # ── Browser / URL ──
    if t.startswith("go to ") or t.startswith("navigate to ") or t.startswith("open website "):
        url = t.split(" to ")[-1].strip() if " to " in t else t.split("website ")[-1].strip()
        return _open_url(url)
    if t.startswith("search for ") or t.startswith("google ") or t.startswith("search web ") or t.startswith("search "):
        for kw in ("search for ", "search web ", "google ", "search "):
            if t.startswith(kw):
                return _web_search(text[len(kw):].strip())

    # ── Typing ──
    if t.startswith("type "):
        return _type_text(text[5:].strip())
    if t.startswith("write "):
        return _type_text(text[6:].strip())

    # ── Screenshot ──
    if "screenshot" in t or "capture screen" in t or "take a screenshot" in t:
        return _take_screenshot()

    # ── Volume ──
    if "volume up" in t or "turn up the volume" in t or "increase volume" in t:
        return _volume_up()
    if "volume down" in t or "turn down the volume" in t or "decrease volume" in t:
        return _volume_down()
    if "mute" in t:
        return _mute()
    if t.startswith("set volume"):
        import re
        m = re.search(r"\d+", t)
        if m:
            return _set_volume(int(m.group()))

    # ── Window management ──
    if "minimize all" in t or "show desktop" in t or "minimise all" in t:
        return _minimize_all()
    if "lock screen" in t or "lock computer" in t:
        return _lock_screen()
    if "switch window" in t or "alt tab" in t:
        return _alt_tab()

    # ── Browser tabs ──
    if "new tab" in t:
        return _new_tab()
    if "close tab" in t:
        return _close_tab()

    # ── Clipboard ──
    if "copy" in t and "clipboard" not in t:
        return _copy()
    if "paste" in t:
        return _paste()
    if "undo" in t:
        return _undo()
    if "save" in t and "file" not in t:
        return _save()
    if "select all" in t:
        return _select_all()

    # ── Keys ──
    for kw in ("press ", "hit key ", "press key "):
        if t.startswith(kw):
            return _press_key(text[len(kw):].strip())

    # ── Scroll ──
    if "scroll up" in t:
        return _scroll("up")
    if "scroll down" in t:
        return _scroll("down")

    # ── List apps ──
    if "list apps" in t or "running apps" in t or "what's running" in t or "what is running" in t:
        return _list_running_apps()

    # ── Clipboard read ──
    if "what's in" in t and "clipboard" in t or "read clipboard" in t or "clipboard content" in t:
        content = _get_clipboard()
        return f"Clipboard contains: {content}"

    return None   # no machine command matched


# ══════════════════════════════════════════════════════════════════════════════
# PLUGINS
# ══════════════════════════════════════════════════════════════════════════════

def _load_plugins() -> None:
    try:
        from openjarvis.plugins import load_directory
        load_directory(_CUSTOM)
    except Exception as exc:
        print(f"  [warning] Plugin loading failed: {exc}")


def _dispatch_plugin(command: str) -> str | None:
    try:
        from openjarvis.plugins import dispatch, JarvisContext
        ctx = JarvisContext(api_key=GROQ_API_KEY)
        return dispatch(command, ctx)
    except Exception as exc:
        return f"Plugin error: {exc}"


# ══════════════════════════════════════════════════════════════════════════════
# TTS
# ══════════════════════════════════════════════════════════════════════════════

_TTS_ENABLED: bool | None = None
_SPEAKING = threading.Event()   # set while TTS is playing — VAD waits


def _try_speak(text: str) -> bool:
    global _TTS_ENABLED
    if _TTS_ENABLED is False:
        return False
    try:
        from openjarvis.speech.groq_tts import speak
        _SPEAKING.set()
        ok = speak(text)
        _SPEAKING.clear()
        if _TTS_ENABLED is None:
            _TTS_ENABLED = ok
            if ok:
                print("  [TTS enabled]")
        return ok
    except Exception:
        _SPEAKING.clear()
        _TTS_ENABLED = False
        return False


def _say(text: str) -> None:
    print(f"\n  Jarvis: {text}\n")
    _try_speak(text)


# ══════════════════════════════════════════════════════════════════════════════
# GREETING
# ══════════════════════════════════════════════════════════════════════════════

_GREET_RESPONSES = [
    "Always at your service, sir.",
    "Ready and listening.",
    "Your wish is my command.",
    "How can I help you?",
    "Online and standing by.",
]

_GREETINGS = {
    "hello jarvis", "jarvis", "wake up jarvis", "hey jarvis", "ok jarvis",
    "are you there", "you there", "hi jarvis", "good morning jarvis",
    "good evening jarvis", "good afternoon jarvis",
}


def _time_greeting() -> str:
    h = datetime.datetime.now().hour
    return "Good morning" if h < 12 else ("Good afternoon" if h < 18 else "Good evening")


def _startup_greeting() -> None:
    _say(
        f"{_time_greeting()}! I am Jarvis — always on and listening. "
        "Just speak to me at any time. Say 'shutdown Jarvis' when you want me to stop."
    )


# ══════════════════════════════════════════════════════════════════════════════
# LLM — with conversation history
# ══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt() -> str:
    base = (
        "You are Jarvis, an advanced AI assistant — loyal, witty, and highly capable. "
        "You have full access to the user's Windows computer and can open apps, control "
        "the mouse and keyboard, manage files, browse the web, and much more. "
        "You also have persistent memory across the conversation. "
        "Keep responses SHORT and conversational — 1 to 3 sentences maximum unless "
        "the user explicitly asks for more detail. "
        "You are speaking out loud via voice — NEVER use markdown, bullet points, "
        "code blocks, or lists. Speak naturally as if talking to a person. "
        "Be warm, helpful, and occasionally witty."
    )
    try:
        from openjarvis.memory.memory_manager import load_memory, format_memory_for_prompt
        mem = load_memory()
        block = format_memory_for_prompt(mem)
        if block:
            return base + "\n\n" + block
    except Exception:
        pass
    return base


def _llm_answer(question: str) -> str:
    global _HISTORY
    _HISTORY.append({"role": "user", "content": question})
    if len(_HISTORY) > _MAX_HISTORY:
        _HISTORY = _HISTORY[-_MAX_HISTORY:]
    messages = [{"role": "system", "content": _build_system_prompt()}] + _HISTORY
    resp = _GROQ.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=200,
        temperature=0.75,
    )
    answer = resp.choices[0].message.content or ""
    _HISTORY.append({"role": "assistant", "content": answer})
    return answer


# ══════════════════════════════════════════════════════════════════════════════
# VAD — continuous listening
# ══════════════════════════════════════════════════════════════════════════════

def _rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def _calibrate_ambient(duration_s: float = 1.5) -> float:
    """Measure ambient noise level so we can set a good threshold."""
    frames: list[np.ndarray] = []
    q: queue.Queue[np.ndarray] = queue.Queue()

    def cb(indata, *_):
        q.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        dtype="float32", blocksize=FRAME_SAMPLES, callback=cb):
        deadline = time.time() + duration_s
        while time.time() < deadline:
            try:
                frames.append(q.get(timeout=0.5))
            except queue.Empty:
                pass

    if not frames:
        return ENERGY_THRESHOLD
    rms_vals = [_rms(f) for f in frames]
    ambient = float(np.mean(rms_vals))
    # threshold = ambient * 3, but at least the default minimum
    threshold = max(ENERGY_THRESHOLD, ambient * 3.5)
    print(f"  Ambient noise: {ambient:.4f}  →  threshold set to {threshold:.4f}")
    return threshold


def record_utterance(threshold: float) -> np.ndarray | None:
    """
    Block until the user speaks, record the utterance, return audio array.
    Returns None if nothing was detected within 2 s of a queue timeout.
    Skips recording while Jarvis is speaking (avoids echo loops).
    """
    q: queue.Queue[np.ndarray] = queue.Queue()

    def cb(indata, *_):
        q.put(indata[:, 0].copy())

    pre_roll:      list[np.ndarray] = []
    speech_frames: list[np.ndarray] = []
    speech_started  = False
    silent_count    = 0
    total_frames    = 0
    silence_needed  = int(SILENCE_TIMEOUT_S * 1000 / FRAME_MS)
    max_frames      = int(MAX_RECORD_S * 1000 / FRAME_MS)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        dtype="float32", blocksize=FRAME_SAMPLES, callback=cb):
        while True:
            # Don't listen while Jarvis is speaking
            if _SPEAKING.is_set():
                try:
                    q.get(timeout=0.1)   # drain queue
                except queue.Empty:
                    pass
                continue

            try:
                frame = q.get(timeout=2.0)
            except queue.Empty:
                break   # return None — outer loop will call again

            energy = _rms(frame)
            total_frames += 1

            if not speech_started:
                pre_roll.append(frame)
                if len(pre_roll) > PRE_ROLL_FRAMES:
                    pre_roll.pop(0)
                if energy > threshold:
                    speech_started = True
                    print("  >> Heard you — recording...", end="\r", flush=True)
                    speech_frames.extend(pre_roll)
                    speech_frames.append(frame)
                    silent_count = 0
            else:
                speech_frames.append(frame)
                if energy < threshold:
                    silent_count += 1
                    if silent_count >= silence_needed:
                        print("  >> Done listening.                  ")
                        break
                else:
                    silent_count = 0

            if total_frames >= max_frames:
                print("  >> (max length reached)")
                break

    if not speech_started or len(speech_frames) < 5:
        return None
    return np.concatenate(speech_frames, axis=0)


# ══════════════════════════════════════════════════════════════════════════════
# STT
# ══════════════════════════════════════════════════════════════════════════════

def transcribe(audio: np.ndarray) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name
        sf.write(path, audio, SAMPLE_RATE)
    try:
        with open(path, "rb") as f:
            result = _GROQ.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text",
            )
        return (result if isinstance(result, str) else str(result)).strip()
    finally:
        os.unlink(path)


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLER
# ══════════════════════════════════════════════════════════════════════════════

_SHUTDOWN_PHRASES = {
    "shutdown jarvis", "shut down jarvis", "turn off jarvis",
    "goodbye jarvis", "exit", "quit", "go offline", "offline",
    "stop jarvis", "jarvis shutdown", "jarvis exit",
}

_PLUGIN_TRIGGERS = (
    "time", "date", "day", "today",
    "news", "headlines",
    "weather",
    "note", "make a note", "remember this", "my notes", "show notes",
    "remember", "memorize", "what do you know", "my memory", "forget", "recall",
    "joke", "tell a joke",
    "tell me about", "who is", "wikipedia", "wiki",
    "system info", "cpu usage", "ram usage", "battery", "ip address",
    "where am i", "my location",
    "play", "youtube", "play music",
    "calculate",
    "remind me", "reminder",
    "analyze screen", "what's on my screen",
    "email", "send email",
    "location",
)


def _handle(text: str, threshold: float) -> bool:
    """Process one utterance. Returns False if Jarvis should shut down."""
    lower = text.lower().strip()

    # ── Shutdown ──────────────────────────────────────────────────────────────
    if any(lower == ph or lower.rstrip(".!? ") == ph for ph in _SHUTDOWN_PHRASES):
        _say("Understood. Shutting down. It was a pleasure, sir. Goodbye!")
        return False

    # ── Greeting ──────────────────────────────────────────────────────────────
    if lower in _GREETINGS or lower.rstrip(".! ") in _GREETINGS:
        reply = random.choice(_GREET_RESPONSES)
        _HISTORY.append({"role": "user",      "content": text})
        _HISTORY.append({"role": "assistant", "content": reply})
        _say(reply)
        return True

    # ── Machine control ───────────────────────────────────────────────────────
    mc = _run_machine_command(text)
    if mc:
        _HISTORY.append({"role": "user",      "content": text})
        _HISTORY.append({"role": "assistant", "content": mc})
        _say(mc)
        return True

    # ── Plugins ───────────────────────────────────────────────────────────────
    if any(lower.startswith(kw.strip()) or kw.strip() in lower for kw in _PLUGIN_TRIGGERS):
        print("  [Plugin]")
        result = _dispatch_plugin(text)
        if result:
            _HISTORY.append({"role": "user",      "content": text})
            _HISTORY.append({"role": "assistant", "content": result})
            _say(result)
            return True
        print("  [Plugin: no match — falling back to LLM]")

    # ── LLM Q&A ───────────────────────────────────────────────────────────────
    print("  [Thinking...]", end="\r", flush=True)
    answer = _llm_answer(text)
    _say(answer)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 62)
    print("  OpenJarvis — Voice Mode  v5  (Always On)")
    print("  Groq: Whisper STT  |  LLaMA 3.3 70B  |  Orpheus TTS")
    print("=" * 62)
    print()
    print("  Calibrating microphone — please be quiet for 1.5 seconds...")
    _load_plugins()
    threshold = _calibrate_ambient()
    print(f"  Ready. Just speak — Jarvis is always listening.")
    print(f"  Say 'shutdown Jarvis' to stop.")
    print()

    _startup_greeting()

    while True:
        try:
            print("  [Standby — listening...]", end="\r", flush=True)
            audio = record_utterance(threshold)
            if audio is None:
                continue   # no speech detected — keep listening

            print("  [Transcribing...]       ", end="\r", flush=True)
            text = transcribe(audio)
            if not text:
                print("  [Could not understand — listening again]")
                continue

            print(f"\n  You: \"{text}\"")
            running = _handle(text, threshold)
            if not running:
                break

        except KeyboardInterrupt:
            print("\n\n  Goodbye!")
            break
        except Exception as exc:
            print(f"\n  [Error: {exc}] — continuing...")
            time.sleep(0.3)

    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: (print("\n\n  Goodbye!"), os._exit(0)))
    main()
    input("\nPress Enter to close...")
