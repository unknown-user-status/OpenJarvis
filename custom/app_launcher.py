"""App launcher plugin — open applications and websites by name.

Upgraded to MK37-style cross-platform smart launcher:
- Tries known aliases first
- Falls back to Start Menu search (Windows) / Spotlight (macOS) / PATH (Linux)
- Opens websites in the default browser

Usage:
  open Chrome
  launch Spotify
  open github.com
  open notepad
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import time
import webbrowser

from openjarvis.plugins import plugin

_OS = platform.system()

# Cross-platform app aliases: {alias: {OS: command/app_name}}
_APP_ALIASES: dict[str, dict[str, str]] = {
    "chrome": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    "google chrome": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    "firefox": {"Windows": "firefox", "Darwin": "Firefox", "Linux": "firefox"},
    "edge": {"Windows": "msedge", "Darwin": "Microsoft Edge", "Linux": "microsoft-edge"},
    "brave": {"Windows": "brave", "Darwin": "Brave Browser", "Linux": "brave-browser"},
    "opera": {"Windows": "opera", "Darwin": "Opera", "Linux": "opera"},
    "safari": {"Windows": "msedge", "Darwin": "Safari", "Linux": "firefox"},
    "whatsapp": {"Windows": "WhatsApp", "Darwin": "WhatsApp", "Linux": "whatsapp"},
    "telegram": {"Windows": "Telegram", "Darwin": "Telegram", "Linux": "telegram"},
    "discord": {"Windows": "Discord", "Darwin": "Discord", "Linux": "discord"},
    "slack": {"Windows": "Slack", "Darwin": "Slack", "Linux": "slack"},
    "zoom": {"Windows": "Zoom", "Darwin": "zoom.us", "Linux": "zoom"},
    "teams": {"Windows": "msteams", "Darwin": "Microsoft Teams", "Linux": "teams"},
    "skype": {"Windows": "skype", "Darwin": "Skype", "Linux": "skype"},
    "signal": {"Windows": "signal", "Darwin": "Signal", "Linux": "signal"},
    "spotify": {"Windows": "Spotify", "Darwin": "Spotify", "Linux": "spotify"},
    "vlc": {"Windows": "vlc", "Darwin": "VLC", "Linux": "vlc"},
    "netflix": {"Windows": "Netflix", "Darwin": "Netflix", "Linux": "firefox"},
    "vscode": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "visual studio code": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "code": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "vs code": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "terminal": {"Windows": "wt", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    "cmd": {"Windows": "cmd.exe", "Darwin": "Terminal", "Linux": "bash"},
    "command prompt": {"Windows": "cmd.exe", "Darwin": "Terminal", "Linux": "bash"},
    "powershell": {"Windows": "powershell.exe", "Darwin": "Terminal", "Linux": "bash"},
    "notepad": {"Windows": "notepad.exe", "Darwin": "TextEdit", "Linux": "gedit"},
    "explorer": {"Windows": "explorer.exe", "Darwin": "Finder", "Linux": "nautilus"},
    "file explorer": {"Windows": "explorer.exe", "Darwin": "Finder", "Linux": "nautilus"},
    "finder": {"Windows": "explorer.exe", "Darwin": "Finder", "Linux": "nautilus"},
    "task manager": {"Windows": "taskmgr.exe", "Darwin": "Activity Monitor", "Linux": "gnome-system-monitor"},
    "settings": {"Windows": "ms-settings:", "Darwin": "System Preferences", "Linux": "gnome-control-center"},
    "calculator": {"Windows": "calc.exe", "Darwin": "Calculator", "Linux": "gnome-calculator"},
    "calc": {"Windows": "calc.exe", "Darwin": "Calculator", "Linux": "gnome-calculator"},
    "paint": {"Windows": "mspaint.exe", "Darwin": "Preview", "Linux": "gimp"},
    "word": {"Windows": "winword", "Darwin": "Microsoft Word", "Linux": "libreoffice --writer"},
    "excel": {"Windows": "excel", "Darwin": "Microsoft Excel", "Linux": "libreoffice --calc"},
    "powerpoint": {"Windows": "powerpnt", "Darwin": "Microsoft PowerPoint", "Linux": "libreoffice --impress"},
    "steam": {"Windows": "steam", "Darwin": "Steam", "Linux": "steam"},
    "epic games": {"Windows": "EpicGamesLauncher", "Darwin": "Epic Games Launcher", "Linux": "legendary"},
    "notion": {"Windows": "Notion", "Darwin": "Notion", "Linux": "notion"},
    "obsidian": {"Windows": "Obsidian", "Darwin": "Obsidian", "Linux": "obsidian"},
    "figma": {"Windows": "Figma", "Darwin": "Figma", "Linux": "figma"},
    "blender": {"Windows": "blender", "Darwin": "Blender", "Linux": "blender"},
    "postman": {"Windows": "Postman", "Darwin": "Postman", "Linux": "postman"},
    "instagram": {"Windows": "Instagram", "Darwin": "Instagram", "Linux": "firefox"},
    "tiktok": {"Windows": "TikTok", "Darwin": "TikTok", "Linux": "firefox"},
    "capcut": {"Windows": "CapCut", "Darwin": "CapCut", "Linux": "capcut"},
    "snipping tool": {"Windows": "snippingtool.exe", "Darwin": "Screenshot", "Linux": "gnome-screenshot"},
    "windows terminal": {"Windows": "wt", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    "control panel": {"Windows": "control.exe", "Darwin": "System Preferences", "Linux": "gnome-control-center"},
}

_WEBSITE_SHORTCUTS: dict[str, str] = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://www.github.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "facebook": "https://www.facebook.com",
    "instagram web": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "gmail": "https://mail.google.com",
    "amazon": "https://www.amazon.com",
    "netflix web": "https://www.netflix.com",
    "wikipedia web": "https://www.wikipedia.org",
    "stackoverflow": "https://www.stackoverflow.com",
    "chatgpt": "https://chat.openai.com",
    "openai": "https://www.openai.com",
}


def _normalize(raw: str) -> str:
    key = raw.lower().strip()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(_OS, raw)
    for alias, os_map in _APP_ALIASES.items():
        if alias in key or key in alias:
            return os_map.get(_OS, raw)
    return raw


def _launch_windows(app_name: str) -> bool:
    if shutil.which(app_name) or shutil.which(app_name.split(".")[0]):
        try:
            subprocess.Popen(app_name, shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            return True
        except Exception:
            pass
    if ":" in app_name:
        try:
            subprocess.Popen(f"start {app_name}", shell=True)
            time.sleep(1.0)
            return True
        except Exception:
            pass
    # Start Menu search via Windows key
    try:
        import pyautogui
        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.7)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.9)
        pyautogui.press("enter")
        time.sleep(2.5)
        return True
    except Exception:
        pass
    return False


def _launch_macos(app_name: str) -> bool:
    try:
        r = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=8)
        if r.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass
    binary = shutil.which(app_name)
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except Exception:
            pass
    # Spotlight fallback
    try:
        import pyautogui
        pyautogui.hotkey("command", "space")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception:
        pass
    return False


def _launch_linux(app_name: str) -> bool:
    binary = (
        shutil.which(app_name)
        or shutil.which(app_name.lower())
        or shutil.which(app_name.lower().replace(" ", "-"))
    )
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except Exception:
            pass
    for desk in [app_name.lower(), app_name.lower().replace(" ", "-")]:
        try:
            r = subprocess.run(["gtk-launch", desk], capture_output=True, timeout=5)
            if r.returncode == 0:
                return True
        except Exception:
            pass
    return False


_LAUNCHERS = {"Windows": _launch_windows, "Darwin": _launch_macos, "Linux": _launch_linux}


def _launch_app(name: str) -> str:
    lower = name.lower().strip()

    # Website shortcut
    if lower in _WEBSITE_SHORTCUTS:
        webbrowser.open(_WEBSITE_SHORTCUTS[lower])
        return f"Opening {name} in your browser."

    # Looks like a domain
    if "." in lower and " " not in lower:
        url = lower if lower.startswith("http") else f"https://{lower}"
        webbrowser.open(url)
        return f"Opening {url} in your browser."

    launcher = _LAUNCHERS.get(_OS)
    if not launcher:
        return f"Unsupported OS: {_OS}"

    normalized = _normalize(name)
    if launcher(normalized):
        return f"Launched {name}."
    if normalized.lower() != lower and launcher(name):
        return f"Launched {name}."
    return (
        f"Could not confirm that {name} launched. "
        "It may still be loading, or it might not be installed."
    )


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
