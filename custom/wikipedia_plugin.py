"""Wikipedia plugin — search and summarize topics using Wikipedia's REST API."""

import json
import urllib.request
import urllib.parse
from openjarvis.plugins import plugin

_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_SEARCH = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={}&format=json&srlimit=1"
_HEADERS = {"User-Agent": "OpenJarvis/1.0 (https://github.com/unknown-user-status/OpenJarvis)"}


def _summary(topic: str) -> str:
    """Fetch the extract from Wikipedia's REST summary endpoint."""
    encoded = urllib.parse.quote(topic.replace(" ", "_"))
    url = _BASE + encoded
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        extract = data.get("extract", "")
        if extract:
            # Return up to first 3 sentences
            sentences = extract.split(". ")
            return ". ".join(sentences[:3]).strip()
        return ""
    except urllib.error.HTTPError:
        return ""


def _search_and_summarize(topic: str) -> str:
    # First try exact title
    result = _summary(topic)
    if result:
        return result

    # Fall back to search
    encoded = urllib.parse.quote(topic)
    search_url = _SEARCH.format(encoded)
    req = urllib.request.Request(search_url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        items = data.get("query", {}).get("search", [])
        if items:
            title = items[0]["title"]
            result = _summary(title)
            if result:
                return result
    except Exception:
        pass

    return ""


@plugin("tell me about")
def tell_me_about(jarvis, s):
    """Search Wikipedia about a topic. Usage: tell me about Albert Einstein"""
    topic = s.strip()
    if not topic:
        jarvis.say("What topic would you like to know about?")
        return
    try:
        result = _search_and_summarize(topic)
        if result:
            jarvis.say(result)
        else:
            jarvis.say(f"Sorry, I couldn't find information about '{topic}' on Wikipedia.")
    except Exception as exc:
        jarvis.say(f"Wikipedia lookup failed: {exc}")


@plugin("wikipedia")
def wikipedia(jarvis, s):
    """Search Wikipedia. Usage: wikipedia Python programming"""
    tell_me_about(jarvis, s)


@plugin("wiki")
def wiki(jarvis, s):
    """Search Wikipedia. Usage: wiki Black holes"""
    tell_me_about(jarvis, s)


@plugin("who is")
def who_is(jarvis, s):
    """Look up a person on Wikipedia. Usage: who is Elon Musk"""
    tell_me_about(jarvis, s)


@plugin("what is")
def what_is(jarvis, s):
    """Look up a concept on Wikipedia. Usage: what is quantum computing"""
    tell_me_about(jarvis, s)
