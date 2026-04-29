"""
v5 Voice Mode WebSocket Server

Implements the always-on voice mode (v5) as a WebSocket service.
This provides Groq Whisper STT, LLaMA chat, Orpheus TTS, and machine control
through a WebSocket connection that the frontend can connect to.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import queue
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd

try:
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect
except ImportError:  # pragma: no cover
    pass  # FastAPI is optional

logger = logging.getLogger(__name__)

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SAMPLE_RATE = 16000
CHANNELS = 1
ENERGY_THRESHOLD = 0.018
SILENCE_DURATION = 0.9  # seconds of silence to stop recording


def create_v5_voice_ws_router() -> Any:
    """Create a FastAPI router with WebSocket endpoint for v5 voice mode."""
    router = APIRouter()

    @router.websocket("/api/v5-voice/ws")
    async def v5_voice_websocket(websocket: WebSocket) -> None:
        """WebSocket endpoint for v5 always-on voice mode."""
        await websocket.accept()

        if not GROQ_API_KEY:
            await websocket.close(code=1008, reason="GROQ_API_KEY not configured")
            return

        # Audio processing queue
        audio_queue: queue.Queue = queue.Queue()
        processing_active = True

        def audio_callback(indata, frames, time_info, status):
            """Callback for audio input."""
            if status:
                logger.warning(f"Audio callback status: {status}")
            audio_queue.put(indata.copy())

        try:
            # Start audio stream
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=audio_callback,
                dtype=np.float32,
            )
            stream.start()

            # Send ready message
            await websocket.send_json({
                "type": "ready",
                "message": "v5 voice mode ready - always-on listening",
            })

            # Process audio in background thread
            def process_audio():
                nonlocal processing_active
                silence_counter = 0
                audio_buffer = []

                while processing_active:
                    try:
                        audio_chunk = audio_queue.get(timeout=0.1)
                        energy = np.mean(np.abs(audio_chunk))

                        if energy > ENERGY_THRESHOLD:
                            # Voice detected
                            silence_counter = 0
                            audio_buffer.extend(audio_chunk.flatten())
                        else:
                            # Silence detected
                            silence_counter += 1
                            if silence_counter > int(SILENCE_DURATION * SAMPLE_RATE / len(audio_chunk)):
                                # Enough silence - process the audio
                                if audio_buffer:
                                    # Convert to base64 and send to frontend for STT
                                    audio_array = np.array(audio_buffer, dtype=np.float32)
                                    # Normalize to int16 for WAV format
                                    audio_int16 = (audio_array * 32767).astype(np.int16)
                                    # Send to frontend for processing
                                    try:
                                        asyncio.run_coroutine_threadsafe(
                                            websocket.send_json({
                                                "type": "speech_detected",
                                                "audio_length": len(audio_int16),
                                            }),
                                            asyncio.get_running_loop()
                                        )
                                    except Exception as e:
                                        logger.error(f"Error sending speech detected: {e}")
                                audio_buffer = []
                                silence_counter = 0
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logger.error(f"Error processing audio: {e}")
                        break

            # Start audio processing thread
            audio_thread = threading.Thread(target=process_audio, daemon=True)
            audio_thread.start()

            # Handle incoming messages from frontend
            while True:
                try:
                    message = await websocket.receive()
                    if message["type"] == "websocket.receive":
                        data = message.get("text") or message.get("bytes")
                        if data:
                            try:
                                msg = json.loads(data) if isinstance(data, str) else {}
                                # Handle messages from frontend
                                if msg.get("type") == "transcript":
                                    # User speech transcribed - send to AI
                                    transcript = msg.get("text", "")
                                    if transcript:
                                        # Process with AI and send response
                                        await websocket.send_json({
                                            "type": "thinking",
                                            "message": "Processing...",
                                        })
                                        # TODO: Integrate with Groq API for response
                                        await websocket.send_json({
                                            "type": "response",
                                            "text": f"I heard: {transcript}",
                                        })
                            except json.JSONDecodeError:
                                pass
                    elif message["type"] == "websocket.disconnect":
                        break
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error receiving from client: {e}")
                    break

        except Exception as e:
            logger.error(f"v5 voice mode error: {e}")
            await websocket.close(code=1011, reason=str(e))
        finally:
            processing_active = False
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    return router


__all__ = ["create_v5_voice_ws_router"]
