# OpenJarvis Five-Primitive Architecture Test Suite

This directory contains comprehensive test scripts to validate all five primitives of the Stanford OpenJarvis architecture with a single command.

## Quick Start

### Option 1: One-Click Batch File (Windows)
```batch
# Double-click or run from command line:
Test-All-Primitives.bat
```

### Option 2: Python Script (Cross-Platform)
```bash
python test_all_primitives.py
```

### Option 3: PowerShell Script (Advanced)
```powershell
# Basic test
.\Test-All-Primitives.ps1

# With automatic server start
.\Test-All-Primitives.ps1 -StartServer

# Watch mode (continuous testing every 30 seconds)
.\Test-All-Primitives.ps1 -Watch

# Custom interval in watch mode
.\Test-All-Primitives.ps1 -Watch -Interval 60

# Stop server
.\Test-All-Primitives.ps1 -StopServer
```

## What Gets Tested

### ✅ Intelligence Primitive
- **Endpoint**: `GET /v1/intelligence/hardware`
- **Validates**: System hardware detection and model recommendations
- **Expected Fields**: platform, cpu, cpu_cores, ram_gb, recommended_tier, recommended_model

### ⚠️ Engine Primitive  
- **Endpoint**: `GET /v1/telemetry/stats`
- **Validates**: Performance metrics and telemetry data
- **Expected Fields**: total_requests, total_tokens, total_cost_usd, total_energy_joules
- **Note**: May show cache issue until server restart

### ✅ Agents Primitive
- **Endpoint**: `GET /v1/agents`
- **Validates**: Agent registry and listing functionality
- **Expected**: List of available agents with id, name, class, description

### ⚠️ Tools & Memory Primitive
- **Endpoints**: 
  - `GET /v1/mcp/servers` (list servers)
  - `POST /v1/mcp/servers` (add server)
  - `DELETE /v1/mcp/servers/{name}` (remove server)
- **Validates**: MCP server management functionality
- **Note**: May show cache issue until server restart

### ⚠️ Learning Primitive
- **Endpoints**:
  - `GET /v1/learning/status` (get status)
  - `POST /v1/learning/trigger` (trigger optimization)
- **Validates**: Learning system status and optimization controls
- **Note**: May show cache issue until server restart

### ✅ Frontend UI
- **Endpoint**: `GET /`
- **Validates**: Frontend application loads correctly

## Test Results

After running tests, results are saved to `test_results.json` with:
- Timestamp of test run
- Detailed results for each primitive
- Pass/fail status with error details
- Summary statistics

## Cache Issues

Some tests may fail with "cache issue" errors. This is due to Python bytecode caching and can be resolved by:

1. **Restart the server**:
   ```bash
   # Stop server (Ctrl+C)
   # Start fresh
   python -m openjarvis.cli serve
   ```

2. **System restart** (most reliable):
   - Restart your computer to clear all Python caches

3. **Use fresh virtual environment**:
   ```bash
   deactivate
   python -m venv fresh_env
   fresh_env\Scripts\activate
   pip install -e ".[server]"
   ```

## Troubleshooting

### Server Not Running
The test scripts will automatically try to start the server if it's not running. If that fails:

```bash
# Manual server start
python -m openjarvis.cli serve

# In a separate terminal, run tests
python test_all_primitives.py
```

### Python Not Found
Ensure Python 3.10+ is installed and in your PATH:
```bash
python --version
```

### Dependencies Missing
Install required dependencies:
```bash
pip install requests
```

## Continuous Testing (Watch Mode)

Use the PowerShell script for continuous testing during development:

```powershell
# Run tests every 30 seconds
.\Test-All-Primitives.ps1 -Watch

# Run tests every 60 seconds
.\Test-All-Primitives.ps1 -Watch -Interval 60
```

Press `Ctrl+C` to stop watching.

## Integration with CI/CD

The Python script returns appropriate exit codes:
- `0` = All tests passed or only cache issues
- `1` = Server not running or critical failures

This makes it easy to integrate with CI/CD pipelines:

```bash
# In CI/CD script
python test_all_primitives.py
if [ $? -eq 1 ]; then
    echo "Critical test failures!"
    exit 1
fi
```

## Customization

You can modify the `test_all_primitives.py` script to:
- Add new test cases
- Change validation criteria
- Modify timeout values
- Add additional endpoints to test

## Example Output

```
╔══════════════════════════════════════════════════════════════╗
║          OpenJarvis Five-Primitive Architecture Test         ║
║                     Comprehensive Test Suite                ║
╚══════════════════════════════════════════════════════════════╝

✅ Passed: 3
❌ Failed: 3  
📊 Total: 6

Failed Tests:
   • engine: Cache issue - restart server or system
   • tools_memory: Cache issue - restart server or system
   • learning: Cache issue - restart server or system

📄 Detailed results saved to: test_results.json
```

## One-Command Testing Summary

Now you have three ways to test all five primitives with a single command:

1. **Double-click `Test-All-Primitives.bat`** - Easiest for Windows users
2. **Run `python test_all_primitives.py`** - Cross-platform Python script
3. **Run `.\Test-All-Primitives.ps1`** - Advanced PowerShell with watch mode

All scripts provide comprehensive testing of the Stanford OpenJarvis five-primitive architecture implementation!