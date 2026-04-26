@echo off
title OpenJarvis GUI

:: ── Load API keys from Windows User environment ──────────────────────────────
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('GROQ_API_KEY','User')"') do set GROQ_API_KEY=%%i
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','User')"') do set OPENROUTER_API_KEY=%%i

set PYTHONUTF8=1
set LITELLM_LOG=ERROR
set JARVIS_PORT=7842

cd /d C:\Users\USER\openjarvis

:: ── Start API server in background ───────────────────────────────────────────
echo Starting OpenJarvis API server on port %JARVIS_PORT%...
start "OpenJarvis-Server" /min cmd /c "uv run python start_server.py"

:: ── Wait for server to be ready ──────────────────────────────────────────────
echo Waiting for server...
:WAIT
timeout /t 1 /nobreak >nul
powershell -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%JARVIS_PORT%/health' -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto WAIT

:: ── Start React dev server if no built dist ──────────────────────────────────
if not exist "frontend\dist\index.html" (
    echo No built frontend found. Starting Vite dev server...
    start "OpenJarvis-Frontend" /min cmd /c "cd frontend && npm run dev -- --port 5173"
    timeout /t 3 /nobreak >nul
    set GUI_URL=http://localhost:5173/jarvis
) else (
    set GUI_URL=http://127.0.0.1:%JARVIS_PORT%/jarvis
)

:: ── Open browser ─────────────────────────────────────────────────────────────
echo Opening %GUI_URL% ...
start "" "%GUI_URL%"

echo.
echo ════════════════════════════════════════════════════
echo   OpenJarvis GUI is running!
echo   API:      http://127.0.0.1:%JARVIS_PORT%
echo   Frontend: %GUI_URL%
echo.
echo   Close this window to keep running in background.
echo   Close the minimised "OpenJarvis-Server" window to stop.
echo ════════════════════════════════════════════════════
pause
