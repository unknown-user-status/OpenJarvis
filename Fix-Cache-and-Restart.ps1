# OpenJarvis Cache Clear and Server Restart - PowerShell Script
# Fixes cache issues for Engine, Tools & Memory, and Learning primitives

param(
    [switch]$Force,
    [switch]$NoRestart
)

# Color scheme
$Colors = @{
    Red = "Red"
    Green = "Green"
    Yellow = "Yellow"
    Blue = "Blue"
    Cyan = "Cyan"
    White = "White"
}

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White",
        [string]$Icon = "ℹ️"
    )
    Write-Host "$Icon $Message" -ForegroundColor $Colors[$Color]
}

function Show-Header {
    Clear-Host
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║         🔧 OpenJarvis Cache Clear & Server Restart            ║" -ForegroundColor Cyan  
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Stop-Processes {
    Write-ColorOutput "Stopping Python processes..." "Yellow" "🛑"
    
    # Stop Python processes
    $pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
    if ($pythonProcesses) {
        $pythonProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-ColorOutput "Stopped Python processes" "Green" "✅"
    }
    
    # Stop jarvis processes
    $jarvisProcesses = Get-Process jarvis -ErrorAction SilentlyContinue
    if ($jarvisProcesses) {
        $jarvisProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-ColorOutput "Stopped Jarvis processes" "Green" "✅"
    }
    
    Start-Sleep -Seconds 2
}

function Clear-Cache {
    Write-ColorOutput "Clearing Python cache..." "Yellow" "🧹"
    
    $cacheCount = 0
    
    # Clear __pycache__ directories
    Get-ChildItem -Path . -Recurse -Directory -Name "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
        $cachePath = Join-Path (Get-Location) $_
        Remove-Item -Path $cachePath -Recurse -Force -ErrorAction SilentlyContinue
        $cacheCount++
    }
    
    # Clear .pyc files
    $pycFiles = Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
    $pycCount = $pycFiles.Count
    $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    
    # Clear pip cache
    try {
        python -m pip cache purge >$null 2>&1
        Write-ColorOutput "Cleared pip cache" "Green" "✅"
    } catch {
        Write-ColorOutput "Could not clear pip cache" "Yellow" "⚠️"
    }
    
    Write-ColorOutput "Removed $cacheCount cache directories and $pycCount .pyc files" "Green" "✅"
}

function Start-Server {
    if ($NoRestart) {
        Write-ColorOutput "Skipping server restart (NoRestart specified)" "Yellow" "⏭️"
        return $true
    }
    
    Write-ColorOutput "Starting OpenJarvis server..." "Yellow" "🚀"
    
    try {
        # Start server in new window
        Start-Process python -ArgumentList "-m", "openjarvis.cli", "serve" -WindowStyle Minimized
        
        # Wait for server to start
        Write-ColorOutput "Waiting for server to start..." "Blue" "⏳"
        
        for ($i = 1; $i -le 30; $i++) {
            try {
                $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2
                Write-ColorOutput "Server started successfully!" "Green" "✅"
                return $true
            } catch {
                Write-Host "." -NoNewline
                Start-Sleep -Seconds 1
            }
        }
        
        Write-Host "`n"
        Write-ColorOutput "Server may not have started properly" "Yellow" "⚠️"
        return $false
        
    } catch {
        Write-ColorOutput "Error starting server: $($_.Exception.Message)" "Red" "❌"
        return $false
    }
}

function Test-Endpoints {
    Write-ColorOutput "Testing previously failing endpoints..." "Blue" "🧪"
    
    $endpoints = @{
        "Engine Telemetry" = "/v1/telemetry/stats"
        "MCP Servers" = "/v1/mcp/servers"  
        "Learning Status" = "/v1/learning/status"
    }
    
    $results = @{}
    
    foreach ($name in $endpoints.Keys) {
        $endpoint = $endpoints[$name]
        
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000$endpoint" -TimeoutSec 5
            
            if ($response.error -or $response.detail -eq "Not found") {
                Write-ColorOutput "$name`: Still failing" "Red" "❌"
                $results[$name] = "FAIL"
            } else {
                Write-ColorOutput "$name`: Working!" "Green" "✅"
                $results[$name] = "PASS"
            }
        } catch {
            Write-ColorOutput "$name`: $($_.Exception.Message)" "Red" "❌"
            $results[$name] = "FAIL"
        }
    }
    
    return $results
}

function Show-Summary {
    param($Results)
    
    Write-Host "`n" + "═"*60
    Write-ColorOutput "SUMMARY" "Cyan" "📊"
    Write-Host "═"*60
    
    $passed = ($Results.Values | Where-Object { $_ -eq "PASS" }).Count
    $total = $Results.Count
    
    foreach ($name in $Results.Keys) {
        $status = $Results[$name]
        $icon = if ($status -eq "PASS") { "✅" } else { "❌" }
        Write-Host "$icon $name`: $status"
    }
    
    Write-Host "`nResults: $passed/$total endpoints now working"
    
    if ($passed -eq $total) {
        Write-ColorOutput "🎉 All cache issues fixed!" "Green" "✅"
    } else {
        Write-ColorOutput "⚠️ Some issues persist. Try restarting your computer." "Yellow" "⚠️"
    }
    
    Write-Host "`nNext steps:"
    Write-Host "1. Run: python test_all_primitives.py"
    Write-Host "2. Or double-click: Test-All-Primitives.bat"
    Write-Host "`n" + "═"*60
}

# Main execution
Show-Header

if (-not $Force) {
    Write-ColorOutput "This will stop all Python processes and clear caches." "Yellow" "⚠️"
    $confirm = Read-Host "Continue? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-ColorOutput "Operation cancelled." "Yellow" "⏹️"
        exit
    }
}

# Step 1: Stop processes
Stop-Processes

# Step 2: Clear cache  
Clear-Cache

# Step 3: Start server
if (Start-Server) {
    # Step 4: Test endpoints
    $results = Test-Endpoints
    
    # Step 5: Show summary
    Show-Summary -Results $results
} else {
    Write-ColorOutput "Failed to start server. Please check manually." "Red" "❌"
}

Write-Host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")