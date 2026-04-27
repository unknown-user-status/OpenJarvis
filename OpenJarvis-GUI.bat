@echo off
title OpenJarvis GUI
chcp 65001 >nul

:: ── Load API keys from Windows User environment ──────────────────────────────
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('GROQ_API_KEY','User')"') do set GROQ_API_KEY=%%i
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','User')"') do set OPENROUTER_API_KEY=%%i

set PYTHONUTF8=1
set LITELLM_LOG=ERROR
set JARVIS_PORT=7842

cd /d C:\Users\USER\openjarvis

:: ── Ensure fastapi + uvicorn are installed ────────────────────────────────────
echo Checking dependencies...
uv sync --extra server --quiet 2>nul

:: ── Start API server in background ───────────────────────────────────────────
echo Starting OpenJarvis API server on port %JARVIS_PORT%...
start "OpenJarvis-Server" /min cmd /c "cd /d C:\Users\USER\openjarvis && .venv\Scripts\python.exe start_server.py"

:: ── Wait up to 30s for server to be ready ────────────────────────────────────
echo Waiting for server to start...
set /a TRIES=0
:WAIT
timeout /t 1 /nobreak >nul
set /a TRIES+=1
powershell -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%JARVIS_PORT%/health' -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if %TRIES% LSS 30 goto WAIT
    echo ERROR: Server did not start after 30 seconds.
    echo Check the OpenJarvis-Server window for errors.
    pause
    exit /b 1
)
echo Server is ready!

:: ── Determine frontend URL ────────────────────────────────────────────────────
if exist "src\openjarvis\server\static\index.html" (
    set GUI_URL=http://127.0.0.1:%JARVIS_PORT%/jarvis
) else if exist "frontend\dist\index.html" (
    set GUI_URL=http://127.0.0.1:%JARVIS_PORT%/jarvis
) else (
    echo No built frontend found. Starting Vite dev server...
    start "OpenJarvis-Frontend" /min cmd /c "cd /d C:\Users\USER\openjarvis\frontend && npm run dev -- --port 5173"
    timeout /t 4 /nobreak >nul
    set GUI_URL=http://localhost:5173/jarvis
)

:: ── Open browser ─────────────────────────────────────────────────────────────
echo Opening %GUI_URL% ...
start "" "%GUI_URL%"

echo.
echo ================================================
echo   OpenJarvis GUI is running!
echo   API:      http://127.0.0.1:%JARVIS_PORT%
echo   Frontend: %GUI_URL%
echo.
echo   Press any key to close this window.
echo   The server keeps running in the background.
echo ================================================
pause >nul
