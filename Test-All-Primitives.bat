@echo off
:: OpenJarvis Five-Primitive Architecture Test - One-Click Test
:: This script tests all implemented primitives with a single command

echo.
echo ========================================
echo   OpenJarvis Five-Primitive Test
echo ========================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python first.
    pause
    exit /b 1
)

:: Check if server is running
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ❌ Server not running! Starting server...
    echo.
    echo Starting OpenJarvis server...
    start /B python -m openjarvis.cli serve
    echo Waiting for server to start...
    timeout /t 5 /nobreak >nul
)

:: Run the comprehensive test
echo.
echo 🧪 Running comprehensive test suite...
echo.
python test_all_primitives.py

echo.
echo ========================================
echo   Test completed!
echo ========================================
echo.
echo Check test_results.json for detailed results.
echo.
pause