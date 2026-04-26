"""File manager plugin — list, create, delete, move, copy, rename, read, write, find files.

Mirrors MK37's file_controller.py with OpenJarvis plugin API.
All operations are sandboxed to the user's home directory for safety.

Usage examples:
  list files desktop
  list files downloads
  create file documents/todo.txt Hello world
  read file documents/todo.txt
  find file report.pdf
  disk usage
  organize desktop
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from openjarvis.plugins import plugin

_OS = platform.system()

# Safety root — only allow operations inside the home directory
_SAFE_ROOTS: list[Path] = [Path.home()]


def _is_safe(target: Path) -> bool:
    try:
        resolved = target.resolve()
        return any(
            resolved == r.resolve() or resolved.is_relative_to(r.resolve())
            for r in _SAFE_ROOTS
        )
    except Exception:
        return False


def _resolve(raw: str) -> Path:
    shortcuts = {
        "desktop": Path.home() / "Desktop",
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
        "pictures": Path.home() / "Pictures",
        "music": Path.home() / "Music",
        "videos": Path.home() / "Videos",
        "home": Path.home(),
    }
    lower = raw.strip().lower()
    if lower in shortcuts:
        return shortcuts[lower]
    return Path(raw).expanduser()


def _fmt_size(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b:.1f} TB"


# ── Core operations ───────────────────────────────────────────────────────────

def _list_files(path: str = "desktop") -> str:
    target = _resolve(path)
    if not _is_safe(target):
        return f"Access denied: {target}"
    if not target.exists():
        return f"Path not found: {target}"
    if not target.is_dir():
        return f"Not a directory: {target}"
    items = []
    for item in sorted(target.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            items.append(f"  {item.name}/")
        else:
            items.append(f"  {item.name} ({_fmt_size(item.stat().st_size)})")
    if not items:
        return f"{target.name}/ is empty."
    return f"Contents of {target.name}/ ({len(items)} items):\n" + "\n".join(items)


def _read_file(path: str, max_chars: int = 3000) -> str:
    target = _resolve(path)
    if not _is_safe(target):
        return f"Access denied: {target}"
    if not target.exists():
        return f"File not found: {target.name}"
    if not target.is_file():
        return f"Not a file: {target.name}"
    content = target.read_text(encoding="utf-8", errors="ignore")
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n[Truncated — {len(content)} total chars]"
    return content


def _find_files(name: str = "", ext: str = "", path: str = "home", max_results: int = 15) -> str:
    search_path = _resolve(path)
    if not _is_safe(search_path):
        return f"Access denied: {search_path}"
    results = []
    dir_count = 0
    for item in search_path.rglob("*"):
        if item.is_dir():
            dir_count += 1
            if dir_count > 300:
                break
            continue
        if ext and item.suffix.lower() != ext.lower():
            continue
        if name and name.lower() not in item.name.lower():
            continue
        results.append(f"  {item.name} ({_fmt_size(item.stat().st_size)}) — {item.parent}")
        if len(results) >= max_results:
            break
    if not results:
        return f"No files matching '{name or ext}' found in {search_path.name}/"
    return f"Found {len(results)} file(s):\n" + "\n".join(results)


def _disk_usage(path: str = "home") -> str:
    target = _resolve(path)
    try:
        usage = shutil.disk_usage(target)
        pct = usage.used / usage.total * 100
        return (
            f"Disk usage ({target}):\n"
            f"  Total : {_fmt_size(usage.total)}\n"
            f"  Used  : {_fmt_size(usage.used)} ({pct:.1f}%)\n"
            f"  Free  : {_fmt_size(usage.free)}"
        )
    except Exception as exc:
        return f"Could not get disk usage: {exc}"


# ── Plugins ───────────────────────────────────────────────────────────────────

@plugin("list files")
def list_files(jarvis, s):
    """List files in a directory. Usage: list files desktop"""
    path = s.strip() or "desktop"
    jarvis.say(_list_files(path))


@plugin("show files")
def show_files(jarvis, s):
    """Show files in a directory. Usage: show files downloads"""
    list_files(jarvis, s)


@plugin("read file")
def read_file_cmd(jarvis, s):
    """Read a file's contents. Usage: read file documents/notes.txt"""
    path = s.strip()
    if not path:
        jarvis.say("Please specify a file path. Example: read file documents/notes.txt")
        return
    jarvis.say(_read_file(path))


