"""Desktop manager plugin — wallpaper, organize, clean, list desktop.

Mirrors MK37's desktop.py action.

Usage:
  list desktop
  organize desktop
  clean desktop
  set wallpaper C:/Users/USER/Pictures/bg.jpg
  wallpaper from url https://example.com/bg.jpg
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

from openjarvis.plugins import plugin

_OS = platform.system()

_FILE_TYPE_MAP = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".odt"},
    "Videos": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "Music": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".cpp", ".java", ".cs", ".go", ".rs"},
    "Executables": {".exe", ".msi", ".bat", ".cmd", ".sh", ".appimage", ".deb"},
}
_SKIP_EXTS = {
    "Windows": {".lnk", ".url"},
    "Darwin": {".webloc"},
    "Linux": {".desktop"},
}


def _desktop() -> Path:
    if _OS == "Linux":
        xdg = os.environ.get("XDG_DESKTOP_DIR", "")
        if xdg and Path(xdg).exists():
            return Path(xdg)
    return Path.home() / "Desktop"


# ── Wallpaper ─────────────────────────────────────────────────────────────────

def _set_wallpaper(image_path: str) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        return f"Image not found: {image_path}"
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return f"Unsupported format: {path.suffix}. Use jpg, png, bmp, or webp."
    try:
        if _OS == "Windows":
            import ctypes
            # Convert webp/png to bmp if needed (Windows SetWallpaper works best with bmp)
            if path.suffix.lower() in {".webp", ".png"}:
                try:
                    from PIL import Image
                    bmp_path = Path(tempfile.mktemp(suffix=".bmp"))
                    Image.open(path).convert("RGB").save(bmp_path, "BMP")
                    path = bmp_path
                except ImportError:
                    pass
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
            return f"Wallpaper set to: {path.name}"
        elif _OS == "Darwin":
            script = f'tell application "System Events" to tell every desktop to set picture to POSIX file "{path}"'
            subprocess.run(["osascript", "-e", script], capture_output=True)
            return f"Wallpaper set to: {path.name}"
        else:
            de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            uri = f"file://{path}"
            if "gnome" in de or "unity" in de:
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri], capture_output=True)
                return f"Wallpaper set to: {path.name}"
            elif "kde" in de:
                subprocess.run(["qdbus", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
                                 f'var d=desktops();for(var i=0;i<d.length;i++){{d[i].wallpaperPlugin="org.kde.image";d[i].currentConfigGroup=["Wallpaper","org.kde.image","General"];d[i].writeConfig("Image","file://{path}");}}'], capture_output=True)
                return f"Wallpaper set to: {path.name}"
            else:
                r = subprocess.run(["feh", "--bg-scale", str(path)], capture_output=True)
                if r.returncode == 0:
                    return f"Wallpaper set to: {path.name}"
                return "Could not set wallpaper automatically. Try installing 'feh'."
    except Exception as exc:
        return f"Could not set wallpaper: {exc}"


def _wallpaper_from_url(url: str) -> str:
    try:
        suffix = Path(url.split("?")[0]).suffix or ".jpg"
        tmp = Path(tempfile.mktemp(suffix=suffix))
        req = urllib.request.Request(url, headers={"User-Agent": "OpenJarvis/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tmp.write_bytes(resp.read())
        result = _set_wallpaper(str(tmp))
        try:
            tmp.unlink()
        except Exception:
            pass
        return result
    except Exception as exc:
        return f"Could not download wallpaper: {exc}"


# ── Desktop list / organize / clean ───────────────────────────────────────────

def _list_desktop() -> str:
    desktop = _desktop()
    items = []
    for item in sorted(desktop.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            try:
                count = len(list(item.iterdir()))
            except PermissionError:
                count = "?"
            items.append(f"  {item.name}/ ({count} items)")
        else:
            size = item.stat().st_size
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
            items.append(f"  {item.name} ({size_str})")
    if not items:
        return "Your desktop is empty."
    return f"Desktop ({len(items)} items):\n" + "\n".join(items)


def _organize_desktop(mode: str = "by_type") -> str:
    desktop = _desktop()
    skip_exts = _SKIP_EXTS.get(_OS, set())
    moved, skipped = [], []
    for item in desktop.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        if item.suffix.lower() in skip_exts:
            continue
        if mode == "by_date":
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            folder_name = mtime.strftime("%Y-%m")
        else:
            ext = item.suffix.lower()
            folder_name = "Others"
            for folder, exts in _FILE_TYPE_MAP.items():
                if ext in exts:
                    folder_name = folder
                    break
        target_dir = desktop / folder_name
        target_dir.mkdir(exist_ok=True)
        new_path = target_dir / item.name
        if new_path.exists():
            skipped.append(item.name)
            continue
        shutil.move(str(item), str(new_path))
        moved.append(f"  {item.name} → {folder_name}/")

    result = f"Desktop organized ({mode}): {len(moved)} files moved."
    if moved:
        result += "\n" + "\n".join(moved[:8])
        if len(moved) > 8:
            result += f"\n  ...and {len(moved) - 8} more."
    if skipped:
        result += f"\n{len(skipped)} file(s) skipped (name conflict)."
    return result


def _clean_desktop() -> str:
    """Archive everything except shortcuts into a timestamped folder."""
    desktop = _desktop()
    skip_exts = _SKIP_EXTS.get(_OS, set())
    today = datetime.now().strftime("%Y-%m-%d")
    archive_dir = desktop / f"Desktop Archive {today}"
    moved = []
    for item in list(desktop.iterdir()):
        if item.is_dir() and item.name.startswith("Desktop Archive"):
            continue
        if item.name.startswith("."):
            continue
        if item.is_file() and item.suffix.lower() in skip_exts:
            continue
        archive_dir.mkdir(exist_ok=True)
        new_path = archive_dir / item.name
        if not new_path.exists():
            shutil.move(str(item), str(new_path))
            moved.append(item.name)
    if not moved:
        return "Desktop is already clean."
    return f"Cleaned desktop: {len(moved)} items archived to 'Desktop Archive {today}/'."


# ── Plugin commands ───────────────────────────────────────────────────────────

@plugin("list desktop")
def list_desktop_cmd(jarvis, s):
    """List items on the desktop"""
    jarvis.say(_list_desktop())


@plugin("show desktop files")
def show_desktop_files(jarvis, s):
    """Show files on the desktop"""
    jarvis.say(_list_desktop())


@plugin("organize desktop")
def organize_desktop_cmd(jarvis, s):
    """Organize desktop files into folders by type"""
    mode = "by_date" if "date" in s.lower() else "by_type"
    jarvis.say(_organize_desktop(mode))


@plugin("clean desktop")
def clean_desktop_cmd(jarvis, s):
    """Archive all desktop files into a timestamped folder"""
    jarvis.say(_clean_desktop())


@plugin("set wallpaper")
def set_wallpaper_cmd(jarvis, s):
    """Set desktop wallpaper. Usage: set wallpaper C:/path/to/image.jpg"""
    path = s.strip()
    if not path:
        jarvis.say("Please provide an image path or URL.")
        return
    if path.startswith("http"):
        jarvis.say(_wallpaper_from_url(path))
    else:
        jarvis.say(_set_wallpaper(path))


@plugin("wallpaper from url")
def wallpaper_from_url_cmd(jarvis, s):
    """Set wallpaper from a URL. Usage: wallpaper from url https://example.com/bg.jpg"""
    url = s.strip()
    if not url:
        jarvis.say("Please provide an image URL.")
        return
    jarvis.say(_wallpaper_from_url(url))


@plugin("change wallpaper")
def change_wallpaper(jarvis, s):
    """Change desktop wallpaper. Usage: change wallpaper /path/to/image.jpg"""
    set_wallpaper_cmd(jarvis, s)
