"""
Deepgram Voice Agent WebSocket Proxy

Proxies Deepgram Voice Agent API WebSocket connections to the frontend.
This allows the browser to connect to Deepgram without exposing the API key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

try:
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect
except ImportError:  # pragma: no cover
    pass  # FastAPI is optional

logger = logging.getLogger(__name__)

# Deepgram configuration
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
DEEPGRAM_ENDPOINT = os.environ.get(
    "DEEPGRAM_ENDPOINT",
    "wss://agent.deepgram.com/v1/agent/converse"
)


def create_deepgram_ws_router() -> Any:
    """Create a FastAPI router with WebSocket endpoint for Deepgram Voice Agent."""
    router = APIRouter()

    @router.websocket("/api/deepgram/ws")
    async def deepgram_websocket(websocket: WebSocket) -> None:
        """Proxy WebSocket connection to Deepgram Voice Agent API."""
        await websocket.accept()

        if not DEEPGRAM_API_KEY:
            await websocket.close(code=1008, reason="DEEPGRAM_API_KEY not configured")
            return

        # Connect to Deepgram
        deepgram_ws: WebSocket | None = None
        try:
            deepgram_ws = await asyncio.to_thread(
                _connect_to_deepgram,
                DEEPGRAM_ENDPOINT,
                DEEPGRAM_API_KEY
            )

            # Start bidirectional message forwarding
            await asyncio.gather(
                _forward_client_to_deepgram(websocket, deepgram_ws),
                _forward_deepgram_to_client(deepgram_ws, websocket),
            )
        except WebSocketDisconnect:
            logger.info("Client disconnected from Deepgram proxy")
        except Exception as e:
            logger.error(f"Deepgram proxy error: {e}")
            await websocket.close(code=1011, reason=str(e))
        finally:
            if deepgram_ws:
                try:
                    await asyncio.to_thread(deepgram_ws.close)
                except Exception:
                    pass

    return router


def _connect_to_deepgram(endpoint: str, api_key: str) -> Any:
    """Connect to Deepgram WebSocket (synchronous)."""
    import websockets
    headers = {"Authorization": f"Token {api_key}"}
    return websockets.connect(endpoint, additional_headers=headers)


async def _forward_client_to_deepgram(client_ws: WebSocket, deepgram_ws: Any) -> None:
    """Forward messages from client to Deepgram."""
    try:
        while True:
            # Receive audio/data from client
            message = await client_ws.receive()
            
            if message["type"] == "websocket.receive":
                data = message.get("bytes") or message.get("text")
                if data:
                    # Send to Deepgram
                    await asyncio.to_thread(deepgram_ws.send, data)
            elif message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error forwarding to Deepgram: {e}")


async def _forward_deepgram_to_client(deepgram_ws: Any, client_ws: WebSocket) -> None:
    """Forward messages from Deepgram to client."""
    try:
        while True:
            # Receive from Deepgram
            message = await asyncio.to_thread(deepgram_ws.recv)
            if message:
                # Send to client
                if isinstance(message, bytes):
                    await client_ws.send_bytes(message)
                else:
                    await client_ws.send_text(message)
    except Exception as e:
        logger.error(f"Error receiving from Deepgram: {e}")


__all__ = ["create_deepgram_ws_router"]
