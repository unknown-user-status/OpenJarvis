@echo off
title OpenJarvis Voice Mode (v5 — Always On)
chcp 65001 >nul

:: Load API keys from Windows user environment
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('GROQ_API_KEY','User')"') do set GROQ_API_KEY=%%i
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','User')"') do set OPENROUTER_API_KEY=%%i
for /f "delims=" %%i in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('OPENAI_API_KEY','User')"') do set OPENAI_API_KEY=%%i

set PYTHONUTF8=1
set LITELLM_LOG=ERROR

cd /d C:\Users\USER\openjarvis

:: Use venv python directly — avoids uv caching stale versions
.venv\Scripts\python.exe jarvis-voice.py

pause
