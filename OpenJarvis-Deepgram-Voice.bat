@echo off
title OpenJarvis Deepgram Voice Agent (One-to-One + Machine + Web)
chcp 65001 >nul

:: ── Load API keys from Windows User environment ──────────────────────────────
:: If set in Windows User env, these override config.toml.
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('DEEPGRAM_API_KEY','User')"') do set DEEPGRAM_API_KEY=%%i
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('FIRECRAWL_API_KEY','User')"') do set FIRECRAWL_API_KEY=%%i

set PYTHONUTF8=1
set LITELLM_LOG=ERROR

cd /d C:\Users\USER\OpenJarvis

:: ── Run Deepgram Voice Agent ────────────────────────────────────────────────
:: Uses .venv python directly for reliability (avoids uv caching issues).
.venv\Scripts\python.exe jarvis-deepgram-voice.py

pause
