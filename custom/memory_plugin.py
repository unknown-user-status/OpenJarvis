"""Memory plugin — persistent long-term memory (MK37-style).

Jarvis remembers facts about you across sessions, stored in
~/.openjarvis/memory/long_term.json under categories:
  identity, preferences, projects, relationships, wishes, notes

Usage:
  remember my name is Alex
  remember I prefer dark mode (preference)
  what do you know about me
  forget my name
  my memory
"""

from __future__ import annotations

import re

from openjarvis.plugins import plugin


def _parse_remember(s: str) -> tuple[str, str, str]:
    """
    Parse 'key is value (category)' or 'key is value' from free text.
    Returns (key, value, category).
    """
    # Check for explicit category in parentheses: "I prefer dark mode (preference)"
    cat_match = re.search(r'\((\w+)\)\s*$', s)
    category = "notes"
    if cat_match:
        cat_raw = cat_match.group(1).lower()
        valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
        if cat_raw in valid:
            category = cat_raw
        elif cat_raw in ("preference", "pref"):
            category = "preferences"
        elif cat_raw in ("project", "goal"):
            category = "projects"
        elif cat_raw in ("relation", "person", "friend", "family"):
            category = "relationships"
        elif cat_raw in ("wish", "plan", "want"):
            category = "wishes"
        elif cat_raw in ("id", "profile", "who", "me"):
            category = "identity"
        s = s[:cat_match.start()].strip()

    # Try "my X is Y" or "I am X" etc.
    m = re.match(
        r"(?:my\s+)?(.+?)\s+(?:is|are|=)\s+(.+)",
        s, re.IGNORECASE
    )
    if m:
        key = m.group(1).strip().lower().replace(" ", "_")
        value = m.group(2).strip()
        # Infer identity category from common keys
        id_keys = {"name", "age", "birthday", "city", "job", "language", "school",
                   "nationality", "country", "email", "phone"}
        if category == "notes" and key in id_keys:
            category = "identity"
        return key, value, category

    # Fallback: whole string is the value, key = "note_<n>"
    import datetime
    key = f"note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return key, s.strip(), category


@plugin("remember")
def remember(jarvis, s):
    """Remember something. Usage: remember my name is Alex"""
    text = s.strip()
    if not text:
        jarvis.say("What would you like me to remember?")
        text = jarvis.input("> ").strip()
    if not text:
        jarvis.say("Nothing to remember.")
        return
    key, value, category = _parse_remember(text)
    result = jarvis.remember(key, value, category)
    jarvis.say(f"Got it. I'll remember: {key.replace('_', ' ')} = {value} [{category}].")


@plugin("memorize")
def memorize(jarvis, s):
    """Store something in memory. Usage: memorize I prefer dark themes (preferences)"""
    remember(jarvis, s)


@plugin("what do you know about me")
def what_do_you_know(jarvis, s):
    """Show everything Jarvis remembers about you"""
    summary = jarvis.memory_summary()
    if summary:
        jarvis.say(summary)
    else:
        jarvis.say("I don't have any information stored about you yet.")


@plugin("my memory")
def my_memory(jarvis, s):
    """Show stored memory"""
    what_do_you_know(jarvis, s)


@plugin("show memory")
def show_memory(jarvis, s):
    """Display all stored memory"""
    what_do_you_know(jarvis, s)


@plugin("forget")
def forget_cmd(jarvis, s):
    """Remove something from memory. Usage: forget my name"""
    text = s.strip()
    if not text:
        jarvis.say("What should I forget?")
        return
    # Strip "my" prefix
    key = re.sub(r"^my\s+", "", text.lower()).strip().replace(" ", "_")
    # Try all categories
    from openjarvis.memory.memory_manager import load_memory, save_memory
    memory = load_memory()
    found = False
    for cat, data in memory.items():
        if isinstance(data, dict) and key in data:
            del data[key]
            save_memory(memory)
            jarvis.say(f"Forgotten: {key.replace('_', ' ')}.")
            found = True
            break
    if not found:
        jarvis.say(f"I don't have '{key.replace('_', ' ')}' in my memory.")


@plugin("recall")
def recall_cmd(jarvis, s):
    """Recall a specific memory. Usage: recall my name"""
    text = re.sub(r"^my\s+", "", s.strip().lower()).replace(" ", "_")
    value = jarvis.recall(text)
    if value:
        jarvis.say(f"{text.replace('_', ' ').title()}: {value}")
    else:
        jarvis.say(f"I don't remember anything about '{text.replace('_', ' ')}'.")
