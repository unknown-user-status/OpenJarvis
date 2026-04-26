"""FastAPI routes for desktop control and voice command endpoints."""

from __future__ import annotations

import base64
import io
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger("openjarvis.server.desktop")

try:
    from fastapi import APIRouter, HTTPException, UploadFile, File
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError:
    raise ImportError("fastapi and pydantic are required")

router = APIRouter(prefix="/api/desktop", tags=["desktop"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DesktopGoalRequest(BaseModel):
    goal: str
    max_steps: int = 15


class DesktopGoalResponse(BaseModel):
    summary: str
    steps: int
    log: List[Dict[str, Any]]


class VoiceCommandResponse(BaseModel):
    transcript: str
    response: str
    mode: str  # 'qa' or 'control'


class ScreenshotResponse(BaseModel):
    base64_png: str
    width: int
    height: int


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

@router.get("/screenshot", response_model=ScreenshotResponse)
async def get_screenshot():
    """Capture the current screen and return as base64 PNG."""
    try:
        import pyautogui
        img = pyautogui.screenshot()
        # Downscale to 1280px wide for performance
        w, h = img.size
        if w > 1280:
            ratio = 1280 / w
            img = img.resize((1280, int(h * ratio)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return ScreenshotResponse(base64_png=b64, width=img.size[0], height=img.size[1])
    except ImportError:
        raise HTTPException(status_code=503, detail="pyautogui not installed. Run: uv sync --extra desktop")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Desktop goal (run DesktopAgent)
# ---------------------------------------------------------------------------

@router.post("/run", response_model=DesktopGoalResponse)
async def run_desktop_goal(request: DesktopGoalRequest):
    """Run the DesktopAgent to complete a goal on the local machine."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not set")

    log: List[Dict[str, Any]] = []

    try:
        from openjarvis.agents.desktop_agent import DesktopAgent

        class _LoggingAgent(DesktopAgent):
            def _log(self, msg: str) -> None:
                logger.info(msg)

        agent = _LoggingAgent(
            api_key=api_key,
            max_steps=request.max_steps,
            step_delay=1.0,
            verbose=False,
        )

        # Monkey-patch _execute to capture log entries
        original_execute = agent._execute

        def _patched_execute(action_obj):
            result, done, summary = original_execute(action_obj)
            log.append({
                "step": len(log) + 1,
                "action": action_obj.get("action", ""),
                "result": result,
                "success": not result.lower().startswith("error"),
            })
            return result, done, summary

        agent._execute = _patched_execute  # type: ignore[method-assign]

        summary = agent.run(request.goal)
        return DesktopGoalResponse(summary=summary, steps=len(log), log=log)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Voice command (STT + route to desktop/QA)
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
    lower = text.lower().strip()
    return any(lower.startswith(kw) or kw in lower for kw in _CONTROL_KEYWORDS)


@router.post("/voice", response_model=VoiceCommandResponse)
async def voice_command(audio: UploadFile = File(...)):
    """Accept audio file, transcribe via Groq Whisper, route to desktop or QA."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not set")

    # Save upload to temp file
    suffix = "." + (audio.filename or "audio.webm").rsplit(".", 1)[-1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

        # Transcribe
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text",
            )
        transcript = result.strip() if isinstance(result, str) else str(result).strip()

        if not transcript:
            return VoiceCommandResponse(transcript="", response="Could not understand audio.", mode="qa")

        # Route
        if _is_control_command(transcript):
            from openjarvis.agents.desktop_agent import DesktopAgent
            agent = DesktopAgent(api_key=api_key, max_steps=15, step_delay=1.0, verbose=False)
            response_text = agent.run(transcript)
            mode = "control"
        else:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": transcript}],
                max_tokens=1024,
                temperature=0.7,
            )
            response_text = resp.choices[0].message.content or ""
            mode = "qa"

        return VoiceCommandResponse(transcript=transcript, response=response_text, mode=mode)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Plugin system routes
# ---------------------------------------------------------------------------

plugins_router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginRunRequest(BaseModel):
    command: str


class PluginInfo(BaseModel):
    name: str
    help: str


@plugins_router.get("/list", response_model=List[PluginInfo])
async def list_plugins():
    """List all registered plugins."""
    try:
        import pathlib
        from openjarvis.plugins import get_plugins, load_directory
        # Load built-in custom plugins
        custom_dir = pathlib.Path(__file__).parents[4] / "custom"
        load_directory(custom_dir)
        plugins = get_plugins()
        return [PluginInfo(name=name, help=help_text) for name, (_, help_text) in plugins.items()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@plugins_router.post("/run")
async def run_plugin(request: PluginRunRequest):
    """Run a plugin command and return its output."""
    try:
        import pathlib
        from openjarvis.plugins import load_directory, dispatch, JarvisContext
        custom_dir = pathlib.Path(__file__).parents[4] / "custom"
        load_directory(custom_dir)
        ctx = JarvisContext()
        output = dispatch(request.command, ctx)
        if output is None:
            raise HTTPException(status_code=404, detail=f"No plugin matched: {request.command!r}")
        return {"output": output, "command": request.command}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


__all__ = ["router", "plugins_router"]
