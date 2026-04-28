"""
OpenJarvis — Deepgram Voice Agent (v3)
========================================
Continuous two-way voice conversation powered by Deepgram's Voice Agent API,
PLUS full local machine control AND web research. Just speak naturally — the agent
listens, thinks, replies with voice, controls your computer, and researches online.

Machine control commands (say any of these):
- "open Chrome / Notepad / VS Code / Explorer / Spotify..."
- "close Chrome" (kill process)
- "type Hello world"  (types text at cursor)
- "press Enter / Ctrl S / Alt Tab..."
- "screenshot"  (saves to Desktop)
- "volume up / down / mute / set volume 50"
- "scroll up / down"
- "minimize all / lock screen / switch window"
- "new tab / close tab / copy / paste / undo / save / select all"
- "go to google.com"  (opens browser)
- "search for weather in Tokyo"
- "list apps"  (shows running processes)
- "what's in the clipboard"

Web research commands (say any of these):
- "research AI trends in 2025"
- "find out about quantum computing"
- "look up the latest Python version"
- "tell me about climate change"
- "explain how blockchains work"
- "investigate the history of the internet"

Requirements
------------
- Python 3.10+
- websockets, sounddevice, numpy, pyautogui, psutil, firecrawl-py
- A working microphone and speakers
- Deepgram API key with Voice Agent access
- Firecrawl API key for web research

Usage
-----
  .venv\Scripts\python.exe jarvis-deepgram-voice.py
  # or
  uv run python jarvis-deepgram-voice.py

Controls
--------
- Press Ctrl+C or close the window to stop.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import numpy as np
import pyautogui
import sounddevice as sd
import websockets

pyautogui.FAILSAFE = False  # let Jarvis control freely

# ── TOML loader (Python 3.10 compat) ──────────────────────────────────────────
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

# ── Config loader ────────────────────────────────────────────────────────────
_CONFIG_PATH = Path.home() / ".openjarvis" / "config.toml"


def _load_deepgram_config() -> dict:
    """Read Deepgram settings from ~/.openjarvis/config.toml if present."""
    if _CONFIG_PATH.exists():
        try:
            with _CONFIG_PATH.open("rb") as f:
                cfg = tomllib.load(f)
                return cfg.get("deepgram", {})
        except Exception as exc:
            print(f"  [warn] Could not read config: {exc}")
    return {}


def _load_firecrawl_config() -> dict:
    """Read Firecrawl settings from ~/.openjarvis/config.toml if present."""
    if _CONFIG_PATH.exists():
        try:
            with _CONFIG_PATH.open("rb") as f:
                cfg = tomllib.load(f)
                return cfg.get("firecrawl", {})
        except Exception as exc:
            print(f"  [warn] Could not read Firecrawl config: {exc}")
    return {}


def _get_api_key() -> str:
    """Resolve Deepgram API key: env → config → Windows registry."""
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if key:
        return key

    cfg = _load_deepgram_config()
    key = cfg.get("api_key", "").strip()
    if key:
        return key

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, "DEEPGRAM_API_KEY")
            return v.strip()
    except Exception:
        pass

    return ""


def _get_firecrawl_api_key() -> str:
    """Resolve Firecrawl API key: env → config → Windows registry."""
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        return key

    cfg = _load_firecrawl_config()
    key = cfg.get("api_key", "").strip()
    if key:
        return key

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, "FIRECRAWL_API_KEY")
            return v.strip()
    except Exception:
        pass

    return ""


# ══════════════════════════════════════════════════════════════════════════════
# MACHINE CONTROL (ported from jarvis-voice.py)
# ══════════════════════════════════════════════════════════════════════════════


def _open_app(name: str) -> str:
    name_lower = name.lower().strip()
    aliases = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "firefox": "firefox",
        "notepad": "notepad",
        "notepad++": "notepad++",
        "calculator": "calc",
        "calc": "calc",
        "file explorer": "explorer",
        "explorer": "explorer",
        "paint": "mspaint",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "outlook": "outlook",
        "teams": "teams",
        "discord": "discord",
        "spotify": "spotify",
        "vlc": "vlc",
        "cmd": "cmd",
        "command prompt": "cmd",
        "powershell": "powershell",
        "task manager": "taskmgr",
        "control panel": "control",
        "settings": "ms-settings:",
        "snipping tool": "snippingtool",
        "vs code": "code",
        "vscode": "code",
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
    try:
        path = save_path or str(Path.home() / "Desktop" / f"screenshot_{int(time.time())}.png")
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
        try:
            pct = max(0, min(100, level))
            if shutil.which("nircmd"):
                subprocess.run(
                    f"nircmd setvolume 0 {int(pct * 655.35)} {int(pct * 655.35)}",
                    shell=True,
                )
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
    """Interpret a machine-control sentence and execute it."""
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
    if ("what's in" in t and "clipboard" in t) or "read clipboard" in t or "clipboard content" in t:
        content = _get_clipboard()
        return f"Clipboard contains: {content}"

    return None


# ══════════════════════════════════════════════════════════════════════════════
# WEB RESEARCH (Firecrawl)
# ══════════════════════════════════════════════════════════════════════════════


def _web_research(query: str) -> str:
    """Use Firecrawl to research a topic and summarize."""
    api_key = _get_firecrawl_api_key()
    if not api_key:
        return "Firecrawl API key not configured."

    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=api_key)
        # First, try to search for relevant pages
        search_result = app.search(query, {
            "pageOptions": {
                "onlyMainContent": True,
                "onlyIncludeTags": ["article", "content"],
            }
        })
        if not search_result or not search_result.get("data"):
            return f"No results found for: {query}"

        # Get content from top result
        top_result = search_result["data"][0]
        url = top_result.get("markdown", "") or top_result.get("url", "")
        if url:
            # Scrape the top result for full content
            scrape_result = app.scrape_url(url, {"formats": ["markdown"]})
            content = scrape_result.get("markdown", "")
            if content:
                # Truncate for voice output
                summary = content[:500]
                return f"Researching {query}. Found: {summary}..."
        return f"Found information about {query}."
    except Exception as e:
        return f"Web research failed: {e}"


def _run_web_research(text: str) -> str | None:
    """Check if text is a web research query and execute it."""
    t = text.lower().strip()
    research_keywords = (
        "research ", "find out about ", "look up ", "tell me about ",
        "what is ", "who is ", "explain ", "investigate ",
        "search the web for ", "web research on ",
    )
    for kw in research_keywords:
        if t.startswith(kw):
            query = text[len(kw):].strip()
            return _web_research(query)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL TTS (Windows SAPI / PowerShell fallback)
# ══════════════════════════════════════════════════════════════════════════════


def _local_speak(text: str) -> bool:
    """Speak text using Windows SAPI or PowerShell — no network required."""
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(text)
        return True
    except Exception:
        pass
    try:
        cmd = (
            f'Add-Type -AssemblyName System.Speech; '
            f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'
        )
        subprocess.run(["powershell", "-Command", cmd], check=True, capture_output=True)
        return True
    except Exception:
        pass
    return False


# ══════════════════════════════════════════════════════════════════════════════
# AUDIO + WEBSOCKET
# ══════════════════════════════════════════════════════════════════════════════

# ── Audio constants ────────────────────────────────────────────────────────────
_MIC_RATE = 48_000
_MIC_CHANNELS = 1
_MIC_BLOCK = 2_400
_MIC_DTYPE = np.int16

_SPK_RATE = 24_000
_SPK_CHANNELS = 1
_SPK_BLOCK = 1_200
_SPK_DTYPE = np.int16

# ── Deepgram config ────────────────────────────────────────────────────────────
_DG_CFG = _load_deepgram_config()
_DEEPGRAM_API_KEY = _get_api_key()
if not _DEEPGRAM_API_KEY:
    print("ERROR: Deepgram API key not found.")
    print(
        "Set DEEPGRAM_API_KEY environment variable or add it to ~/.openjarvis/config.toml"
    )
    input("Press Enter to close...")
    sys.exit(1)

# ── Deepgram endpoint (with fallbacks for API changes) ────────────────────────
_POSSIBLE_ENDPOINTS = [
    _DG_CFG.get("endpoint", ""),
    "wss://api.eu.deepgram.com/v1/agent/converse",  # EU endpoint (from docs)
    "wss://api.deepgram.com/v1/agent/converse",    # US endpoint (if exists)
    "wss://agent.deepgram.com/v1/agent",
    "wss://listen.deepgram.com/v1/agent",
    "wss://api.deepgram.com/v1/listen",  # standard STT endpoint
]
_WS_URL = _DG_CFG.get("endpoint", "wss://api.eu.deepgram.com/v1/agent/converse")

_DEFAULT_PROMPT = (
    "You are a helpful personal AI assistant with full access to the user's computer and web research capabilities.\n"
    "Keep responses concise (1–2 sentences, under 120 characters) unless asked for detail.\n"
    "Speak naturally — no markdown, no bullet points, no code blocks.\n"
    "IMPORTANT: If the user asks to open apps, control volume, take screenshots, type text, "
    "scroll, lock the screen, manage windows, or do anything with the computer, "
    "just say 'Done' or 'OK' very briefly. The local system handles the action automatically. "
    "Do NOT describe how to do it — just confirm it is done.\n"
    "If the user asks to research something, look up information, investigate a topic, "
    "or search the web, the local system handles it using Firecrawl. Just say 'Researching...' briefly. "
    "Do NOT try to answer from your training data — let the research tool find current information.\n"
    "Be warm, friendly, and conversational."
)

_SETTINGS = {
    "type": "Settings",
    "audio": {
        "input": {"encoding": "linear16", "sample_rate": _MIC_RATE},
        "output": {
            "encoding": "linear16",
            "sample_rate": _SPK_RATE,
            "container": "none",
        },
    },
    "agent": {
        "speak": {
            "provider": {
                "type": "deepgram",
                "model": _DG_CFG.get("speak_model", "aura-2-odysseus-en"),
            }
        },
        "listen": {
            "provider": {
                "type": "deepgram",
                "version": "v2",
                "model": _DG_CFG.get("listen_model", "flux-general-en"),
            }
        },
        "think": {
            "provider": {
                "type": _DG_CFG.get("think_provider", "google"),
                "model": _DG_CFG.get("think_model", "gemini-2.5-flash"),
            },
            "prompt": _DG_CFG.get("prompt", _DEFAULT_PROMPT),
        },
        "greeting": _DG_CFG.get("greeting", "Hello! How may I help you?"),
    },
}

# ── Threading queues ───────────────────────────────────────────────────────────
_MIC_Q: queue.Queue = queue.Queue(maxsize=200)
_SPK_Q: queue.Queue = queue.Queue(maxsize=200)
_SHUTDOWN = threading.Event()


def _mic_callback(indata, frames, time_info, status) -> None:
    if status:
        print(f"  [Mic status: {status}]")
    _MIC_Q.put(indata.copy())


def _spk_callback(outdata, frames, time_info, status) -> None:
    if status:
        print(f"  [Spk status: {status}]")
    try:
        chunk = _SPK_Q.get_nowait()
        n = min(frames, len(chunk))
        if outdata.ndim == 1:
            outdata[:n] = chunk[:n].ravel()
        else:
            outdata[:n] = chunk[:n].reshape(-1, outdata.shape[1])
        if n < frames:
            outdata[n:] = 0
    except queue.Empty:
        outdata[:] = 0


async def _send_audio(ws: websockets.WebSocketClientProtocol) -> None:
    while not _SHUTDOWN.is_set():
        try:
            frame = _MIC_Q.get(timeout=0.05)
            await ws.send(frame.tobytes())
        except queue.Empty:
            await asyncio.sleep(0.005)
        except websockets.exceptions.ConnectionClosed:
            break


async def _receive_messages(ws: websockets.WebSocketClientProtocol) -> None:
    while not _SHUTDOWN.is_set():
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
        except asyncio.TimeoutError:
            continue
        except websockets.exceptions.ConnectionClosed:
            print("  [Connection closed by server]")
            _SHUTDOWN.set()
            break

        # ---- Binary audio from server ----------------------------------------
        if isinstance(msg, bytes):
            _queue_audio(msg)
            continue

        # ---- JSON control / text / audio -------------------------------------
        try:
            payload = json.loads(msg)
        except json.JSONDecodeError:
            continue

        msg_type = payload.get("type", "")

        if msg_type == "UserStartedSpeaking":
            print("  >> You started speaking")
        elif msg_type == "AgentStartedSpeaking":
            print("  >> Agent is speaking...")
        elif msg_type == "AgentAudioDone":
            print("  >> Agent finished")
        elif msg_type in ("ConversationText", "Transcript"):
            role = payload.get("role", "agent")
            content = payload.get("content", payload.get("text", ""))
            if content:
                prefix = "You" if role == "user" else "Jarvis"
                print(f"\n  {prefix}: {content}\n")
                # ── MACHINE CONTROL HOOK ──
                if role == "user":
                    result = _run_machine_command(content)
                    if result:
                        print(f"  [Action] {result}")
                        _local_speak(result)
                    # ── WEB RESEARCH HOOK ──
                    research_result = _run_web_research(content)
                    if research_result:
                        print(f"  [Research] {research_result}")
                        _local_speak(research_result)
        elif msg_type == "Audio" and "audio" in payload:
            audio_bytes = base64.b64decode(payload["audio"])
            _queue_audio(audio_bytes)
        elif msg_type == "SettingsApplied":
            print("  [Deepgram settings applied — ready]")
        elif msg_type == "Error":
            print(f"  [Deepgram Error] {payload.get('message', payload)}")
        else:
            pass


def _queue_audio(audio_bytes: bytes) -> None:
    if len(audio_bytes) < 2:
        return
    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]
    audio = np.frombuffer(audio_bytes, dtype=_SPK_DTYPE)
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)
    for i in range(0, len(audio), _SPK_BLOCK):
        chunk = audio[i : i + _SPK_BLOCK]
        _SPK_Q.put(chunk)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def _main_async() -> None:
    # Try endpoints in sequence until one works
    ws = None
    connected_url = None
    for url in _POSSIBLE_ENDPOINTS:
        if not url:
            continue
        print(f"  Trying {url} ...")
        try:
            ws = await asyncio.wait_for(websockets.connect(url), timeout=10)
            connected_url = url
            print(f"  Connected to {url}")
            break
        except websockets.exceptions.InvalidStatus as e:
            print(f"  {url} returned {e}")
        except asyncio.TimeoutError:
            print(f"  {url} timed out")
        except TypeError as e:
            print(f"  {url} parameter error: {e}")
        except Exception as e:
            print(f"  {url} failed: {e}")

    if ws is None:
        print("  ERROR: Could not connect to any Deepgram endpoint.")
        print("  Tried the following endpoints:")
        for url in _POSSIBLE_ENDPOINTS:
            if url:
                print(f"    - {url}")
        print()
        print("  Possible issues:")
        print("  1. Deepgram Voice Agent API may have changed — check docs")
        print("  2. API key may be invalid or expired")
        print("  3. Network connectivity issue")
        input("Press Enter to close...")
        sys.exit(1)

    # Send Settings with auth token embedded in message
    settings_with_auth = {**_SETTINGS, "token": _DEEPGRAM_API_KEY}
    await ws.send(json.dumps(settings_with_auth))

    mic_stream = sd.InputStream(
        samplerate=_MIC_RATE,
        channels=_MIC_CHANNELS,
        dtype=_MIC_DTYPE,
        blocksize=_MIC_BLOCK,
        callback=_mic_callback,
    )
    spk_stream = sd.OutputStream(
        samplerate=_SPK_RATE,
        channels=_SPK_CHANNELS,
        dtype=_SPK_DTYPE,
        blocksize=_SPK_BLOCK,
        callback=_spk_callback,
    )
    mic_stream.start()
    spk_stream.start()
    print("  [Microphone active — speak naturally]")
    print("  [Speakers active]")
    print("  [Machine control ready — say commands like 'open Chrome']")
    print("  [Web research ready — say 'research AI trends']")
    print()

    send_task = asyncio.create_task(_send_audio(ws))
    recv_task = asyncio.create_task(_receive_messages(ws))

    while not _SHUTDOWN.is_set():
        await asyncio.sleep(0.1)

    send_task.cancel()
    recv_task.cancel()
    try:
        await ws.close()
    except Exception:
        pass
    mic_stream.stop()
    mic_stream.close()
    spk_stream.stop()
    spk_stream.close()
    print("  [Disconnected]")


def main() -> None:
    print("=" * 62)
    print("  OpenJarvis — Deepgram Voice Agent + Machine + Web")
    print("  Speak naturally. Control your PC. Research online.")
    print("=" * 62)
    print()

    if sys.platform == "win32":
        import signal

        def _on_sigint(*_):
            print("\n  [Shutdown signal]")
            _SHUTDOWN.set()

        signal.signal(signal.SIGINT, _on_sigint)

    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        _SHUTDOWN.set()
    finally:
        print("\n  Goodbye!")


if __name__ == "__main__":
    main()
    input("\nPress Enter to close...")
