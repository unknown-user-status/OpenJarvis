"""YouTube plugin — search and open YouTube videos in the browser."""

import webbrowser
import urllib.parse
from openjarvis.plugins import plugin


def _youtube_search_url(query: str) -> str:
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)


def _youtube_play_url(query: str) -> str:
    """Try to open the first result via ytsearch (pywhatkit if available, else search page)."""
    try:
        import pywhatkit
        # pywhatkit.playonyt opens the top result directly
        pywhatkit.playonyt(query)
        return ""  # pywhatkit handles it
    except ImportError:
        pass
    # Fallback: open search results page
    return _youtube_search_url(query)


@plugin("play")
def play_youtube(jarvis, s):
    """Play a YouTube video. Usage: play Bohemian Rhapsody"""
    query = s.strip()
    if not query:
        jarvis.say("What would you like me to play on YouTube?")
        return
    jarvis.say(f"Opening YouTube for '{query}'...")
    url = _youtube_play_url(query)
    if url:
        webbrowser.open(url)


@plugin("youtube")
def youtube(jarvis, s):
    """Search YouTube. Usage: youtube lofi music"""
    query = s.strip()
    if not query:
        webbrowser.open("https://www.youtube.com")
        jarvis.say("Opening YouTube.")
        return
    jarvis.say(f"Searching YouTube for '{query}'...")
    url = _youtube_play_url(query)
    if url:
        webbrowser.open(url)


@plugin("play on youtube")
def play_on_youtube(jarvis, s):
    """Play a video on YouTube. Usage: play on youtube lo-fi beats"""
    play_youtube(jarvis, s)


@plugin("search youtube")
def search_youtube(jarvis, s):
    """Search YouTube for a video. Usage: search youtube Python tutorial"""
    query = s.strip()
    if not query:
        jarvis.say("What should I search for on YouTube?")
        return
    url = _youtube_search_url(query)
    webbrowser.open(url)
    jarvis.say(f"Searching YouTube for '{query}'.")


@plugin("play music")
def play_music(jarvis, s):
    """Play music on YouTube. Usage: play music jazz"""
    query = (s.strip() + " music").strip()
    play_youtube(jarvis, query)
