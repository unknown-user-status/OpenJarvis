"""Computer settings plugin — volume, brightness, window management, keyboard shortcuts.

Mirrors MK37's computer_settings.py action.

Usage:
  volume up
  volume down
  mute
  set volume 50
  brightness up
  brightness down
  minimize window
  maximize window
  fullscreen
  switch window
  close tab
  new tab
  next tab
  zoom in
  zoom out
  scroll down
  scroll up
  copy
  paste
  undo
  redo
  lock screen
  screenshot
"""

from __future__ import annotations

import platform
import subprocess
import time

from openjarvis.plugins import plugin

_OS = platform.system()

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False


def _require_pyautogui() -> str | None:
    if not _PYAUTOGUI:
        return "pyautogui is not installed. Run: pip install pyautogui"
    return None


# ── Volume ────────────────────────────────────────────────────────────────────

def _volume_up():
    if _OS == "Windows":
        for _ in range(5):
            pyautogui.press("volumeup")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        "set volume output volume (output volume of (get volume settings) + 10)"],
                       capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"], capture_output=True)


def _volume_down():
    if _OS == "Windows":
        for _ in range(5):
            pyautogui.press("volumedown")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        "set volume output volume (output volume of (get volume settings) - 10)"],
                       capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], capture_output=True)


def _volume_mute():
    if _OS == "Windows":
        pyautogui.press("volumemute")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", "set volume with output muted"], capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], capture_output=True)


def _volume_set(value: int):
    value = max(0, min(100, value))
    if _OS == "Windows":
        try:
            import math
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(interface, POINTER(IAudioEndpointVolume))
            vol_db = -65.25 if value == 0 else max(-65.25, 20 * math.log10(value / 100))
            vol.SetMasterVolumeLevel(vol_db, None)
            return
        except Exception:
            pass
        # Fallback: approximate via key presses
        pyautogui.press("volumemute")
        pyautogui.press("volumemute")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e", f"set volume output volume {value}"], capture_output=True)
    else:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{value}%"], capture_output=True)


# ── Brightness ────────────────────────────────────────────────────────────────

def _brightness_up():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 144'], capture_output=True)
    elif _OS == "Linux":
        if subprocess.run(["which", "brightnessctl"], capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", "+10%"], capture_output=True)
    else:
        try:
            subprocess.run(["powershell", "-Command",
                            "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                            ".WmiSetBrightness(1,[math]::Min(100,(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness+10))"],
                           capture_output=True, timeout=5)
        except Exception:
            pass


def _brightness_down():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 145'], capture_output=True)
    elif _OS == "Linux":
        if subprocess.run(["which", "brightnessctl"], capture_output=True).returncode == 0:
            subprocess.run(["brightnessctl", "set", "10%-"], capture_output=True)
    else:
        try:
            subprocess.run(["powershell", "-Command",
                            "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                            ".WmiSetBrightness(1,[math]::Max(0,(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness-10))"],
                           capture_output=True, timeout=5)
        except Exception:
            pass


# ── Window management ─────────────────────────────────────────────────────────

def _minimize():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "m")
    else:
        pyautogui.hotkey("win", "down")


def _maximize():
    if _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        'tell application "System Events" to keystroke "f" using {control down, command down}'],
                       capture_output=True)
    elif _OS == "Windows":
        pyautogui.hotkey("win", "up")
    else:
        try:
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"], capture_output=True)
        except Exception:
            pyautogui.hotkey("super", "up")


def _fullscreen():
    if _OS == "Darwin":
        pyautogui.hotkey("ctrl", "command", "f")
    else:
        pyautogui.press("f11")


def _switch_window():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "tab")
    else:
        pyautogui.hotkey("alt", "tab")


def _show_desktop():
    if _OS == "Darwin":
        pyautogui.hotkey("fn", "f11")
    elif _OS == "Windows":
        pyautogui.hotkey("win", "d")
    else:
        pyautogui.hotkey("super", "d")


def _lock_screen():
    if _OS == "Windows":
        pyautogui.hotkey("win", "l")
    elif _OS == "Darwin":
        subprocess.run(["osascript", "-e",
                        'tell application "System Events" to keystroke "q" using {command down, control down}'],
                       capture_output=True)
    else:
        subprocess.run(["loginctl", "lock-session"], capture_output=True)


# ── Browser / tab ─────────────────────────────────────────────────────────────

def _close_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "w")
    else:
        pyautogui.hotkey("ctrl", "w")


def _new_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "t")
    else:
        pyautogui.hotkey("ctrl", "t")


def _next_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "bracketright")
    else:
        pyautogui.hotkey("ctrl", "tab")


def _prev_tab():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "bracketleft")
    else:
        pyautogui.hotkey("ctrl", "shift", "tab")


def _zoom_in():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "equal")
    else:
        pyautogui.hotkey("ctrl", "equal")


def _zoom_out():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "minus")
    else:
        pyautogui.hotkey("ctrl", "minus")


def _zoom_reset():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "0")
    else:
        pyautogui.hotkey("ctrl", "0")


def _scroll_up(amount: int = 500):
    pyautogui.scroll(amount)


def _scroll_down(amount: int = 500):
    pyautogui.scroll(-amount)


def _copy():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "c")
    else:
        pyautogui.hotkey("ctrl", "c")


def _paste():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "v")
    else:
        pyautogui.hotkey("ctrl", "v")


def _undo():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "z")
    else:
        pyautogui.hotkey("ctrl", "z")


def _redo():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "shift", "z")
    else:
        pyautogui.hotkey("ctrl", "y")


def _select_all():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "a")
    else:
        pyautogui.hotkey("ctrl", "a")


def _save():
    if _OS == "Darwin":
        pyautogui.hotkey("command", "s")
    else:
        pyautogui.hotkey("ctrl", "s")


