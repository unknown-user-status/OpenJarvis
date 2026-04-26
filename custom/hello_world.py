"""Example plugin — mirrors the sukeesh/Jarvis quickstart example."""

from openjarvis.plugins import plugin


@plugin("hello world")
def hello_world(jarvis, s):
    """Say 'hello world' — example plugin"""
    jarvis.say("Hello, World! OpenJarvis is alive and running.")
