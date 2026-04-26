"""Reminder plugin — set timed reminders using Windows Task Scheduler (or 'at' on Linux/Mac).

Usage:
  remind me to call dentist on 2026-05-01 at 09:00
  set a reminder for 2026-04-28 14:30 buy groceries
  reminder 2026-04-30 18:00 team meeting
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openjarvis.plugins import plugin

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"
_SCRIPTS_DIR = Path.home() / ".openjarvis" / "reminders"


def _scripts_dir() -> Path:
    _SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    return _SCRIPTS_DIR


def _sanitise(text: str, max_len: int = 200) -> str:
    return (
        text.replace("\\", "")
        .replace('"', "")
        .replace("'", "")
        .replace("\n", " ")
        .replace("\r", "")
        .strip()
    )[:max_len]


def _write_notify_script(task_name: str, message: str) -> Path:
    script_path = _scripts_dir() / f"{task_name}.py"
    msg_literal = json.dumps(message)

    if _OS == "Windows":
        notify_block = f"""
message = {msg_literal}
notified = False
try:
    from plyer import notification
    notification.notify(title="OpenJarvis Reminder", message=message, timeout=15)
    notified = True
except Exception:
    pass
if not notified:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "OpenJarvis Reminder", 0x40)
    except Exception:
        pass
try:
    import winsound
    for freq in [800, 1000, 1200]:
        winsound.Beep(freq, 180)
    import time; time.sleep(0.08)
except Exception:
    pass
"""
    elif _OS == "Darwin":
        notify_block = f"""
message = {msg_literal}
try:
    from plyer import notification
    notification.notify(title="OpenJarvis Reminder", message=message, timeout=15)
except Exception:
    import subprocess
    script = 'display notification "{{}}" with title "OpenJarvis Reminder"'.format(
        message.replace('"', '')
    )
    subprocess.run(["osascript", "-e", script], check=False)
"""
    else:
        notify_block = f"""
message = {msg_literal}
try:
    from plyer import notification
    notification.notify(title="OpenJarvis Reminder", message=message, timeout=15)
except Exception:
    import subprocess
    subprocess.run(
        ["notify-send", "--urgency=normal", "--expire-time=15000",
         "OpenJarvis Reminder", message],
        check=False,
    )
"""

    body = f"""# Auto-generated OpenJarvis reminder — do not edit
import sys, pathlib
{notify_block}
try:
    pathlib.Path(__file__).unlink(missing_ok=True)
except Exception:
    pass
