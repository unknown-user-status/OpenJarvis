# OpenJarvis Five-Primitive Architecture Test - PowerShell Script
# This script provides advanced testing with automatic server management

param(
    [switch]$StartServer,
    [switch]$StopServer,
    [switch]$Watch,
    [int]$Interval = 30
)

# Color scheme
$Colors = @{
    Red = "Red"
    Green = "Green"
    Yellow = "Yellow"
    Blue = "Blue"
    White = "White"
}

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Colors[$Color]
}

function Show-Header {
    Write-ColorOutput "╔══════════════════════════════════════════════════════════════╗" "Blue"
    Write-ColorOutput "║          OpenJarvis Five-Primitive Architecture Test         ║" "Blue"
    Write-ColorOutput "║                 PowerShell Advanced Test Suite              ║" "Blue"
    Write-ColorOutput "╚══════════════════════════════════════════════════════════════╝" "Blue"
}

function Test-ServerHealth {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        return $true
    }
    catch {
        return $false
    }
}

function Start-OpenJarvisServer {
    Write-ColorOutput "🚀 Starting OpenJarvis server..." "Yellow"
    
    # Check if already running
    if (Test-ServerHealth) {
        Write-ColorOutput "✅ Server is already running!" "Green"
        return $true
    }
    
    # Start server in background
    $serverJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD
        python -m openjarvis.cli serve
    }
    
    # Wait for server to start
    $timeout = 30
    $timer = 0
    while ($timer -lt $timeout) {
        if (Test-ServerHealth) {
            Write-ColorOutput "✅ Server started successfully!" "Green"
            return $true
        }
        Start-Sleep -Seconds 1
        $timer++
        Write-Host "." -NoNewline
    }
    
    Write-ColorOutput "`n❌ Server failed to start within $timeout seconds!" "Red"
    return $false
}

function Stop-OpenJarvisServer {
    Write-ColorOutput "🛑 Stopping OpenJarvis server..." "Yellow"
    
    # Find and kill Python processes running openjarvis
    $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
        $_.CommandLine -like "*openjarvis*" -or $_.CommandLine -like "*jarvis*" 
    }
    
    if ($processes) {
        $processes | Stop-Process -Force
        Write-ColorOutput "✅ Server stopped!" "Green"
    } else {
        Write-ColorOutput "ℹ️  No OpenJarvis server processes found." "White"
    }
}

function Run-ComprehensiveTest {
    Write-ColorOutput "`n🧪 Running comprehensive test suite..." "Blue"
    Write-ColorOutput "═══════════════════════════════════════════════════════════════" "Blue"
    
    # Run the Python test script
    $testResult = python test_all_primitives.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "`n✅ Test suite completed!" "Green"
    } else {
        Write-ColorOutput "`n❌ Test suite failed!" "Red"
    }
    
    # Show results summary if file exists
    if (Test-Path "test_results.json") {
        Write-ColorOutput "`n📊 Test Results Summary:" "Yellow"
        $results = Get-Content "test_results.json" | ConvertFrom-Json
        Write-Host "   Passed: $($results.summary.passed)" -ForegroundColor Green
        Write-Host "   Failed: $($results.summary.failed)" -ForegroundColor Red
        Write-Host "   Total: $($results.summary.total)" -ForegroundColor Blue
    }
}

function Watch-Tests {
    Write-ColorOutput "`n👁️  Watching mode enabled - Running tests every $Interval seconds..." "Yellow"
    Write-ColorOutput "Press Ctrl+C to stop watching" "White"
    
    try {
        while ($true) {
            Clear-Host
            Show-Header
            Write-ColorOutput "🕐 Test run at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "White"
            Write-ColorOutput "═══════════════════════════════════════════════════════════════" "Blue"
            
            Run-ComprehensiveTest
            
            Write-ColorOutput "`n⏳ Next test in $Interval seconds..." "Yellow"
            Start-Sleep -Seconds $Interval
        }
    }
    catch [System.Management.Automation.HaltCommandException] {
        Write-ColorOutput "`n👋 Watching mode stopped." "White"
    }
}

# Main execution
Show-Header

if ($StopServer) {
    Stop-OpenJarvisServer
    exit
}

if ($StartServer -or -not (Test-ServerHealth)) {
    if (-not (Start-OpenJarvisServer)) {
        Write-ColorOutput "❌ Cannot start server. Exiting." "Red"
        exit 1
    }
}

if ($Watch) {
    Watch-Tests
} else {
    Run-ComprehensiveTest
}

Write-ColorOutput "`n🎉 All done! Check test_results.json for detailed results." "Green"