#!/usr/bin/env python3
"""
OpenJarvis Five-Primitive Architecture Test Script
Tests all implemented primitives with a single command.

Usage:
    python test_all_primitives.py

Primitives tested:
1. Intelligence - Hardware detection and model recommendations
2. Engine - Telemetry stats and performance metrics
3. Agents - Agent listing and selection
4. Tools & Memory - MCP server management
5. Learning - Learning system status and triggers
"""

import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, List
import subprocess
import requests

# Configuration
BASE_URL = "http://localhost:8000"
TEST_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "results": {},
    "summary": {"passed": 0, "failed": 0, "total": 0}
}

# ANSI color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text:^60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*60}{Colors.END}")

def print_test(name: str, status: str, details: str = ""):
    """Print a test result."""
    if status == "PASS":
        icon = "✅"
        color = Colors.GREEN
    elif status == "FAIL":
        icon = "❌"
        color = Colors.RED
    else:
        icon = "⚠️"
        color = Colors.YELLOW
    
    print(f"\n{color}{icon} {name}{Colors.END}")
    if details:
        print(f"   {details}")

def test_endpoint(name: str, endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Test an API endpoint and return the response."""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"response": response.text}
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
    
    except requests.exceptions.ConnectionError:
        return {"error": "Connection refused - server not running"}
    except requests.exceptions.Timeout:
        return {"error": "Request timeout"}
    except Exception as e:
        return {"error": str(e)}

def test_intelligence_primitive():
    """Test the Intelligence primitive."""
    print_header("INTELLIGENCE PRIMITIVE TEST")
    
    # Test hardware detection
    result = test_endpoint("Hardware Detection", "/v1/intelligence/hardware")
    
    if "error" in result:
        print_test("Hardware Detection", "FAIL", result["error"])
        TEST_RESULTS["results"]["intelligence"] = {"status": "FAIL", "error": result["error"]}
    else:
        # Validate required fields
        required_fields = ["platform", "cpu", "cpu_cores", "ram_gb", "recommended_tier", "recommended_model"]
        missing = [field for field in required_fields if field not in result]
        
        if missing:
            print_test("Hardware Detection", "FAIL", f"Missing fields: {missing}")
            TEST_RESULTS["results"]["intelligence"] = {"status": "FAIL", "missing_fields": missing}
        else:
            details = f"Platform: {result.get('platform')}, CPU Cores: {result.get('cpu_cores')}, RAM: {result.get('ram_gb')}GB, Recommended: {result.get('recommended_model')}"
            print_test("Hardware Detection", "PASS", details)
            TEST_RESULTS["results"]["intelligence"] = {"status": "PASS", "data": result}

def test_engine_primitive():
    """Test the Engine primitive."""
    print_header("ENGINE PRIMITIVE TEST")
    
    # Test telemetry stats
    result = test_endpoint("Telemetry Stats", "/v1/telemetry/stats")
    
    if "error" in result:
        if "aggregate" in result["error"]:
            print_test("Telemetry Stats", "FAIL", "Cache issue - needs server restart")
            TEST_RESULTS["results"]["engine"] = {"status": "FAIL", "cache_issue": True}
        else:
            print_test("Telemetry Stats", "FAIL", result["error"])
            TEST_RESULTS["results"]["engine"] = {"status": "FAIL", "error": result["error"]}
    else:
        # Validate expected fields
        expected_fields = ["total_requests", "total_tokens", "total_cost_usd"]
        missing = [field for field in expected_fields if field not in result]
        
        if missing:
            print_test("Telemetry Stats", "FAIL", f"Missing fields: {missing}")
            TEST_RESULTS["results"]["engine"] = {"status": "FAIL", "missing_fields": missing}
        else:
            details = f"Requests: {result.get('total_requests')}, Tokens: {result.get('total_tokens')}, Cost: ${result.get('total_cost_usd')}"
            print_test("Telemetry Stats", "PASS", details)
            TEST_RESULTS["results"]["engine"] = {"status": "PASS", "data": result}

def test_agents_primitive():
    """Test the Agents primitive."""
    print_header("AGENTS PRIMITIVE TEST")
    
    # Test agents list
    result = test_endpoint("Agents List", "/v1/agents")
    
    if "error" in result:
        print_test("Agents List", "FAIL", result["error"])
        TEST_RESULTS["results"]["agents"] = {"status": "FAIL", "error": result["error"]}
    else:
        agents = result.get("agents", [])
        if not agents:
            print_test("Agents List", "FAIL", "No agents returned")
            TEST_RESULTS["results"]["agents"] = {"status": "FAIL", "no_agents": True}
        else:
            # Count agent types
            agent_types = {}
            for agent in agents:
                class_name = agent.get("class", "Unknown")
                agent_types[class_name] = agent_types.get(class_name, 0) + 1
            
            details = f"Found {len(agents)} agents: {', '.join([f'{count} {cls}' for cls, count in list(agent_types.items())[:3]])}..."
            print_test("Agents List", "PASS", details)
            TEST_RESULTS["results"]["agents"] = {"status": "PASS", "count": len(agents), "types": agent_types}

def test_tools_memory_primitive():
    """Test the Tools & Memory primitive."""
    print_header("TOOLS & MEMORY PRIMITIVE TEST")
    
    # Test MCP servers list
    result = test_endpoint("MCP Servers", "/v1/mcp/servers")
    
    if "error" in result:
        if "AppConfig" in result["error"]:
            print_test("MCP Servers", "FAIL", "Cache issue - needs server restart")
            TEST_RESULTS["results"]["tools_memory"] = {"status": "FAIL", "cache_issue": True}
        else:
            print_test("MCP Servers", "FAIL", result["error"])
            TEST_RESULTS["results"]["tools_memory"] = {"status": "FAIL", "error": result["error"]}
    else:
        servers = result.get("servers", [])
        if servers is None:
            servers = []
        
        details = f"Found {len(servers)} MCP servers configured"
        print_test("MCP Servers", "PASS", details)
        TEST_RESULTS["results"]["tools_memory"] = {"status": "PASS", "count": len(servers)}
        
        # Test adding a test MCP server (optional)
        print("\n📝 Testing MCP server addition...")
        test_server = {
            "name": "test-server",
            "command": "echo",
            "args": ["test"]
        }
        add_result = test_endpoint("Add MCP Server", "/v1/mcp/servers", "POST", test_server)
        
        if "error" in add_result:
            print_test("Add MCP Server", "FAIL", add_result["error"])
        else:
            print_test("Add MCP Server", "PASS", "Test server added successfully")
            
            # Clean up - delete the test server
            delete_result = test_endpoint("Delete MCP Server", "/v1/mcp/servers/test-server", "DELETE")
            if "error" in delete_result:
                print_test("Delete MCP Server", "FAIL", delete_result["error"])
            else:
                print_test("Delete MCP Server", "PASS", "Test server cleaned up")

def test_learning_primitive():
    """Test the Learning primitive."""
    print_header("LEARNING PRIMITIVE TEST")
    
    # Test learning status
    result = test_endpoint("Learning Status", "/v1/learning/status")
    
    if "error" in result or result.get("detail") == "Not found":
        print_test("Learning Status", "FAIL", "Endpoint not found - needs server restart")
        TEST_RESULTS["results"]["learning"] = {"status": "FAIL", "cache_issue": True}
    else:
        # Validate expected fields
        expected_fields = ["enabled", "policy"]
        missing = [field for field in expected_fields if field not in result]
        
        if missing:
            print_test("Learning Status", "FAIL", f"Missing fields: {missing}")
            TEST_RESULTS["results"]["learning"] = {"status": "FAIL", "missing_fields": missing}
        else:
            details = f"Enabled: {result.get('enabled')}, Policy: {result.get('policy')}"
            print_test("Learning Status", "PASS", details)
            TEST_RESULTS["results"]["learning"] = {"status": "PASS", "data": result}
        
        # Test learning trigger
        print("\n📝 Testing learning trigger...")
        trigger_result = test_endpoint("Learning Trigger", "/v1/learning/trigger", "POST")
        
        if "error" in trigger_result:
            print_test("Learning Trigger", "FAIL", trigger_result["error"])
        else:
            success = trigger_result.get("success", False)
            if success:
                print_test("Learning Trigger", "PASS", "Learning cycle triggered successfully")
            else:
                print_test("Learning Trigger", "FAIL", trigger_result.get("error", "Unknown error"))

def test_frontend():
    """Test the frontend UI."""
    print_header("FRONTEND UI TEST")
    
    # Test main page
    result = test_endpoint("Frontend Main Page", "/")
    
    if "error" in result:
        print_test("Frontend Main Page", "FAIL", result["error"])
        TEST_RESULTS["results"]["frontend"] = {"status": "FAIL", "error": result["error"]}
    else:
        # Check for HTML content
        if "OpenJarvis" in str(result):
            print_test("Frontend Main Page", "PASS", "Frontend loads correctly")
            TEST_RESULTS["results"]["frontend"] = {"status": "PASS"}
        else:
            print_test("Frontend Main Page", "FAIL", "Invalid HTML content")
            TEST_RESULTS["results"]["frontend"] = {"status": "FAIL", "invalid_html": True}

def check_server_health():
    """Check if the server is running."""
    print_header("SERVER HEALTH CHECK")
    
    result = test_endpoint("Health Check", "/health")
    
    if "error" in result:
        print_test("Server Health", "FAIL", result["error"])
        print(f"\n{Colors.RED}❌ Server is not running!{Colors.END}")
        print(f"Please start the server with: {Colors.YELLOW}python -m openjarvis.cli serve{Colors.END}")
        return False
    else:
        print_test("Server Health", "PASS", "Server is running")
        return True

def generate_summary():
    """Generate a test summary."""
    print_header("TEST SUMMARY")
    
    # Count results
    passed = sum(1 for r in TEST_RESULTS["results"].values() if r["status"] == "PASS")
    failed = sum(1 for r in TEST_RESULTS["results"].values() if r["status"] == "FAIL")
    total = len(TEST_RESULTS["results"])
    
    TEST_RESULTS["summary"] = {"passed": passed, "failed": failed, "total": total}
    
    # Print summary
    print(f"\n{Colors.BOLD}Test Results:{Colors.END}")
    print(f"   {Colors.GREEN}✅ Passed: {passed}{Colors.END}")
    print(f"   {Colors.RED}❌ Failed: {failed}{Colors.END}")
    print(f"   {Colors.BLUE}📊 Total: {total}{Colors.END}")
    
    # Print details for failed tests
    failed_tests = [name for name, result in TEST_RESULTS["results"].items() if result["status"] == "FAIL"]
    if failed_tests:
        print(f"\n{Colors.YELLOW}Failed Tests:{Colors.END}")
        for test in failed_tests:
            result = TEST_RESULTS["results"][test]
            if result.get("cache_issue"):
                print(f"   • {test}: Cache issue - restart server or system")
            else:
                print(f"   • {test}: {result.get('error', 'Unknown error')}")
    
    # Save results to file
    with open("test_results.json", "w") as f:
        json.dump(TEST_RESULTS, f, indent=2)
    
    print(f"\n{Colors.BLUE}📄 Detailed results saved to: test_results.json{Colors.END}")
    
    # Overall status
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.END}")
    elif failed <= 2 and any(r.get("cache_issue") for r in TEST_RESULTS["results"].values()):
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  MOST TESTS PASSED (Cache issues detected){Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED{Colors.END}")

def main():
    """Main test function."""
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          OpenJarvis Five-Primitive Architecture Test         ║")
    print("║                     Comprehensive Test Suite                ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    # Check server health first
    if not check_server_health():
        sys.exit(1)
    
    # Run all tests
    test_intelligence_primitive()
    test_engine_primitive()
    test_agents_primitive()
    test_tools_memory_primitive()
    test_learning_primitive()
    test_frontend()
    
    # Generate summary
    generate_summary()

if __name__ == "__main__":
    main()