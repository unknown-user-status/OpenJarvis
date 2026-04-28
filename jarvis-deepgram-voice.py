"""
OpenJarvis — Deepgram Voice Agent (v1)
========================================
Continuous two-way voice conversation powered by Deepgram's Voice Agent API.
No button pressing — just speak naturally. The agent listens, thinks, and replies
with natural voice.

Requirements
------------
- Python 3.10+
- websockets, sounddevice, numpy
- A working microphone and speakers
- Deepgram API key with Voice Agent access

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
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import websockets

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


def _get_api_key() -> str:
    """Resolve Deepgram API key: env → config → Windows registry."""
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if key:
        return key

    cfg = _load_deepgram_config()
    key = cfg.get("api_key", "").strip()
    if key:
        return key

    # Windows User env fallback
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, "DEEPGRAM_API_KEY")
            return v.strip()
    except Exception:
        pass

    return ""


# ── Audio constants ────────────────────────────────────────────────────────────
_MIC_RATE = 48_000          # Hz — Deepgram Voice Agent input
_MIC_CHANNELS = 1
_MIC_BLOCK = 2_400          # 50 ms at 48 kHz
_MIC_DTYPE = np.int16

_SPK_RATE = 24_000          # Hz — Deepgram Voice Agent output
_SPK_CHANNELS = 1
_SPK_BLOCK = 1_200          # 50 ms at 24 kHz
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

_WS_URL = _DG_CFG.get("endpoint", "wss://agent.deepgram.com/v1/agent")

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
            "prompt": _DG_CFG.get(
                "prompt",
                (
                    "You are a helpful personal AI assistant. "
                    "Keep responses concise and conversational."
                ),
            ),
        },
        "greeting": _DG_CFG.get("greeting", "Hello! How may I help you?"),
    },
}

# ── Threading queues ───────────────────────────────────────────────────────────
_MIC_Q: queue.Queue = queue.Queue(maxsize=200)
_SPK_Q: queue.Queue = queue.Queue(maxsize=200)
_SHUTDOWN = threading.Event()


def _mic_callback(indata, frames, time_info, status) -> None:
    """sounddevice InputStream callback — runs in its own thread."""
    if status:
        print(f"  [Mic status: {status}]")
    _MIC_Q.put(indata.copy())


def _spk_callback(outdata, frames, time_info, status) -> None:
    """sounddevice OutputStream callback — runs in its own thread."""
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


# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET TASKS
# ═══════════════════════════════════════════════════════════════════════════════

async def _send_audio(ws: websockets.WebSocketClientProtocol) -> None:
    """Forward microphone frames to Deepgram as binary messages."""
    while not _SHUTDOWN.is_set():
        try:
            frame = _MIC_Q.get(timeout=0.05)
            await ws.send(frame.tobytes())
        except queue.Empty:
            await asyncio.sleep(0.005)
        except websockets.exceptions.ConnectionClosed:
            break


async def _receive_messages(ws: websockets.WebSocketClientProtocol) -> None:
    """Handle all messages from Deepgram: text transcripts + audio."""
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
        elif msg_type == "Audio" and "audio" in payload:
            audio_bytes = base64.b64decode(payload["audio"])
            _queue_audio(audio_bytes)
        elif msg_type == "SettingsApplied":
            print("  [Deepgram settings applied — ready]")
        elif msg_type == "Error":
            print(f"  [Deepgram Error] {payload.get('message', payload)}")
        else:
            # Debug: uncomment to inspect unknown messages
            # print(f"  [Deepgram {msg_type}] {json.dumps(payload, indent=2)[:200]}")
            pass


def _queue_audio(audio_bytes: bytes) -> None:
    """Decode raw int16 bytes and push frame-sized chunks to the speaker queue."""
    if len(audio_bytes) < 2:
        return
    # Trim odd byte to keep int16 alignment
    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]
    audio = np.frombuffer(audio_bytes, dtype=_SPK_DTYPE)
    # Ensure shape is (frames, channels)
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)
    # Split into block-sized chunks
    for i in range(0, len(audio), _SPK_BLOCK):
        chunk = audio[i : i + _SPK_BLOCK]
        _SPK_Q.put(chunk)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def _main_async() -> None:
    """Connect to Deepgram Voice Agent and run bidirectional audio."""
    headers = {"Authorization": f"Token {_DEEPGRAM_API_KEY}"}

    print(f"  Connecting to {_WS_URL} ...")
    try:
        ws = await websockets.connect(_WS_URL, additional_headers=headers)
    except TypeError:
        # Fallback for older websockets versions (<14)
        ws = await websockets.connect(_WS_URL, extra_headers=headers)

    # Send Settings as first text message
    await ws.send(json.dumps(_SETTINGS))

    # Start audio streams (callbacks run in sounddevice's internal threads)
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
    print()

    # Run websocket tasks concurrently
    send_task = asyncio.create_task(_send_audio(ws))
    recv_task = asyncio.create_task(_receive_messages(ws))

    # Wait until shutdown is triggered
    while not _SHUTDOWN.is_set():
        await asyncio.sleep(0.1)

    # Cleanup
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
    print("  OpenJarvis — Deepgram Voice Agent")
    print("  Continuous two-way voice conversation")
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
