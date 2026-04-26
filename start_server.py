"""
Minimal OpenJarvis API server launcher.

Starts a uvicorn server on http://127.0.0.1:7842 that serves:
  - /api/jarvis/chat  (text → plugin/LLM dispatch)
  - /api/jarvis/voice (audio → Whisper STT → dispatch → optional TTS)
  - /api/jarvis/tts   (text → Groq Orpheus WAV)
  - /api/desktop/*    (screenshot, desktop goals, voice)
  - /api/plugins/*    (list, run)
  - / → frontend (if frontend/dist/ exists after `npm run build`)

Usage
-----
  uv run python start_server.py
or
  .venv\\Scripts\\python.exe start_server.py
"""

from __future__ import annotations

import os
import pathlib
import sys

# ── Inject GROQ_API_KEY from Windows user env if not already set ─────────────
if not os.environ.get("GROQ_API_KEY"):
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "GROQ_API_KEY")
            os.environ["GROQ_API_KEY"] = value
    except Exception:
        pass

# ── Bootstrap src/ onto sys.path ─────────────────────────────────────────────
_root = pathlib.Path(__file__).parent
_src  = str(_root / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

os.environ.setdefault("LITELLM_LOG", "ERROR")
os.environ.setdefault("PYTHONUTF8",  "1")

PORT = int(os.environ.get("JARVIS_PORT", "7842"))

# ── Build a minimal FastAPI app ───────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="OpenJarvis GUI Server", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core jarvis routes ────────────────────────────────────────────────────────
from openjarvis.server.jarvis_routes  import jarvis_router
from openjarvis.server.desktop_routes import router as desktop_router, plugins_router

app.include_router(jarvis_router)
app.include_router(desktop_router)
app.include_router(plugins_router)

# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True, "port": PORT}

# ── Serve built frontend (if present) ────────────────────────────────────────
# Vite builds into src/openjarvis/server/static/ (configured in vite.config)
_dist = _root / "src" / "openjarvis" / "server" / "static"
if not _dist.is_dir():
    # fallback: old frontend/dist location
    _dist = _root / "frontend" / "dist"

if _dist.is_dir():
    _assets = _dist / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="fe-assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = (_dist / full_path).resolve()
        if candidate.is_relative_to(_dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("=" * 56)
    print("  OpenJarvis GUI Server")
    print(f"  http://127.0.0.1:{PORT}/jarvis")
    print("=" * 56)

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
