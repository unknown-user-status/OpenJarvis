"""App launcher plugin — open common applications and websites by name."""

import os
import sys
import subprocess
import webbrowser
from openjarvis.plugins import plugin

# Common Windows application paths / commands
_WIN_APPS: dict[str, str] = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "notepad": "notepad.exe",
    "notepad++": r"C:\Program Files\Notepad++\notepad++.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint": r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "spotify": r"C:\Users\USER\AppData\Roaming\Spotify\Spotify.exe",
    "discord": r"C:\Users\USER\AppData\Local\Discord\Update.exe",
    "vs code": r"C:\Users\USER\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vscode": r"C:\Users\USER\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\USER\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "paint 3d": "mspaint.exe",
    "snipping tool": "snippingtool.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
}

# Common website shortcuts
_WEBSITES: dict[str, str] = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://www.github.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "gmail": "https://mail.google.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "wikipedia": "https://www.wikipedia.org",
    "stackoverflow": "https://www.stackoverflow.com",
    "stack overflow": "https://www.stackoverflow.com",
    "chatgpt": "https://chat.openai.com",
    "openai": "https://www.openai.com",
}


def _launch_app(name: str) -> str:
    name_lower = name.lower().strip()

    # Check website shortcuts first
    if name_lower in _WEBSITES:
        url = _WEBSITES[name_lower]
        webbrowser.open(url)
        return f"Opening {name} in your browser."

    # Try to open as a website if it looks like a domain
    if "." in name_lower and " " not in name_lower:
        url = name_lower if name_lower.startswith("http") else f"https://{name_lower}"
        webbrowser.open(url)
        return f"Opening {url} in your browser."

    # Try application map
    app_path = _WIN_APPS.get(name_lower)
    if app_path:
        try:
            if app_path.startswith("ms-"):
                os.startfile(app_path)
            else:
                subprocess.Popen([app_path], shell=True)
            return f"Launching {name}."
        except Exception as exc:
            return f"Failed to launch {name}: {exc}"

    # Fallback: try subprocess
    try:
        subprocess.Popen([name_lower], shell=True)
        return f"Attempting to launch {name}."
    except Exception as exc:
        return f"I couldn't find or launch '{name}'. ({exc})"


@plugin("open")
def open_app(jarvis, s):
    """Open an application or website. Usage: open Chrome"""
    target = s.strip()
    if not target:
        jarvis.say("What would you like me to open?")
        return
    result = _launch_app(target)
    jarvis.say(result)


@plugin("launch")
def launch_app(jarvis, s):
    """Launch an application. Usage: launch Notepad"""
    open_app(jarvis, s)


@plugin("start app")
def start_app(jarvis, s):
    """Start an application. Usage: start app Chrome"""
    open_app(jarvis, s)