"""
    script_path.write_text(body, encoding="utf-8")
    script_path.chmod(0o600)
    return script_path


def _schedule_windows(target_dt: datetime, task_name: str, script_path: Path) -> bool:
    python_exe = Path(sys.executable)
    pythonw = python_exe.parent / "pythonw.exe"
    if pythonw.exists():
        python_exe = pythonw

    xml_path = _scripts_dir() / f"{task_name}.xml"
    xml_content = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        '  <RegistrationInfo><Description>OpenJarvis Reminder</Description></RegistrationInfo>\n'
        '  <Triggers><TimeTrigger>\n'
        f'    <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>\n'
        '    <Enabled>true</Enabled>\n'
        '  </TimeTrigger></Triggers>\n'
        '  <Actions Context="Author"><Exec>\n'
        f'    <Command>{python_exe}</Command>\n'
        f'    <Arguments>"{script_path}"</Arguments>\n'
        '  </Exec></Actions>\n'
        '  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
        '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
        '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
        '    <StartWhenAvailable>true</StartWhenAvailable>\n'
        '    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>\n'
        '    <Enabled>true</Enabled></Settings>\n'
        '  <Principals><Principal id="Author">\n'
        '    <LogonType>InteractiveToken</LogonType>\n'
        '    <RunLevel>LeastPrivilege</RunLevel>\n'
        '  </Principal></Principals>\n'
        '</Task>'
    )
    xml_path.write_text(xml_content, encoding="utf-16")
    result = subprocess.run(
        ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
        capture_output=True, text=True,
    )
    try:
        xml_path.unlink(missing_ok=True)
    except Exception:
        pass
    return result.returncode == 0


def _schedule_posix(target_dt: datetime, script_path: Path) -> bool:
    """Use 'at' on Linux/macOS as a fallback scheduler."""
    try:
        at_time = target_dt.strftime("%H:%M %Y-%m-%d")
        cmd_str = f"{sys.executable} {script_path}\n"
        result = subprocess.run(
            ["at", at_time],
            input=cmd_str, capture_output=True, text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _parse_reminder(text: str) -> tuple[str, str, str] | None:
    """
    Try to extract (date YYYY-MM-DD, time HH:MM, message) from free-form text.
    Patterns tried:
      - "... on YYYY-MM-DD at HH:MM ..."
      - "... YYYY-MM-DD HH:MM ..."
    """
    import re
    # Pattern: date then time
    m = re.search(
        r"(\d{4}-\d{2}-\d{2})\s+(?:at\s+)?(\d{1,2}:\d{2})\s*(.*)",
        text, re.IGNORECASE
    )
    if m:
        date_s, time_s, msg = m.group(1), m.group(2), m.group(3).strip()
        # Normalize time to HH:MM
        parts = time_s.split(":")
        time_s = f"{int(parts[0]):02d}:{parts[1]}"
        return date_s, time_s, msg or "Reminder from OpenJarvis"
    return None


def set_reminder(date_str: str, time_str: str, message: str) -> str:
    """Core scheduling logic — returns a human-readable result string."""
    try:
        target_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "Invalid date/time format. Use YYYY-MM-DD and HH:MM."

    if target_dt <= datetime.now():
        return "That time has already passed — I can't set a reminder in the past."

    safe_msg = _sanitise(message)
    task_name = f"OpenJarvisReminder_{target_dt.strftime('%Y%m%d_%H%M%S')}"

    try:
        script_path = _write_notify_script(task_name, safe_msg)
    except Exception as exc:
        return f"Could not prepare reminder script: {exc}"

    try:
        if _OS == "Windows":
            ok = _schedule_windows(target_dt, task_name, script_path)
        else:
            ok = _schedule_posix(target_dt, script_path)
    except Exception as exc:
        script_path.unlink(missing_ok=True)
        return f"Scheduling failed: {exc}"

    if not ok:
        script_path.unlink(missing_ok=True)
        return "Could not register the reminder with the system scheduler."

    friendly = target_dt.strftime("%B %d at %I:%M %p")
    return f"Reminder set for {friendly}: \"{safe_msg}\""


@plugin("remind me")
def remind_me(jarvis, s):
    """Set a reminder. Usage: remind me 2026-05-01 09:00 call dentist"""
    parsed = _parse_reminder(s)
    if parsed:
        date_s, time_s, msg = parsed
        result = set_reminder(date_s, time_s, msg)
        jarvis.say(result)
        return

    # Interactive fallback
    jarvis.say("What date should I remind you? (YYYY-MM-DD)")
    date_s = jarvis.input("> ").strip()
    jarvis.say("What time? (HH:MM, 24-hour)")
    time_s = jarvis.input("> ").strip()
    jarvis.say("What is the reminder message?")
    msg = jarvis.input("> ").strip() or "Reminder from OpenJarvis"
    result = set_reminder(date_s, time_s, msg)
    jarvis.say(result)


@plugin("reminder")
def reminder(jarvis, s):
    """Set a reminder. Usage: reminder 2026-05-01 09:00 call dentist"""
    remind_me(jarvis, s)


@plugin("set reminder")
def set_reminder_cmd(jarvis, s):
    """Set a timed reminder. Usage: set reminder 2026-05-01 09:00 dentist"""
    remind_me(jarvis, s)


@plugin("set a reminder")
def set_a_reminder(jarvis, s):
    """Set a timed reminder"""
    remind_me(jarvis, s)
