"""OpenJarvis channel management API routes.

Endpoints
---------
GET  /api/channels
    List all supported channels with their connection status and config state.

POST /api/channels/{channel}/connect
    Connect a channel using credentials from request body.
    Body: {bot_token?, app_token?, webhook_url?, ...}

POST /api/channels/{channel}/disconnect
    Disconnect a running channel.

POST /api/channels/{channel}/send
    Send a message via a connected channel.
    Body: {content, conversation_id?}

GET  /api/channels/{channel}/status
    Get status of a specific channel.

POST /api/channels/webchat/message
    Submit a message to the built-in WebChat channel and get a Jarvis reply.
    Body: {text, conversation_id?}
    This is the simplest way to chat — no external accounts needed.
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("openjarvis.server.channels")

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError:
    raise ImportError("fastapi and pydantic are required")

channel_router = APIRouter(prefix="/api/channels", tags=["channels"])

# ---------------------------------------------------------------------------
# Global channel registry (in-memory, lives for server lifetime)
# ---------------------------------------------------------------------------

_ACTIVE_CHANNELS: Dict[str, Any] = {}   # channel_id → channel instance
_CHANNEL_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Channel metadata (what we support + instructions)
# ---------------------------------------------------------------------------

SUPPORTED_CHANNELS = {
    "webchat": {
        "name": "Web Chat",
        "description": "Built-in browser chat — no setup needed",
        "icon": "💬",
        "fields": [],
        "easy": True,
    },
    "telegram": {
        "name": "Telegram",
        "description": "Chat with Jarvis via Telegram Bot",
        "icon": "✈️",
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "placeholder": "123456:ABC-DEF..."},
        ],
        "easy": True,
        "setup_url": "https://t.me/BotFather",
        "setup_steps": [
            "Open Telegram, search @BotFather",
            "Send /newbot → choose name and username",
            "Copy the token it gives you",
            "Paste it below and click Connect",
            "Open your bot in Telegram and start chatting!",
        ],
    },
    "discord": {
        "name": "Discord",
        "description": "Chat with Jarvis in a Discord server",
        "icon": "🎮",
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "placeholder": "MTI3..."},
        ],
        "easy": True,
        "setup_url": "https://discord.com/developers/applications",
        "setup_steps": [
            "Go to discord.com/developers/applications → New Application",
            "Go to Bot tab → Reset Token → copy it",
            "Enable 'Message Content Intent' in Privileged Gateway Intents",
            "OAuth2 → URL Generator → select bot + Send Messages → invite bot to server",
            "Paste token below and click Connect",
        ],
    },
    "slack": {
        "name": "Slack",
        "description": "DM Jarvis inside your Slack workspace",
        "icon": "💼",
        "fields": [
            {"key": "bot_token", "label": "Bot Token (xoxb-...)", "placeholder": "xoxb-..."},
            {"key": "app_token", "label": "App Token (xapp-...)", "placeholder": "xapp-..."},
        ],
        "easy": False,
        "setup_url": "https://api.slack.com/apps",
        "setup_steps": [
            "Go to api.slack.com/apps → Create New App → From an app manifest",
            "Paste the manifest from the docs/user-guide/channels-and-connectors.md",
            "Install to workspace → copy Bot Token (xoxb-...)",
            "Basic Information → App-Level Tokens → add connections:write → copy App Token (xapp-...)",
            "Paste both tokens below and click Connect",
        ],
    },
    "webhook": {
        "name": "Webhook",
        "description": "Receive messages via HTTP POST webhook",
        "icon": "🔗",
        "fields": [
            {"key": "url", "label": "Webhook URL", "placeholder": "https://..."},
            {"key": "secret", "label": "Secret (optional)", "placeholder": ""},
        ],
        "easy": False,
    },
    "email": {
        "name": "Email",
        "description": "Chat via email (SMTP/IMAP)",
        "icon": "📧",
        "fields": [
            {"key": "smtp_host", "label": "SMTP Host", "placeholder": "smtp.gmail.com"},
            {"key": "smtp_port", "label": "SMTP Port", "placeholder": "587"},
            {"key": "username", "label": "Email Address", "placeholder": "you@gmail.com"},
            {"key": "password", "label": "App Password", "placeholder": ""},
        ],
        "easy": False,
    },
    "whatsapp": {
        "name": "WhatsApp",
        "description": "WhatsApp Business API messaging",
        "icon": "📱",
        "fields": [
            {"key": "access_token", "label": "Access Token", "placeholder": "EAA..."},
            {"key": "phone_number_id", "label": "Phone Number ID", "placeholder": ""},
        ],
        "easy": False,
    },
}


# ---------------------------------------------------------------------------
# Helper: ensure channel module is importable
# ---------------------------------------------------------------------------

def _ensure_src_path() -> None:
    _src = str(pathlib.Path(__file__).parents[3])
    if _src not in sys.path:
        sys.path.insert(0, _src)


def _get_channel_class(channel_id: str):
    _ensure_src_path()
    import openjarvis.channels  # trigger registry  # noqa: F401
    from openjarvis.core.registry import ChannelRegistry
    cls = ChannelRegistry.get(channel_id)
    if cls is None:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
    return cls


# ---------------------------------------------------------------------------
# Jarvis LLM reply helper (reuse from jarvis_routes)
# ---------------------------------------------------------------------------

def _get_jarvis_reply(text: str) -> str:
    """Get a Jarvis reply for a WebChat message — tries plugins first, then LLM."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    _ensure_src_path()

    # Try plugin dispatch
    try:
        import pathlib as _p
        from openjarvis.plugins import load_directory, dispatch, JarvisContext
        custom_dir = _p.Path(__file__).parents[4] / "custom"
        load_directory(custom_dir)
        ctx = JarvisContext(api_key=api_key)
        result = dispatch(text, ctx)
        if result:
            return result
    except Exception:
        pass

    # Fall back to Groq LLM
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            system_prompt = (
                "You are OpenJarvis, a helpful AI assistant. "
                "Give concise, accurate answers in 1-3 sentences unless more detail is needed."
            )
            # Try to load memory context
            try:
                from openjarvis.memory.memory_manager import load_memory, format_memory_for_prompt
                mem_block = format_memory_for_prompt(load_memory())
                if mem_block:
                    system_prompt += "\n\n" + mem_block
            except Exception:
                pass

            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=512,
                temperature=0.7,
            )
            return resp.choices[0].message.content or "I'm not sure how to answer that."
        except Exception as exc:
            return f"Error getting response: {exc}"

    return "GROQ_API_KEY not set — cannot generate a response. Set it in your environment."


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    bot_token: Optional[str] = None
    app_token: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    access_token: Optional[str] = None
    phone_number_id: Optional[str] = None


