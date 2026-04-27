"""OpenJarvis channel management API routes.

Endpoints
---------
GET  /api/channels
    List all supported channels with their connection status and config state.

POST /api/channels/{channel}/connect
    Connect a channel using credentials from request body.

POST /api/channels/{channel}/disconnect
    Disconnect a running channel.

POST /api/channels/{channel}/send
    Send a message (and optionally an image) via a connected channel.
    Body: {content, conversation_id?, image_b64?}

GET  /api/channels/{channel}/status
    Get status of a specific channel.

POST /api/channels/webchat/message
    Built-in no-setup chat.  Body: {text, conversation_id?}

POST /api/channels/whatsapp_baileys/connect
    Start WhatsApp Baileys bridge (QR-code auth via polling).

GET  /api/channels/whatsapp_baileys/qr
    Poll for the latest QR code string (empty string when connected).

POST /api/channels/telegram/photo
    Send a photo + caption via Telegram.
    Body: {chat_id, image_b64, caption?}
"""

from __future__ import annotations

import base64
import logging
import os
import pathlib
import queue
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
        "name": "WhatsApp Business",
        "description": "WhatsApp Business Cloud API (requires Meta developer account)",
        "icon": "📱",
        "fields": [
            {"key": "access_token", "label": "Access Token", "placeholder": "EAA..."},
            {"key": "phone_number_id", "label": "Phone Number ID", "placeholder": ""},
        ],
        "easy": False,
        "setup_url": "https://developers.facebook.com/",
        "setup_steps": [
            "Go to developers.facebook.com → Create App → Business",
            "Add 'WhatsApp' product → Get Phone Number ID and Temp Access Token",
            "Paste both below and click Connect",
            "Note: send-only until you set up a webhook for incoming messages",
        ],
    },
    "whatsapp_baileys": {
        "name": "WhatsApp (Personal)",
        "description": "Connect your personal WhatsApp by scanning a QR code — bidirectional",
        "icon": "💚",
        "fields": [],
        "easy": True,
        "setup_steps": [
            "Click Connect — a QR code will appear",
            "Open WhatsApp on your phone → Settings → Linked Devices → Link a Device",
            "Scan the QR code",
            "Done! Any message sent to your WhatsApp that mentions Jarvis gets an auto-reply",
        ],
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
    image_b64: Optional[str] = None   # optional image to send along with content


class TelegramPhotoRequest(BaseModel):
    chat_id: str
    image_b64: str
    caption: str = ""


class WebChatMessage(BaseModel):
    text: str
    conversation_id: str = "default"


# ---------------------------------------------------------------------------
# In-memory WebChat conversation store
# ---------------------------------------------------------------------------

_WEBCHAT_HISTORY: Dict[str, List[Dict[str, str]]] = {}

# ---------------------------------------------------------------------------
# WhatsApp Baileys state (QR code + status tracking)
# ---------------------------------------------------------------------------

_BAILEYS_QR: str = ""          # latest QR string, empty when connected
_BAILEYS_STATUS: str = "disconnected"
_BAILEYS_LOCK = threading.Lock()


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

    elif channel_id == "whatsapp_baileys":
        # Handled separately by the dedicated endpoint
        raise HTTPException(status_code=400, detail="Use POST /api/channels/whatsapp_baileys/connect")

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


# ---------------------------------------------------------------------------
# Telegram — send photo via Bot API
# ---------------------------------------------------------------------------

@channel_router.post("/telegram/photo")
async def telegram_send_photo(req: TelegramPhotoRequest):
    """Send a photo + caption to a Telegram chat.

    Useful for sharing camera snapshots, charts, screenshots, etc.
    The Telegram channel must be connected first.
    """
    with _CHANNEL_LOCK:
        instance = _ACTIVE_CHANNELS.get("telegram")
    if not instance:
        raise HTTPException(status_code=409, detail="Telegram is not connected")

    token = getattr(instance, "_token", None)
    if not token:
        raise HTTPException(status_code=500, detail="No Telegram token found on instance")

    try:
        import httpx
        img_bytes = base64.b64decode(req.image_b64)
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        files = {"photo": ("photo.jpg", img_bytes, "image/jpeg")}
        data = {"chat_id": req.chat_id}
        if req.caption:
            data["caption"] = req.caption[:1024]

        resp = httpx.post(url, data=data, files=files, timeout=15.0)
        if resp.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Telegram API error: {resp.text[:200]}")
        return {"ok": True, "chat_id": req.chat_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Photo send failed: {exc}")


# ---------------------------------------------------------------------------
# WhatsApp Baileys — personal WhatsApp via QR-code auth
# ---------------------------------------------------------------------------

def _start_baileys_bridge() -> None:
    """Start the Baileys Node.js bridge in a background thread, updating QR state."""
    global _BAILEYS_QR, _BAILEYS_STATUS

    _ensure_src_path()
    bridge_src = pathlib.Path(__file__).parents[2] / "channels" / "whatsapp_baileys_bridge"
    bridge_js = bridge_src / "dist" / "bridge.js"
    auth_dir = pathlib.Path.home() / ".openjarvis" / "whatsapp_baileys" / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)

    if not bridge_js.exists():
        logger.error("Baileys bridge not compiled — run: npm run build in %s", bridge_src)
        with _BAILEYS_LOCK:
            _BAILEYS_STATUS = "error"
        return

    import subprocess
    import json as _json

    def _thread():
        global _BAILEYS_QR, _BAILEYS_STATUS
        try:
            proc = subprocess.Popen(
                ["node", str(bridge_js), "--auth-dir", str(auth_dir)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            with _CHANNEL_LOCK:
                # Store proc reference so we can send commands
                _ACTIVE_CHANNELS["whatsapp_baileys"] = proc

            for line in proc.stdout:  # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = _json.loads(line)
                except Exception:
                    continue

                etype = evt.get("type", "")
                if etype == "qr":
                    with _BAILEYS_LOCK:
                        _BAILEYS_QR = evt.get("data", "")
                        _BAILEYS_STATUS = "waiting_qr"
                    # Generate QR image as base64 PNG
                    try:
                        import qrcode  # type: ignore
                        import io
                        img = qrcode.make(evt["data"])
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        with _BAILEYS_LOCK:
                            _BAILEYS_QR = base64.b64encode(buf.getvalue()).decode()
                    except ImportError:
                        pass  # keep raw string if qrcode not installed

                elif etype == "status":
                    s = evt.get("status", "disconnected")
                    with _BAILEYS_LOCK:
                        _BAILEYS_STATUS = s
                        if s == "connected":
                            _BAILEYS_QR = ""  # clear QR once connected

                elif etype == "message":
                    # Auto-reply via Jarvis
                    jid = evt.get("jid", "")
                    text = evt.get("text", "")
                    if text:
                        reply = _get_jarvis_reply(text)
                        try:
                            cmd = _json.dumps({"type": "send", "jid": jid, "text": reply})
                            proc.stdin.write(cmd + "\n")  # type: ignore[union-attr]
                            proc.stdin.flush()  # type: ignore[union-attr]
                        except Exception as exc:
                            logger.warning("Baileys send failed: %s", exc)

        except Exception as exc:
            logger.error("Baileys bridge crashed: %s", exc)
            with _BAILEYS_LOCK:
                _BAILEYS_STATUS = "error"

    t = threading.Thread(target=_thread, daemon=True, name="baileys-bridge")
    t.start()


@channel_router.post("/whatsapp_baileys/connect")
async def whatsapp_baileys_connect():
    """Start the WhatsApp Baileys bridge.

    If already connected, does nothing.  Otherwise launches the Node.js bridge
    and begins QR-code authentication.  Poll GET /whatsapp_baileys/qr for the
    QR code to display, then scan with your phone.
    """
    global _BAILEYS_STATUS, _BAILEYS_QR
    with _BAILEYS_LOCK:
        status = _BAILEYS_STATUS

    if status in ("connected", "waiting_qr"):
        return {"ok": True, "status": status, "message": "Bridge already running"}

    with _BAILEYS_LOCK:
        _BAILEYS_STATUS = "starting"
        _BAILEYS_QR = ""

    threading.Thread(target=_start_baileys_bridge, daemon=True).start()
    return {"ok": True, "status": "starting", "message": "Bridge starting — poll /qr for QR code"}


@channel_router.post("/whatsapp_baileys/disconnect")
async def whatsapp_baileys_disconnect():
    """Stop the WhatsApp Baileys bridge."""
    global _BAILEYS_STATUS, _BAILEYS_QR
    with _CHANNEL_LOCK:
        proc = _ACTIVE_CHANNELS.pop("whatsapp_baileys", None)
    if proc and hasattr(proc, "stdin") and proc.stdin:
        try:
            import json as _json
            proc.stdin.write(_json.dumps({"type": "disconnect"}) + "\n")
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
    with _BAILEYS_LOCK:
        _BAILEYS_STATUS = "disconnected"
        _BAILEYS_QR = ""
    return {"ok": True, "status": "disconnected"}


@channel_router.get("/whatsapp_baileys/qr")
async def whatsapp_baileys_qr():
    """Return the current QR code (base64 PNG) and bridge status.

    When status is 'connected', qr will be empty — stop polling.
    When status is 'waiting_qr', display the qr image for scanning.
    """
    with _BAILEYS_LOCK:
        return {
            "status": _BAILEYS_STATUS,
            "qr": _BAILEYS_QR,   # base64 PNG or empty string
            "connected": _BAILEYS_STATUS == "connected",
        }


__all__ = ["channel_router"]
