# 🚀 OpenJarvis One-Click Testing & Cache Fix Solution

Complete solution for testing the Stanford OpenJarvis five-primitive architecture and fixing cache issues with a single click.

## 🎯 What You Have Now

### Desktop Shortcuts (Created on Your Desktop)
1. **Test All Primitives** - Quick comprehensive test
2. **Fix Cache and Restart** - Fix cache issues  
3. **OpenJarvis Test Suite** - Python version
4. **OpenJarvis Cache Fix** - Python version

### Scripts in OpenJarvis Directory
- `Test-All-Primitives.bat` - Windows batch test
- `Fix-Cache-and-Restart.bat` - Windows batch cache fix
- `test_all_primitives.py` - Python comprehensive test
- `fix_cache_and_restart.py` - Python cache fix
- `Test-All-Primitives.ps1` - PowerShell advanced test
- `Fix-Cache-and-Restart.ps1` - PowerShell cache fix
- `Create-Desktop-Shortcuts.bat` - Recreate shortcuts

## 🎮 How to Use

### **Easiest Method - Double-Click Desktop Shortcuts**

#### 🧪 Test All Primitives
```
Double-click: "Test All Primitives" on your desktop
```
- Tests all 5 primitives + frontend
- Shows colored results
- Saves detailed JSON report

#### 🔧 Fix Cache and Restart
```
Double-click: "Fix Cache and Restart" on your desktop
```
- Kills Python processes
- Clears all Python caches
- Restarts server
- Tests previously failing endpoints

### **Alternative Methods**

#### Method 1: Batch Files (Windows)
```batch
# Run from command line or double-click
Test-All-Primitives.bat
Fix-Cache-and-Restart.bat
```

#### Method 2: Python Scripts (Cross-Platform)
```bash
python test_all_primitives.py
python fix_cache_and_restart.py
```

#### Method 3: PowerShell Scripts (Advanced)
```powershell
# Basic test
.\Test-All-Primitives.ps1

# Watch mode (continuous testing)
.\Test-All-Primitives.ps1 -Watch -Interval 30

# Cache fix
.\Fix-Cache-and-Restart.ps1

# Cache fix without restart
.\Fix-Cache-and-Restart.ps1 -NoRestart

# Force without confirmation
.\Fix-Cache-and-Restart.ps1 -Force
```

## 📊 What Gets Tested

### ✅ Intelligence Primitive
- **Endpoint**: `GET /v1/intelligence/hardware`
- **Tests**: Hardware detection, CPU, RAM, GPU, model recommendations
- **Expected**: System specs and recommended model tier

### ⚠️ Engine Primitive  
- **Endpoint**: `GET /v1/telemetry/stats`
- **Tests**: Performance metrics, energy, cost, tokens
- **Issue**: May show cache error until cache fix is run

### ✅ Agents Primitive
- **Endpoint**: `GET /v1/agents`
- **Tests**: Agent registry, listing all available agents
- **Expected**: List of 12+ agents with details

### ⚠️ Tools & Memory Primitive
- **Endpoints**: MCP server management (GET/POST/DELETE)
- **Tests**: External tool integration via MCP
- **Issue**: May show cache error until cache fix is run

### ⚠️ Learning Primitive
- **Endpoints**: Learning status and trigger
- **Tests**: Learning system status and optimization controls
- **Issue**: May show cache error until cache fix is run

### ✅ Frontend UI
- **Endpoint**: `GET /`
- **Tests**: Frontend application loading
- **Expected**: HTML page with OpenJarvis title

## 🔧 Cache Issues Explained

### Why Cache Issues Occur
Python caches compiled bytecode (.pyc files) to speed up subsequent imports. When you modify Python code, sometimes the cached bytecode isn't invalidated properly, causing the server to run old code.

### Symptoms of Cache Issues
- Error: `'TelemetryAggregator' object has no attribute 'aggregate'`
- Error: `cannot import name 'AppConfig' from 'openjarvis.core.config'`
- Error: `"detail": "Not found"` for new endpoints
- Code changes not reflected in running server

### How the Cache Fix Works
1. **Kill Processes**: Stops all Python and Jarvis processes
2. **Clear Cache**: Removes all .pyc files and __pycache__ directories
3. **Clear Pip Cache**: Purges pip package cache
4. **Restart Server**: Starts fresh server instance
5. **Test Endpoints**: Validates that cache issues are resolved

