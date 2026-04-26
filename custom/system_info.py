"""System info plugin — reports CPU, RAM, disk, and battery status."""

import platform
from openjarvis.plugins import plugin


def _get_stats() -> str:
    try:
        import psutil
    except ImportError:
        return "psutil is not installed. Run: pip install psutil"

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    lines = [
        f"CPU usage: {cpu:.1f}%",
        f"RAM: {mem.percent:.1f}% used ({mem.used // 1024**2} MB / {mem.total // 1024**2} MB)",
        f"Disk: {disk.percent:.1f}% used ({disk.used // 1024**3:.1f} GB / {disk.total // 1024**3:.1f} GB)",
    ]

    try:
        batt = psutil.sensors_battery()
        if batt is not None:
            plugged = "plugged in" if batt.power_plugged else "on battery"
            lines.append(f"Battery: {batt.percent:.0f}% ({plugged})")
    except Exception:
        pass

    lines.append(f"Platform: {platform.system()} {platform.release()}")
    return "\n".join(lines)


@plugin("system")
def system_info(jarvis, s):
    """Report CPU, RAM, disk, and battery status"""
    jarvis.say(_get_stats())


@plugin("system info")
def system_info_long(jarvis, s):
    """Report CPU, RAM, disk, and battery status"""
    jarvis.say(_get_stats())


@plugin("system status")
def system_status(jarvis, s):
    """Report CPU, RAM, disk, and battery status"""
    jarvis.say(_get_stats())
