"""Location plugin — current IP-based location and place lookup via Nominatim."""

import json
import urllib.request
import urllib.parse
from openjarvis.plugins import plugin

_HEADERS = {"User-Agent": "OpenJarvis/1.0"}


def _my_location() -> dict:
    """Return current location dict via ip-api.com (free, no key needed)."""
    with urllib.request.urlopen("http://ip-api.com/json/", timeout=8) as resp:
        return json.loads(resp.read())


def _geocode(place: str) -> dict | None:
    """Return first geocoding result for *place* via Nominatim."""
    q = urllib.parse.quote(place)
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        results = json.loads(resp.read())
    return results[0] if results else None


@plugin("where am i")
def where_am_i(jarvis, s):
    """Tell your current location based on your IP address"""
    try:
        loc = _my_location()
        if loc.get("status") == "success":
            city = loc.get("city", "unknown city")
            region = loc.get("regionName", "")
            country = loc.get("country", "")
            jarvis.say(f"You are currently in {city}, {region}, {country}.")
        else:
            jarvis.say("Sorry, I couldn't determine your current location.")
    except Exception as exc:
        jarvis.say(f"Location lookup failed: {exc}")


@plugin("my location")
def my_location(jarvis, s):
    """Tell your current location"""
    where_am_i(jarvis, s)


@plugin("current location")
def current_location(jarvis, s):
    """Tell your current location"""
    where_am_i(jarvis, s)


@plugin("where is")
def where_is(jarvis, s):
    """Look up the location of a place. Usage: where is Paris"""
    place = s.strip()
    if not place:
        jarvis.say("Please tell me which place you want to look up.")
        return
    try:
        result = _geocode(place)
        if result:
            display = result.get("display_name", place)
            lat = float(result["lat"])
            lon = float(result["lon"])
            jarvis.say(f"{place} is at {display}. Coordinates: {lat:.4f}°N, {lon:.4f}°E.")
        else:
            jarvis.say(f"Sorry, I couldn't find the location of {place}.")
    except Exception as exc:
        jarvis.say(f"Location search failed: {exc}")


@plugin("ip address")
def ip_address(jarvis, s):
    """Tell your current public IP address"""
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=6) as resp:
            ip = resp.read().decode().strip()
        jarvis.say(f"Your public IP address is {ip}.")
    except Exception as exc:
        jarvis.say(f"Could not retrieve IP address: {exc}")
