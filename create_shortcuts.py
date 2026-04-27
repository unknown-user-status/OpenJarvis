# OpenJarvis Desktop Shortcuts Creation Script
# Creates desktop shortcuts for all OpenJarvis test and fix scripts

import os
import sys
import shutil
from pathlib import Path

def create_shortcut(target_path, shortcut_path, description="", working_dir=""):
    """Create a desktop shortcut on Windows."""
    try:
        import win32com.client
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = working_dir or str(Path(target_path).parent)
        shortcut.Description = description
        shortcut.save()
        
        return True
    except ImportError:
        print("win32com not available. Please install: pip install pywin32")
        return False
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False

def get_desktop_path():
    """Get the desktop path."""
    return os.path.join(os.path.expanduser("~"), "Desktop")

def main():
    """Create all desktop shortcuts."""
    
    script_dir = Path(__file__).parent
    desktop = Path(get_desktop_path())
    
    scripts = [
        {
            "name": "Test All Primitives",
            "target": script_dir / "Test-All-Primitives.bat",
            "description": "Run comprehensive test suite for all five primitives"
        },
        {
            "name": "Fix Cache and Restart", 
            "target": script_dir / "Fix-Cache-and-Restart.bat",
            "description": "Clear Python cache and restart server to fix cache issues"
        },
        {
            "name": "OpenJarvis Test Suite",
            "target": sys.executable,
            "args": [str(script_dir / "test_all_primitives.py")],
            "description": "Run Python test script for all primitives"
        },
        {
            "name": "OpenJarvis Cache Fix",
            "target": sys.executable,
            "args": [str(script_dir / "fix_cache_and_restart.py")],
            "description": "Clear cache and restart server (Python version)"
        }
    ]
    
    print("Creating OpenJarvis desktop shortcuts...")
    print("="*60)
    
    created = 0
    failed = 0
    
    for script in scripts:
        shortcut_name = f"{script['name']}.lnk"
        shortcut_path = desktop / shortcut_name
        
        if "args" in script:
            # For Python scripts with arguments, we need a different approach
            # Create a temporary batch file
            batch_content = f'@echo off\n"{sys.executable}" {" ".join(script["args"])}\n'
            batch_path = script_dir / f"{script['name']}.bat"
            
            with open(batch_path, 'w') as f:
                f.write(batch_content)
            
            if create_shortcut(str(batch_path), str(shortcut_path), script['description'], str(script_dir)):
                print(f"✅ Created: {shortcut_name}")
                created += 1
            else:
                print(f"❌ Failed: {shortcut_name}")
                failed += 1
        else:
            if create_shortcut(str(script['target']), str(shortcut_path), script['description'], str(script_dir)):
                print(f"✅ Created: {shortcut_name}")
                created += 1
            else:
                print(f"❌ Failed: {shortcut_name}")
                failed += 1
    
    print("="*60)
    print(f"Created: {created} shortcuts")
    print(f"Failed: {failed} shortcuts")
    
    if created > 0:
        print("\n🎉 Shortcuts created on your desktop!")
        print("You can now double-click them to run the scripts.")

if __name__ == "__main__":
    main()