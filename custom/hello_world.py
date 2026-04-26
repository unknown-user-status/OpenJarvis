"""Example plugin — mirrors the sukeesh/Jarvis quickstart example."""

from openjarvis.plugins import plugin


@plugin("hello")
def hello(jarvis, s):
    """Repeats what you type back to you"""
    jarvis.say(s if s else "Hello! What can I do for you?")
