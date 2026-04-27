"""
OpenJarvis GUI Server — full stack launcher.

Boots the complete OpenJarvis FastAPI application (same as `jarvis serve`)
so that ALL pages — Chat, Agents, Data Sources, Voice, Dashboard — work.

Usage
-----
  uv run python start_server.py
  .venv\\Scripts\\python.exe start_server.py
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys

# ── Read API keys from Windows User environment ───────────────────────────────
def _load_win_env(name: str) -> None:
    if os.environ.get(name):
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, name)
            os.environ[name] = v
    except Exception:
        pass

for _key in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY",
             "ANTHROPIC_API_KEY", "JARVIS_EMAIL", "JARVIS_EMAIL_PASS"):
    _load_win_env(_key)

# ── Bootstrap src/ onto sys.path ─────────────────────────────────────────────
_root = pathlib.Path(__file__).parent
_src  = str(_root / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

os.environ.setdefault("LITELLM_LOG", "ERROR")
os.environ.setdefault("PYTHONUTF8",  "1")

PORT = int(os.environ.get("JARVIS_PORT", "7842"))

logging.basicConfig(level=logging.WARNING)
for _log in ("openjarvis", "uvicorn", "litellm", "httpx", "httpcore"):
    logging.getLogger(_log).setLevel(logging.ERROR)

# ── Imports ───────────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# ── Boot the full OpenJarvis app ──────────────────────────────────────────────
try:
    from openjarvis.core.config import load_config
    from openjarvis.engine import get_engine
    from openjarvis.server.app import create_app
    from openjarvis.server.jarvis_routes import jarvis_router

    cfg = load_config()
    engine_name, engine = get_engine(cfg, None)

    model_name = (
        cfg.intelligence.default_model
        or cfg.server.model
        or "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    )

    # ── Agent Manager ─────────────────────────────────────────────────────────
    agent_manager = None
    agent_scheduler = None
    try:
        from openjarvis.agents.manager import AgentManager
        am_db = cfg.agent_manager.db_path or str(
            pathlib.Path.home() / ".openjarvis" / "agents.db"
        )
        pathlib.Path(am_db).parent.mkdir(parents=True, exist_ok=True)
        agent_manager = AgentManager(db_path=am_db)
        print(f"  Agents:  manager ready ({len(agent_manager.list_agents())} agents)")
    except Exception as e:
        print(f"  Agents:  unavailable ({e})")

    # ── Create full app ───────────────────────────────────────────────────────
    app = create_app(
        engine=engine,
        model=model_name,
        engine_name=engine_name,
        config=cfg,
        agent_manager=agent_manager,
        cors_origins=["*"],
    )

    # Add the Jarvis chat/voice/tts routes
    app.include_router(jarvis_router)

    print(f"  Engine:  {engine_name}")
    print(f"  Model:   {model_name}")

except Exception as _boot_err:
    import traceback
    print(f"[warn] Full boot failed: {_boot_err}")
    traceback.print_exc()
    print("[warn] Starting minimal fallback server...")

    from openjarvis.server.jarvis_routes  import jarvis_router
    from openjarvis.server.desktop_routes import router as desktop_router, plugins_router

    app = FastAPI(title="OpenJarvis GUI Server (minimal)", version="3.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    app.include_router(jarvis_router)
    app.include_router(desktop_router)
    app.include_router(plugins_router)

    @app.get("/v1/managed-agents")
    def _agents(): return {"agents": []}
    @app.get("/v1/templates")
    def _templates(): return {"templates": []}
    @app.get("/v1/models")
    def _models(): return {"data": [{"id": "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "object": "model"}]}
    @app.get("/v1/info")
    def _info(): return {"model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "version": "3.0.0"}
    @app.get("/v1/connectors")
    @app.get("/v1/connectors/list")
    def _connectors(): return {"connectors": []}
    @app.get("/v1/memory/stats")
    def _mem_stats(): return {"total_items": 0, "total_tokens": 0}
    @app.post("/v1/memory/search")
    def _mem_search(): return {"results": []}
    @app.get("/v1/savings")
    def _savings(): return {"total_calls": 0, "total_tokens": 0, "per_provider": []}
    @app.get("/v1/traces")
    def _traces(): return {"traces": []}
    @app.get("/v1/telemetry/stats")
    def _telemetry(): return {}
    @app.get("/v1/speech/health")
    def _speech():
        key = os.environ.get("GROQ_API_KEY", "")
        return {"available": bool(key), "backend": "groq_tts" if key else None}
    @app.get("/health")
    def _health(): return {"ok": True, "port": PORT}


# ── Add compat shims for endpoints the frontend expects ───────────────────────
# (these are no-ops if the full app already has them)

def _safe_add(method: str, path: str, fn):
    """Add a route only if no existing route matches that path."""
    existing = {getattr(r, 'path', '') for r in app.routes}
    if path not in existing:
        getattr(app, method)(path)(fn)

try:
    # /v1/connectors/list — frontend calls this but server uses /v1/connectors
    _safe_add("get", "/v1/connectors/list",
              lambda: JSONResponse({"connectors": []}))

    # /v1/managed-agents — only present if agent_manager was set up
    _safe_add("get", "/v1/managed-agents",
              lambda: JSONResponse({"agents": []}))

    # /v1/recommended-model
    _safe_add("get", "/v1/recommended-model",
              lambda: JSONResponse({"model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
                                    "reason": "Free model configured"}))
except Exception:
    pass


# ── Serve the built frontend ──────────────────────────────────────────────────
_dist = _root / "src" / "openjarvis" / "server" / "static"
if not _dist.is_dir():
    _dist = _root / "frontend" / "dist"

_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

if _dist.is_dir():
    _assets = _dist / "assets"
    if _assets.is_dir():
        try:
            app.mount("/assets", StaticFiles(directory=_assets), name="fe-assets-extra")
        except Exception:
            pass  # already mounted by create_app

    # The SPA fallback is already registered in create_app/app.py.
    # We only add it here for the minimal fallback path.
    existing_paths = {getattr(r, 'path', '') for r in app.routes}
    if "/{full_path:path}" not in existing_paths:
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            _skip = ("v1/", "api/", "health", "assets/",
                     "registerSW", "manifest.webmanifest", "favicon",
                     "apple-touch", "openapi.json", "docs", "redoc")
            for p in _skip:
                if full_path.startswith(p):
                    return JSONResponse({"detail": "Not found"}, status_code=404)
            candidate = (_dist / full_path).resolve()
            if full_path and candidate.is_relative_to(_dist.resolve()) and candidate.is_file():
                return FileResponse(candidate, headers=_NO_CACHE)
            return FileResponse(_dist / "index.html", headers=_NO_CACHE)


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("=" * 56)
    print("  OpenJarvis GUI Server")
    print(f"  GUI:  http://127.0.0.1:{PORT}/jarvis")
    print(f"  API:  http://127.0.0.1:{PORT}/v1/")
    print(f"  Docs: http://127.0.0.1:{PORT}/docs")
    print("=" * 56)
    print("Starting uvicorn...")

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
