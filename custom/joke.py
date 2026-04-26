"""Joke plugin — fetches a random joke from icanhazdadjoke."""

import urllib.request
import json

from openjarvis.plugins import plugin


@plugin("joke")
def joke(jarvis, s):
    """Tell a random dad joke"""
    try:
        req = urllib.request.Request(
            "https://icanhazdadjoke.com/",
            headers={"Accept": "application/json", "User-Agent": "OpenJarvis/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        jarvis.say(data.get("joke", "Why don't scientists trust atoms? Because they make up everything!"))
    except Exception:
        jarvis.say("Why don't scientists trust atoms? Because they make up everything!")
