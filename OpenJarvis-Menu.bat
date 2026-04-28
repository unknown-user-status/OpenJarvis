@echo off
title OpenJarvis Launcher
chcp 65001 >nul
cd /d C:\Users\USER\OpenJarvis

:MENU
cls
echo.
echo ================================================================
echo   OpenJarvis — AI Personal Assistant
echo ================================================================
echo.
echo   Choose your mode:
echo.
echo   [1] GUI Mode          — Web interface in browser
echo   [2] Voice Mode v5     — Local VAD-based voice control
echo   [3] Deepgram Voice    — Continuous two-way voice (Deepgram API)
echo   [4] Terminal          — Interactive CLI
echo   [5] Exit
echo.
echo ================================================================
set /p CHOICE="Enter your choice (1-5): "

if "%CHOICE%"=="1" goto GUI
if "%CHOICE%"=="2" goto VOICE_V5
if "%CHOICE%"=="3" goto DEEPGRAM_VOICE
if "%CHOICE%"=="4" goto TERMINAL
if "%CHOICE%"=="5" goto EXIT
goto MENU

:GUI
call OpenJarvis-GUI.bat
goto MENU

:VOICE_V5
call OpenJarvis-Voice.bat
goto MENU

:DEEPGRAM_VOICE
call OpenJarvis-Deepgram-Voice.bat
goto MENU

:TERMINAL
"C:\Program Files\Git\bin\bash.exe" --login "C:\Users\USER\OpenJarvis\jarvis-terminal.sh"
goto MENU

:EXIT
exit
