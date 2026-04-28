@echo off
:: Create Desktop Shortcuts for OpenJarvis Scripts (Simplified Version)
:: Creates shortcuts for batch files only (most reliable)

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║          Creating OpenJarvis Desktop Shortcuts               ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

echo Creating shortcuts...
echo.

:: Create shortcut for OpenJarvis Menu (Unified Launcher)
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\OpenJarvis.lnk'); $s.TargetPath = '%SCRIPT_DIR%OpenJarvis-Menu.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'OpenJarvis Unified Launcher - Choose GUI, Voice, or Terminal'; $s.Save()"
if errorlevel 1 (
    echo ❌ OpenJarvis shortcut failed
) else (
    echo ✅ OpenJarvis shortcut created
)

:: Create shortcut for OpenJarvis GUI
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\OpenJarvis GUI.lnk'); $s.TargetPath = '%SCRIPT_DIR%OpenJarvis-GUI.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'OpenJarvis Web Interface'; $s.Save()"
if errorlevel 1 (
    echo ❌ OpenJarvis GUI shortcut failed
) else (
    echo ✅ OpenJarvis GUI shortcut created
)

:: Create shortcut for Voice Mode v5
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\OpenJarvis Voice.lnk'); $s.TargetPath = '%SCRIPT_DIR%OpenJarvis-Voice.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'OpenJarvis Voice Mode v5 - Local VAD'; $s.Save()"
if errorlevel 1 (
    echo ❌ OpenJarvis Voice shortcut failed
) else (
    echo ✅ OpenJarvis Voice shortcut created
)

:: Create shortcut for Deepgram Voice Agent
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\OpenJarvis Deepgram Voice.lnk'); $s.TargetPath = '%SCRIPT_DIR%OpenJarvis-Deepgram-Voice.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'OpenJarvis Deepgram Voice - Continuous two-way voice'; $s.Save()"
if errorlevel 1 (
    echo ❌ OpenJarvis Deepgram Voice shortcut failed
) else (
    echo ✅ OpenJarvis Deepgram Voice shortcut created
)

:: Create shortcut for Test All Primitives
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Test All Primitives.lnk'); $s.TargetPath = '%SCRIPT_DIR%Test-All-Primitives.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Run comprehensive test suite for all five primitives'; $s.Save()"
if errorlevel 1 (
    echo ❌ Test All Primitives shortcut failed
) else (
    echo ✅ Test All Primitives shortcut created
)

:: Create shortcut for Fix Cache and Restart
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\Fix Cache and Restart.lnk'); $s.TargetPath = '%SCRIPT_DIR%Fix-Cache-and-Restart.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Clear Python cache and restart server'; $s.Save()"
if errorlevel 1 (
    echo ❌ Fix Cache and Restart shortcut failed
) else (
    echo ✅ Fix Cache and Restart shortcut created
)

:: Create shortcut for Python Test Script (create wrapper batch)
echo @echo off > "%SCRIPT_DIR%run_python_test.bat"
echo python "%SCRIPT_DIR%test_all_primitives.py" >> "%SCRIPT_DIR%run_python_test.bat"
echo pause >> "%SCRIPT_DIR%run_python_test.bat"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\OpenJarvis Test Suite.lnk'); $s.TargetPath = '%SCRIPT_DIR%run_python_test.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Run Python test script for all primitives'; $s.Save()"
if errorlevel 1 (
    echo ❌ OpenJarvis Test Suite shortcut failed
) else (
    echo ✅ OpenJarvis Test Suite shortcut created
)

:: Create shortcut for Python Cache Fix (create wrapper batch)
echo @echo off > "%SCRIPT_DIR%run_python_fix.bat"
echo python "%SCRIPT_DIR%fix_cache_and_restart.py" >> "%SCRIPT_DIR%run_python_fix.bat"
echo pause >> "%SCRIPT_DIR%run_python_fix.bat"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\OpenJarvis Cache Fix.lnk'); $s.TargetPath = '%SCRIPT_DIR%run_python_fix.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Clear cache and restart server (Python version)'; $s.Save()"
if errorlevel 1 (
    echo ❌ OpenJarvis Cache Fix shortcut failed
) else (
    echo ✅ OpenJarvis Cache Fix shortcut created
)

echo.
echo ════════════════════════════════════════════════════════════════
echo.
echo 🎉 Desktop shortcuts created successfully!
echo.
echo You can now double-click these shortcuts on your desktop:
echo.
echo    • OpenJarvis - Unified launcher (choose GUI, Voice, or Terminal)
echo    • OpenJarvis GUI - Web interface
echo    • OpenJarvis Voice - Local VAD-based voice control
echo    • OpenJarvis Deepgram Voice - Continuous two-way voice (Deepgram API)
echo    • Test All Primitives - Quick comprehensive test
echo    • Fix Cache and Restart - Fix cache issues
echo    • OpenJarvis Test Suite - Python version
echo    • OpenJarvis Cache Fix - Python version
echo.
echo ════════════════════════════════════════════════════════════════
echo.
pause