def _type_text(text: str):
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        _paste()
    else:
        pyautogui.write(text, interval=0.03)


def _take_screenshot() -> str:
    try:
        import pathlib
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = pathlib.Path.home() / "Desktop" / f"screenshot_{ts}.png"
        import mss, mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=str(path))
        return f"Screenshot saved: {path.name}"
    except ImportError:
        try:
            import pyautogui as _pag
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path_str = str(pathlib.Path.home() / "Desktop" / f"screenshot_{ts}.png")
            _pag.screenshot(path_str)
            return f"Screenshot saved: screenshot_{ts}.png"
        except Exception as exc:
            return f"Screenshot failed: {exc}"
    except Exception as exc:
        return f"Screenshot failed: {exc}"


# ── Plugin registrations ──────────────────────────────────────────────────────

@plugin("volume up")
def volume_up(jarvis, s):
    """Increase system volume"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _volume_up()
    jarvis.say("Volume increased.")


@plugin("volume down")
def volume_down(jarvis, s):
    """Decrease system volume"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _volume_down()
    jarvis.say("Volume decreased.")


@plugin("mute")
def mute(jarvis, s):
    """Mute or unmute the system volume"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _volume_mute()
    jarvis.say("Volume toggled.")


@plugin("set volume")
def set_volume(jarvis, s):
    """Set volume to a specific level. Usage: set volume 50"""
    try:
        val = int(s.strip())
    except ValueError:
        jarvis.say("Please provide a number between 0 and 100.")
        return
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _volume_set(val)
    jarvis.say(f"Volume set to {val}%.")


@plugin("brightness up")
def brightness_up(jarvis, s):
    """Increase screen brightness"""
    _brightness_up()
    jarvis.say("Brightness increased.")


@plugin("brightness down")
def brightness_down(jarvis, s):
    """Decrease screen brightness"""
    _brightness_down()
    jarvis.say("Brightness decreased.")


@plugin("minimize window")
def minimize_window(jarvis, s):
    """Minimize the current window"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _minimize()
    jarvis.say("Window minimized.")


@plugin("maximize window")
def maximize_window(jarvis, s):
    """Maximize the current window"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _maximize()
    jarvis.say("Window maximized.")


@plugin("fullscreen")
def fullscreen(jarvis, s):
    """Toggle fullscreen mode"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _fullscreen()
    jarvis.say("Toggled fullscreen.")


@plugin("switch window")
def switch_window(jarvis, s):
    """Switch to the next window (Alt+Tab)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _switch_window()
    jarvis.say("Switching window.")


@plugin("show desktop")
def show_desktop_cmd(jarvis, s):
    """Show the desktop (Win+D)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _show_desktop()
    jarvis.say("Showing desktop.")


@plugin("lock screen")
def lock_screen(jarvis, s):
    """Lock the screen"""
    _lock_screen()
    jarvis.say("Screen locked.")


@plugin("close tab")
def close_tab(jarvis, s):
    """Close the current browser tab"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _close_tab()
    jarvis.say("Tab closed.")


@plugin("new tab")
def new_tab(jarvis, s):
    """Open a new browser tab"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _new_tab()
    jarvis.say("New tab opened.")


@plugin("next tab")
def next_tab(jarvis, s):
    """Switch to the next browser tab"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _next_tab()
    jarvis.say("Switched to next tab.")


@plugin("zoom in")
def zoom_in(jarvis, s):
    """Zoom in (Ctrl/Cmd +)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _zoom_in()
    jarvis.say("Zoomed in.")


@plugin("zoom out")
def zoom_out(jarvis, s):
    """Zoom out (Ctrl/Cmd -)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _zoom_out()
    jarvis.say("Zoomed out.")


@plugin("scroll up")
def scroll_up_cmd(jarvis, s):
    """Scroll up"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _scroll_up()
    jarvis.say("Scrolled up.")


@plugin("scroll down")
def scroll_down_cmd(jarvis, s):
    """Scroll down"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _scroll_down()
    jarvis.say("Scrolled down.")


@plugin("copy")
def copy_cmd(jarvis, s):
    """Copy selected text (Ctrl/Cmd+C)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _copy()
    jarvis.say("Copied.")


@plugin("paste")
def paste_cmd(jarvis, s):
    """Paste clipboard (Ctrl/Cmd+V)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _paste()
    jarvis.say("Pasted.")


@plugin("undo")
def undo_cmd(jarvis, s):
    """Undo last action (Ctrl/Cmd+Z)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _undo()
    jarvis.say("Undone.")


@plugin("redo")
def redo_cmd(jarvis, s):
    """Redo last action (Ctrl+Y / Cmd+Shift+Z)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _redo()
    jarvis.say("Redone.")


@plugin("select all")
def select_all(jarvis, s):
    """Select all (Ctrl/Cmd+A)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _select_all()
    jarvis.say("Selected all.")


@plugin("save file")
def save_file_cmd(jarvis, s):
    """Save current file (Ctrl/Cmd+S)"""
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _save()
    jarvis.say("Saved.")


@plugin("type text")
def type_text_cmd(jarvis, s):
    """Type text. Usage: type text Hello, world!"""
    text = s.strip()
    if not text:
        jarvis.say("What should I type?")
        return
    err = _require_pyautogui()
    if err:
        jarvis.say(err)
        return
    _type_text(text)
    jarvis.say(f"Typed: {text[:40]}")


@plugin("take screenshot")
def take_screenshot(jarvis, s):
    """Take a screenshot and save to Desktop"""
    result = _take_screenshot()
    jarvis.say(result)


@plugin("capture screen")
def capture_screen(jarvis, s):
    """Capture the screen and save to Desktop"""
    take_screenshot(jarvis, s)