class SendRequest(BaseModel):
    content: str
    conversation_id: str = ""


class WebChatMessage(BaseModel):
    text: str
    conversation_id: str = "default"


# ---------------------------------------------------------------------------
# In-memory WebChat conversation store
# ---------------------------------------------------------------------------

_WEBCHAT_HISTORY: Dict[str, List[Dict[str, str]]] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@channel_router.get("")
async def list_channels():
    """List all supported channels and their status."""
    result = []
    with _CHANNEL_LOCK:
        for ch_id, meta in SUPPORTED_CHANNELS.items():
            active = _ACTIVE_CHANNELS.get(ch_id)
            if active:
                try:
                    from openjarvis.channels._stubs import ChannelStatus
                    status = active.status()
                    status_str = status.value if hasattr(status, "value") else str(status)
                except Exception:
                    status_str = "unknown"
            else:
                status_str = "disconnected"

            result.append({
                "id": ch_id,
                "name": meta["name"],
                "description": meta["description"],
                "icon": meta["icon"],
                "status": status_str,
                "easy": meta.get("easy", False),
                "fields": meta.get("fields", []),
                "setup_steps": meta.get("setup_steps", []),
                "setup_url": meta.get("setup_url", ""),
            })
    return {"channels": result}


@channel_router.get("/{channel_id}/status")
async def channel_status(channel_id: str):
    """Get status of a specific channel."""
    with _CHANNEL_LOCK:
        active = _ACTIVE_CHANNELS.get(channel_id)
    if not active:
        return {"channel": channel_id, "status": "disconnected"}
    try:
        status = active.status()
        status_str = status.value if hasattr(status, "value") else str(status)
    except Exception:
        status_str = "unknown"
    return {"channel": channel_id, "status": status_str}


