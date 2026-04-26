"""Search plugin — open Google search results in the browser."""

import webbrowser
import urllib.parse
from openjarvis.plugins import plugin


@plugin("search")
def search(jarvis, s):
    """Search Google. Usage: search latest AI news"""
    query = s.strip()
    if not query:
        jarvis.say("What would you like me to search for?")
        return
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url)
    jarvis.say(f"Searching Google for '{query}'.")


@plugin("google")
def google(jarvis, s):
    """Search Google. Usage: google Python tutorials"""
    query = s.strip()
    if not query:
        webbrowser.open("https://www.google.com")
        jarvis.say("Opening Google.")
        return
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url)
    jarvis.say(f"Searching Google for '{query}'.")


@plugin("search google for")
def search_google_for(jarvis, s):
    """Search Google. Usage: search google for deep learning"""
    search(jarvis, s)


@plugin("search for")
def search_for(jarvis, s):
    """Search Google. Usage: search for Python tutorials"""
    search(jarvis, s)
