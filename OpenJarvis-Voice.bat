@echo off
title OpenJarvis Voice Mode (v4 — Continuous)

:: Load API keys from Windows environment
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('GROQ_API_KEY','User')"') do set GROQ_API_KEY=%%i
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','User')"') do set OPENROUTER_API_KEY=%%i

set PYTHONUTF8=1
set LITELLM_LOG=ERROR

cd /d C:\Users\USER\openjarvis
uv run python jarvis-voice.py

pause
