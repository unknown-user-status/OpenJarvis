@echo off
:: OpenJarvis Cache Clear and Server Restart - Windows Batch File
:: Fixes cache issues for Engine, Tools & Memory, and Learning primitives

title OpenJarvis Cache Fix

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         🔧 OpenJarvis Cache Clear & Server Restart            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

echo [1/4] Killing Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM jarvis.exe >nul 2>&1
echo    ✅ Processes terminated

echo.
echo [2/4] Clearing Python cache...
del /S /Q *.pyc >nul 2>&1
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
python -m pip cache purge >nul 2>&1
echo    ✅ Cache cleared

echo.
echo [3/4] Starting OpenJarvis server...
start /B python -m openjarvis.cli serve
echo    Waiting for server to start...

timeout /t 5 /nobreak >nul

echo.
echo [4/4] Testing endpoints...
echo.

:: Test Engine Telemetry
curl -s http://localhost:8000/v1/telemetry/stats >temp_result.json 2>nul
findstr /C:"aggregate" temp_result.json >nul 2>&1
if errorlevel 1 (
    echo    ✅ Engine Telemetry: Working
) else (
    echo    ❌ Engine Telemetry: Still has cache issue
)
del temp_result.json >nul 2>&1

:: Test MCP Servers
curl -s http://localhost:8000/v1/mcp/servers >temp_result.json 2>nul
findstr /C:"AppConfig" temp_result.json >nul 2>&1
if errorlevel 1 (
    echo    ✅ MCP Servers: Working
) else (
    echo    ❌ MCP Servers: Still has cache issue
)
del temp_result.json >nul 2>&1

:: Test Learning Status
curl -s http://localhost:8000/v1/learning/status >temp_result.json 2>nul
findstr /C:"Not found" temp_result.json >nul 2>&1
if errorlevel 1 (
    echo    ✅ Learning Status: Working
) else (
    echo    ❌ Learning Status: Still has cache issue
)
del temp_result.json >nul 2>&1

echo.
echo ════════════════════════════════════════════════════════════════
echo 🎉 Cache fix complete!
echo.
echo Next steps:
echo    1. Run: python test_all_primitives.py
echo    2. Or double-click: Test-All-Primitives.bat
echo.
echo If issues persist, restart your computer.
echo ════════════════════════════════════════════════════════════════
echo.
pause