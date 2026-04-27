# OpenJarvis — Agent / Developer Notes

## Workflow Rules

- **Always `git push` after every commit.** Never leave commits local-only.
- **Update `README.md`** after every new feature or significant fix — add it to the "Recent Improvements" section.
- Frontend changes must be built before committing: `cd frontend && npm run build`
- Build output goes to `src/openjarvis/server/static/` (already in `.gitignore`-safe location — commit the built files too).

## Project Layout

| Path | Purpose |
|------|---------|
| `src/openjarvis/` | Python backend (FastAPI server, engines, connectors, agents) |
| `src/openjarvis/server/routes.py` | All HTTP API routes |
| `src/openjarvis/server/upload_router.py` | File upload / ingest endpoints |
| `src/openjarvis/connectors/store.py` | KnowledgeStore — vector DB wrapper |
| `frontend/src/` | React/TypeScript UI |
| `frontend/src/pages/DataSourcesPage.tsx` | Data sources + upload UI |
| `frontend/src/components/Chat/` | Chat UI components |
| `frontend/src/components/CommandPalette.tsx` | Model download catalogue |
| `jarvis-voice.py` | Standalone voice mode (continuous conversation) |
| `custom/` | User plugin scripts |
| `OpenJarvis-GUI.bat` | Windows launcher for GUI server |
| `OpenJarvis-Voice.bat` | Windows launcher for voice mode |

## Build Commands

```bash
# Frontend
cd frontend && npm run build

# Run server (dev)
.venv/Scripts/jarvis.exe serve

# Run voice mode
.venv/Scripts/python.exe jarvis-voice.py
# or
uv run python jarvis-voice.py
```

## Key Known Issues / Fixes Applied

- `_is_ollama_available` — must use `_iter_engines()` to walk full wrapper chain
  (`InstrumentedEngine → GuardrailsEngine → MultiEngine`). MultiEngine._engines
  is a `list[tuple[str, engine]]`, not a dict.
- Chat error surface — `isError` flag on `ChatMessage` renders red banner instead
  of a normal bubble when the backend returns a generation error.
- Voice mode — `ENERGY_THRESHOLD = 0.015` in `jarvis-voice.py`. Raise to `0.025`
  in noisy environments to avoid false triggers.
