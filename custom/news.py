"""News plugin — fetch top headlines via BBC RSS feed (no API key needed)."""

import urllib.request
import xml.etree.ElementTree as ET
from openjarvis.plugins import plugin


_RSS_URL = "http://feeds.bbci.co.uk/news/rss.xml"
_MAX_HEADLINES = 5


def _fetch_headlines(url: str = _RSS_URL, max_items: int = _MAX_HEADLINES) -> list[str]:
    req = urllib.request.Request(url, headers={"User-Agent": "OpenJarvis/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    titles = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            titles.append(title_el.text.strip())
        if len(titles) >= max_items:
            break
    return titles


@plugin("news")
def news(jarvis, s):
    """Fetch and read top news headlines (BBC RSS)"""
    try:
        headlines = _fetch_headlines()
        if not headlines:
            jarvis.say("Sorry, I couldn't fetch the news right now.")
            return
        jarvis.say(f"Here are today's top {len(headlines)} headlines:")
        for i, h in enumerate(headlines, 1):
            jarvis.say(f"{i}. {h}")
    except Exception as exc:
        jarvis.say(f"Could not fetch news: {exc}")


@plugin("headlines")
def headlines(jarvis, s):
    """Fetch and read top news headlines"""
    news(jarvis, s)


@plugin("top news")
def top_news(jarvis, s):
    """Fetch and read top news headlines"""
    news(jarvis, s)
