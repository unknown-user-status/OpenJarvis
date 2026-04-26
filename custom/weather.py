"""Weather plugin — get weather report for a city using wttr.in."""

import urllib.request

from openjarvis.plugins import plugin


@plugin("weather")
def weather(jarvis, s):
    """Get weather report for a city. Usage: weather London"""
    city = s.strip() if s.strip() else "auto"
    try:
        url = f"https://wttr.in/{urllib.request.quote(city)}?format=3"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = resp.read().decode("utf-8").strip()
        jarvis.say(result)
    except Exception as exc:
        jarvis.say(f"Could not fetch weather: {exc}")
