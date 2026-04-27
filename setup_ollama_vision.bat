@echo off
title OpenJarvis - Ollama Vision Setup
color 0B

echo.
echo  ============================================================
echo   OpenJarvis - Ollama Vision Setup
echo   Recommended model: moondream (fastest, CPU-friendly)
echo  ============================================================
echo.

REM Check if Ollama is installed
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Ollama is NOT installed.
    echo.
    echo  Please download and install Ollama first:
    echo  https://ollama.com/download/windows
    echo.
    echo  After installing, run this script again.
    echo.
    pause
    start https://ollama.com/download/windows
    exit /b 1
)

echo  [OK] Ollama is installed.
echo.

REM Start Ollama serve in background (if not already running)
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] Starting Ollama server...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
) else (
    echo  [OK] Ollama server is already running.
)

echo.
echo  Choose which vision model to download:
echo.
echo  [1] moondream  ~1.7 GB  Fastest, works great on CPU, good for camera Q^&A
echo  [2] llava:7b    ~4.5 GB  Better quality, still runs on CPU (slower)
echo  [3] Both models (recommended if you have space)
echo.
set /p choice="Enter choice [1/2/3]: "

if "%choice%"=="1" goto pull_moondream
if "%choice%"=="2" goto pull_llava
if "%choice%"=="3" goto pull_both
echo Invalid choice, defaulting to moondream.

:pull_moondream
echo.
echo  [*] Pulling moondream (~1.7 GB)...
ollama pull moondream
echo.
echo  [OK] moondream ready!
goto done

:pull_llava
echo.
echo  [*] Pulling llava:7b (~4.5 GB)...
ollama pull llava:7b
echo.
echo  [OK] llava:7b ready!
goto done

:pull_both
echo.
echo  [*] Pulling moondream (~1.7 GB)...
ollama pull moondream
echo.
echo  [*] Pulling llava:7b (~4.5 GB)...
ollama pull llava:7b
echo.
echo  [OK] Both models ready!
goto done

:done
echo.
echo  ============================================================
echo   Setup complete! Available vision models:
echo  ============================================================
ollama list
echo.
echo  To use Camera Vision in OpenJarvis:
echo  1. Make sure Ollama is running (it starts automatically)
echo  2. Open the OpenJarvis GUI (OpenJarvis-GUI.bat)
echo  3. Click "Camera Vision" in the sidebar
echo.
echo  Voice commands (in Jarvis mode):
echo    "look at camera what do you see"
echo    "camera describe the scene"
echo    "webcam what am I holding"
echo.
pause