## 🎯 Recommended Workflow

### First Time Setup
1. **Create Shortcuts** (if needed):
   ```batch
   Create-Desktop-Shortcuts.bat
   ```

### Daily Testing
1. **Run Full Test**:
   ```
   Double-click: "Test All Primitives"
   ```

### When Cache Issues Appear
1. **Run Cache Fix**:
   ```
   Double-click: "Fix Cache and Restart"
   ```
2. **Wait 10 seconds** for server to start
3. **Run Full Test** again to verify fixes

### During Development
1. **Use Watch Mode** (PowerShell):
   ```powershell
   .\Test-All-Primitives.ps1 -Watch -Interval 30
   ```
2. Tests run automatically every 30 seconds
3. Press Ctrl+C to stop watching

## 📁 Test Results

### JSON Output
All tests save results to `test_results.json`:
```json
{
  "timestamp": "2026-04-27T23:57:36.929469",
  "results": {
    "intelligence": {"status": "PASS", "data": {...}},
    "engine": {"status": "FAIL", "cache_issue": true},
    "agents": {"status": "PASS", "count": 12},
    "tools_memory": {"status": "FAIL", "cache_issue": true},
    "learning": {"status": "FAIL", "cache_issue": true},
    "frontend": {"status": "PASS"}
  },
  "summary": {"passed": 3, "failed": 3, "total": 6}
}
```

### Console Output
- Colored pass/fail indicators
- Detailed error messages
- Progress indicators
- Summary statistics

## 🛠️ Troubleshooting

### Server Not Starting
If the cache fix can't start the server:
```bash
# Manual server start
python -m openjarvis.cli serve

# Then run tests in another terminal
python test_all_primitives.py
```

### Shortcuts Not Working
If desktop shortcuts don't work:
1. Re-create shortcuts:
   ```batch
   Create-Desktop-Shortcuts.bat
   ```
2. Or run scripts directly from the OpenJarvis directory

### Persistent Cache Issues
If cache issues persist after running the fix:
1. **Restart your computer** (most reliable)
2. **Use fresh virtual environment**:
   ```bash
   deactivate
   python -m venv fresh_env
   fresh_env\Scripts\activate
   pip install -e ".[server]"
   ```

### Python Not Found
Ensure Python 3.10+ is installed:
```bash
python --version
```

## 🎨 Advanced Features

### PowerShell Watch Mode
```powershell
# Continuous testing every 30 seconds
.\Test-All-Primitives.ps1 -Watch

# Custom interval (60 seconds)
.\Test-All-Primitives.ps1 -Watch -Interval 60
```

### PowerShell Cache Fix Options
```powershell
# Fix without confirmation
.\Fix-Cache-and-Restart.ps1 -Force

# Clear cache but don't restart server
.\Fix-Cache-and-Restart.ps1 -NoRestart

# Stop server only
.\Fix-Cache-and-Restart.ps1 -StopServer
```

## 📝 Integration with CI/CD

The Python script returns proper exit codes:
- `0` = All tests passed or only cache issues
- `1` = Server not running or critical failures

```bash
# In CI/CD pipeline
python test_all_primitives.py
if [ $? -eq 1 ]; then
    echo "Critical test failures!"
    exit 1
fi
```

## 🎉 Quick Reference

| Task | Method |
|------|--------|
| **Test All Primitives** | Double-click "Test All Primitives" |
| **Fix Cache Issues** | Double-click "Fix Cache and Restart" |
| **Continuous Testing** | `.\Test-All-Primitives.ps1 -Watch` |
| **Recreate Shortcuts** | `Create-Desktop-Shortcuts.bat` |
| **View Test Results** | Check `test_results.json` |

## 📚 Additional Documentation

- **TEST_README.md** - Detailed test documentation
- **AGENTS.md** - Project workflow rules
- **README.md** - Main project documentation

---

## 🎯 Summary

You now have a complete one-click testing solution:

1. **4 Desktop Shortcuts** - Instant access from your desktop
2. **6 Script Files** - Multiple methods for different needs
3. **Cache Fix Solution** - Automatically resolves Python cache issues
4. **Comprehensive Testing** - Tests all 5 primitives + frontend
5. **Detailed Reporting** - JSON results + colored console output

**No more manual testing or cache issues!** Just double-click and go! 🚀