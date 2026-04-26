"""Note plugin — save and read notes to a local text file."""

import pathlib
import datetime
from openjarvis.plugins import plugin

_NOTES_FILE = pathlib.Path.home() / "jarvis_notes.txt"


def _append_note(text: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with _NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text}\n")


def _read_notes(max_lines: int = 10) -> list[str]:
    if not _NOTES_FILE.exists():
        return []
    lines = _NOTES_FILE.read_text(encoding="utf-8").splitlines()
    return lines[-max_lines:]


@plugin("note")
def note(jarvis, s):
    """Save a note. Usage: note Buy groceries tomorrow"""
    text = s.strip()
    if not text:
        jarvis.say("What would you like me to note down?")
        text = jarvis.input("> ").strip()
    if text:
        _append_note(text)
        jarvis.say(f"Got it. I've noted: \"{text}\"")
    else:
        jarvis.say("Nothing to note.")


@plugin("make a note")
def make_a_note(jarvis, s):
    """Save a note. Usage: make a note Buy groceries"""
    note(jarvis, s)


@plugin("remember this")
def remember_this(jarvis, s):
    """Save a note. Usage: remember this Call doctor at 3 PM"""
    note(jarvis, s)


@plugin("write this down")
def write_this_down(jarvis, s):
    """Save a note. Usage: write this down Meeting at 10 AM"""
    note(jarvis, s)


@plugin("read notes")
def read_notes(jarvis, s):
    """Read your last saved notes"""
    lines = _read_notes()
    if not lines:
        jarvis.say("You have no notes yet.")
    else:
        jarvis.say(f"Here are your last {len(lines)} notes:")
        for line in lines:
            jarvis.say(line)


@plugin("show notes")
def show_notes(jarvis, s):
    """Show your last saved notes"""
    read_notes(jarvis, s)


@plugin("my notes")
def my_notes(jarvis, s):
    """Show your saved notes"""
    read_notes(jarvis, s)
