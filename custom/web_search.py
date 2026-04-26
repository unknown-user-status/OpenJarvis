"""Web search plugin — real web search using DuckDuckGo (no API key needed).

Falls back to opening a browser search page if the library isn't installed.

Usage:
  search for python tutorials
  search web artificial intelligence
  web search how to make pasta
"""

from __future__ import annotations

import urllib.parse
import webbrowser

from openjarvis.plugins import plugin


def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Search using duckduckgo-search library if available."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })
        return results
    except ImportError:
        return []


def _format_results(query: str, results: list[dict]) -> str:
    if not results:
        return ""
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):
            lines.append(f"{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _search(query: str) -> str:
    results = _ddg_search(query)
    if results:
        return _format_results(query, results)
    # Fallback: open browser
    url = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
    webbrowser.open(url)
    return f"Opened DuckDuckGo search for '{query}' in your browser."


@plugin("web search")
def web_search(jarvis, s):
    """Search the web. Usage: web search python tutorials"""
    query = s.strip()
    if not query:
        jarvis.say("What would you like me to search for?")
        return
    jarvis.say(_search(query))


@plugin("search web")
def search_web(jarvis, s):
    """Search the web. Usage: search web latest AI news"""
    web_search(jarvis, s)


@plugin("look up")
def look_up(jarvis, s):
    """Search the web for something. Usage: look up best Python IDE"""
    web_search(jarvis, s)


@plugin("find information about")
def find_info(jarvis, s):
    """Search the web for information. Usage: find information about quantum computing"""
    web_search(jarvis, s)
