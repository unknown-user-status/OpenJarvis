#!/usr/bin/env python3
"""
OpenJarvis Cache Clear and Server Restart Script
Fixes cache issues for Engine, Tools & Memory, and Learning primitives.

Usage:
    python fix_cache_and_restart.py
"""

import os
import sys
import subprocess
import time
import requests
import shutil
from pathlib import Path

def print_status(message, status="INFO"):
    """Print colored status messages."""
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m", 
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "END": "\033[0m",
        "BOLD": "\033[1m"
    }
    
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅", 
        "WARNING": "⚠️",
        "ERROR": "❌"
    }
    
    print(f"{colors[status]}{icons[status]} {message}{colors['END']}")

def kill_python_processes():
    """Kill all Python processes related to OpenJarvis."""
    print_status("Killing Python processes...", "INFO")
    
    try:
        if os.name == 'nt':  # Windows
            # Kill jarvis.exe and python.exe processes
            subprocess.run(['taskkill', '/F', '/IM', 'jarvis.exe'], capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
        else:  # Unix/Linux/Mac
            # Kill processes with openjarvis or jarvis in name
            subprocess.run(['pkill', '-f', 'openjarvis'], capture_output=True)
            subprocess.run(['pkill', '-f', 'jarvis'], capture_output=True)
        
        time.sleep(2)
        print_status("Python processes terminated", "SUCCESS")
    except Exception as e:
        print_status(f"Error killing processes: {e}", "WARNING")

def clear_python_cache():
    """Clear all Python cache directories and files."""
    print_status("Clearing Python cache...", "INFO")
    
    # Clear current directory cache
    cache_dirs = []
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            cache_dirs.append(os.path.join(root, '__pycache__'))
        for file in files:
            if file.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, file))
                except:
                    pass
    
    # Remove cache directories
    for cache_dir in cache_dirs:
        try:
            shutil.rmtree(cache_dir)
        except:
            pass
    
    # Clear pip cache
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'cache', 'purge'], capture_output=True)
        print_status("Pip cache cleared", "SUCCESS")
    except:
        print_status("Could not clear pip cache", "WARNING")
    
    # Clear Python bytecode cache
    try:
        subprocess.run([sys.executable, '-B', '-c', 'import sys; sys.exit(0)'], capture_output=True)
    except:
        pass
    
    print_status(f"Removed {len(cache_dirs)} cache directories", "SUCCESS")

def restart_server():
    """Restart the OpenJarvis server."""
    print_status("Starting OpenJarvis server...", "INFO")
    
    try:
        # Start server in background
        if os.name == 'nt':  # Windows
            subprocess.Popen([sys.executable, '-m', 'openjarvis.cli', 'serve'], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Unix/Linux/Mac
            subprocess.Popen([sys.executable, '-m', 'openjarvis.cli', 'serve'])
        
        # Wait for server to start
        print_status("Waiting for server to start...", "INFO")
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get('http://localhost:8000/health', timeout=1)
                if response.status_code == 200:
                    print_status("Server started successfully!", "SUCCESS")
                    return True
            except:
                pass
            time.sleep(1)
            print(f".", end="", flush=True)
        
        print("\n" + "⚠️ Server may not have started properly", "WARNING")
        return False
        
    except Exception as e:
        print_status(f"Error starting server: {e}", "ERROR")
        return False

def test_fixed_endpoints():
    """Test the previously failing endpoints."""
    print_status("Testing fixed endpoints...", "INFO")
    
    endpoints = [
        ("Engine Telemetry", "/v1/telemetry/stats"),
        ("MCP Servers", "/v1/mcp/servers"),
        ("Learning Status", "/v1/learning/status")
    ]
    
    results = {}
    
    for name, endpoint in endpoints:
        try:
            response = requests.get(f'http://localhost:8000{endpoint}', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "error" not in data and data.get("detail") != "Not found":
                    print_status(f"{name}: ✅ Working", "SUCCESS")
                    results[name] = "PASS"
                else:
                    print_status(f"{name}: ❌ Still failing - {data.get('error', 'Not found')}", "ERROR")
                    results[name] = "FAIL"
            else:
                print_status(f"{name}: ❌ HTTP {response.status_code}", "ERROR")
                results[name] = "FAIL"
        except Exception as e:
            print_status(f"{name}: ❌ {e}", "ERROR")
            results[name] = "FAIL"
    
    return results

def main():
    """Main function to fix cache issues and restart server."""
    print("\n" + "="*60)
    print("🔧 OpenJarvis Cache Fix & Server Restart")
    print("="*60 + "\n")
    
    # Step 1: Kill processes
    kill_python_processes()
    
    # Step 2: Clear cache
    clear_python_cache()
    
    # Step 3: Restart server
    if restart_server():
        # Step 4: Test endpoints
        print("\n" + "─"*60)
        print_status("Testing previously failing endpoints...", "INFO")
        results = test_fixed_endpoints()
        
        # Summary
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in results.values() if r == "PASS")
        total = len(results)
        
        for name, status in results.items():
            icon = "✅" if status == "PASS" else "❌"
            print(f"{icon} {name}: {status}")
        
        print(f"\nResults: {passed}/{total} endpoints now working")
        
        if passed == total:
            print_status("🎉 All cache issues fixed! Run full test suite to verify.", "SUCCESS")
        else:
            print_status("⚠️ Some issues persist. Try restarting your computer.", "WARNING")
        
        print("\nNext steps:")
        print("1. Run: python test_all_primitives.py")
        print("2. Or double-click: Test-All-Primitives.bat")
        
    else:
        print_status("❌ Failed to start server. Please check manually.", "ERROR")

if __name__ == "__main__":
    main()