@plugin("find file")
def find_file(jarvis, s):
    """Find files by name. Usage: find file report.pdf"""
    name = s.strip()
    if not name:
        jarvis.say("What file name should I search for?")
        return
    # Check if it looks like an extension
    if name.startswith("."):
        jarvis.say(_find_files(ext=name))
    else:
        jarvis.say(_find_files(name=name))


@plugin("disk usage")
def disk_usage(jarvis, s):
    """Show disk usage. Usage: disk usage"""
    path = s.strip() or "home"
    jarvis.say(_disk_usage(path))


@plugin("disk space")
def disk_space(jarvis, s):
    """Show available disk space"""
    disk_usage(jarvis, s)


@plugin("create file")
def create_file_cmd(jarvis, s):
    """Create a new file. Usage: create file documents/hello.txt Hello world"""
    parts = s.strip().split(None, 1)
    if not parts:
        jarvis.say("Please specify a path. Example: create file documents/hello.txt")
        return
    path = _resolve(parts[0])
    content = parts[1] if len(parts) > 1 else ""
    if not _is_safe(path):
        jarvis.say(f"Access denied: {path}")
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        jarvis.say(f"Created file: {path.name}")
    except Exception as exc:
        jarvis.say(f"Could not create file: {exc}")


@plugin("delete file")
def delete_file_cmd(jarvis, s):
    """Move a file to Trash. Usage: delete file downloads/old.txt"""
    path_str = s.strip()
    if not path_str:
        jarvis.say("Please specify which file to delete.")
        return
    target = _resolve(path_str)
    if not _is_safe(target):
        jarvis.say(f"Access denied: {target}")
        return
    if not target.exists():
        jarvis.say(f"File not found: {target.name}")
        return
    try:
        import send2trash
        send2trash.send2trash(str(target))
        jarvis.say(f"Moved to Trash: {target.name}")
    except ImportError:
        jarvis.say("send2trash not installed. Run: pip install send2trash")
    except Exception as exc:
        jarvis.say(f"Could not delete: {exc}")


@plugin("rename file")
def rename_file_cmd(jarvis, s):
    """Rename a file. Usage: rename file old.txt new.txt"""
    parts = s.strip().split()
    if len(parts) < 2:
        jarvis.say("Usage: rename file <old_path> <new_name>")
        return
    src = _resolve(parts[0])
    new_name = parts[1]
    if not _is_safe(src):
        jarvis.say(f"Access denied: {src}")
        return
    if not src.exists():
        jarvis.say(f"File not found: {src.name}")
        return
    new_path = src.parent / new_name
    if new_path.exists():
        jarvis.say(f"A file named '{new_name}' already exists.")
        return
    try:
        src.rename(new_path)
        jarvis.say(f"Renamed {src.name} to {new_name}.")
    except Exception as exc:
        jarvis.say(f"Could not rename: {exc}")


@plugin("move file")
def move_file_cmd(jarvis, s):
    """Move a file. Usage: move file downloads/report.pdf documents"""
    parts = s.strip().split(None, 1)
    if len(parts) < 2:
        jarvis.say("Usage: move file <source> <destination>")
        return
    src = _resolve(parts[0])
    dst = _resolve(parts[1])
    if not _is_safe(src) or not _is_safe(dst):
        jarvis.say("Access denied.")
        return
    if not src.exists():
        jarvis.say(f"Source not found: {src.name}")
        return
    if dst.is_dir():
        dst = dst / src.name
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        jarvis.say(f"Moved {src.name} to {dst.parent.name}/")
    except Exception as exc:
        jarvis.say(f"Could not move: {exc}")