@channel_router.post("/{channel_id}/connect")
async def connect_channel(channel_id: str, req: ConnectRequest):
    """Connect a channel with the provided credentials."""
    if channel_id not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown channel: {channel_id}")

    # Build kwargs from request
    kwargs: Dict[str, Any] = {}
    if channel_id == "telegram":
        token = req.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise HTTPException(status_code=400, detail="bot_token is required for Telegram")
        kwargs["bot_token"] = token

    elif channel_id == "discord":
        token = req.bot_token or os.environ.get("DISCORD_BOT_TOKEN", "")
        if not token:
            raise HTTPException(status_code=400, detail="bot_token is required for Discord")
        kwargs["bot_token"] = token

    elif channel_id == "slack":
        bot_token = req.bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
        app_token = req.app_token or os.environ.get("SLACK_APP_TOKEN", "")
        if not bot_token:
            raise HTTPException(status_code=400, detail="bot_token (xoxb-...) is required for Slack")
        if not app_token:
            raise HTTPException(status_code=400, detail="app_token (xapp-...) is required for Slack")
        kwargs["bot_token"] = bot_token
        kwargs["app_token"] = app_token

    elif channel_id == "webhook":
        if not req.url:
            raise HTTPException(status_code=400, detail="url is required for Webhook")
        kwargs["url"] = req.url
        if req.secret:
            kwargs["secret"] = req.secret

    elif channel_id == "email":
        if not req.smtp_host or not req.username or not req.password:
            raise HTTPException(status_code=400, detail="smtp_host, username, password required for Email")
        kwargs = {
            "smtp_host": req.smtp_host,
            "smtp_port": req.smtp_port,
            "username": req.username,
            "password": req.password,
        }

    elif channel_id == "whatsapp":
        if not req.access_token or not req.phone_number_id:
            raise HTTPException(status_code=400, detail="access_token and phone_number_id required")
        kwargs = {"access_token": req.access_token, "phone_number_id": req.phone_number_id}

    elif channel_id == "webchat":
        pass  # no credentials needed

    # Disconnect existing instance if any
    with _CHANNEL_LOCK:
        old = _ACTIVE_CHANNELS.pop(channel_id, None)
    if old:
        try:
            old.disconnect()
        except Exception:
            pass

    # Register a handler that feeds incoming messages to Jarvis and auto-replies
    def _auto_reply_handler(msg):
        """Auto-reply via Jarvis when a message arrives on this channel."""
        try:
            reply = _get_jarvis_reply(msg.content)
            with _CHANNEL_LOCK:
                ch = _ACTIVE_CHANNELS.get(channel_id)
            if ch:
                ch.send(msg.conversation_id or msg.channel, reply,
                        conversation_id=msg.conversation_id)
        except Exception as exc:
            logger.warning("Auto-reply failed on %s: %s", channel_id, exc)

    # Instantiate and connect
    try:
        cls = _get_channel_class(channel_id)
        instance = cls(**kwargs)
        instance.on_message(_auto_reply_handler)
        instance.connect()
        with _CHANNEL_LOCK:
            _ACTIVE_CHANNELS[channel_id] = instance
        status = instance.status()
        status_str = status.value if hasattr(status, "value") else str(status)
        return {"channel": channel_id, "status": status_str, "ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to connect %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Connection failed: {exc}")


@channel_router.post("/{channel_id}/disconnect")
async def disconnect_channel(channel_id: str):
    """Disconnect a running channel."""
    with _CHANNEL_LOCK:
        instance = _ACTIVE_CHANNELS.pop(channel_id, None)
    if not instance:
        return {"channel": channel_id, "status": "disconnected", "ok": True}
    try:
        instance.disconnect()
    except Exception as exc:
        logger.warning("Disconnect error on %s: %s", channel_id, exc)
    return {"channel": channel_id, "status": "disconnected", "ok": True}


@channel_router.post("/{channel_id}/send")
async def send_message(channel_id: str, req: SendRequest):
    """Send a message via an active channel."""
    with _CHANNEL_LOCK:
        instance = _ACTIVE_CHANNELS.get(channel_id)
    if not instance:
        raise HTTPException(
            status_code=409,
            detail=f"Channel '{channel_id}' is not connected. Connect it first."
        )
    ok = instance.send(
        req.conversation_id or channel_id,
        req.content,
        conversation_id=req.conversation_id,
    )
    return {"ok": ok, "channel": channel_id}


# ---------------------------------------------------------------------------
# WebChat — built-in no-setup chat endpoint
# ---------------------------------------------------------------------------

@channel_router.post("/webchat/message")
async def webchat_chat(req: WebChatMessage):
    """Send a message to the built-in WebChat and receive a Jarvis reply.

    This is the zero-setup way to chat — works without any external accounts.
    Messages and replies are stored in memory per conversation_id.
    """
    conv_id = req.conversation_id or "default"
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # Store user message in history
    if conv_id not in _WEBCHAT_HISTORY:
        _WEBCHAT_HISTORY[conv_id] = []
    _WEBCHAT_HISTORY[conv_id].append({"role": "user", "content": text})

    # Get Jarvis reply
    reply = _get_jarvis_reply(text)

    # Store reply in history
    _WEBCHAT_HISTORY[conv_id].append({"role": "assistant", "content": reply})

    # Keep last 50 messages per conversation
    _WEBCHAT_HISTORY[conv_id] = _WEBCHAT_HISTORY[conv_id][-50:]

    return {
        "reply": reply,
        "conversation_id": conv_id,
        "history": _WEBCHAT_HISTORY[conv_id],
    }


@channel_router.get("/webchat/history/{conversation_id}")
async def webchat_history(conversation_id: str):
    """Get chat history for a conversation."""
    return {
        "conversation_id": conversation_id,
        "history": _WEBCHAT_HISTORY.get(conversation_id, []),
    }


@channel_router.delete("/webchat/history/{conversation_id}")
async def webchat_clear(conversation_id: str):
    """Clear chat history for a conversation."""
    _WEBCHAT_HISTORY.pop(conversation_id, None)
    return {"ok": True, "conversation_id": conversation_id}


__all__ = ["channel_router"]
