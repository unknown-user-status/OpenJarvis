"""Greet plugin — respond to user greetings."""

import random
import datetime
from openjarvis.plugins import plugin


_RESPONSES = [
    "Always at your service, sir.",
    "I am ready, sir.",
    "Your wish is my command.",
    "How can I help you today?",
    "Online and ready, sir.",
    "Hello! What can I do for you?",
]


def _time_greeting() -> str:
    hour = datetime.datetime.now().hour
    if 0 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 18:
        return "Good afternoon"
    return "Good evening"


@plugin("hello")
def hello(jarvis, s):
    """Respond to a greeting"""
    jarvis.say(f"{_time_greeting()}! {random.choice(_RESPONSES)}")


@plugin("hi")
def hi(jarvis, s):
    """Respond to a greeting"""
    jarvis.say(random.choice(_RESPONSES))


@plugin("hey")
def hey(jarvis, s):
    """Respond to a greeting"""
    jarvis.say(random.choice(_RESPONSES))


@plugin("good morning")
def good_morning(jarvis, s):
    """Respond to a morning greeting"""
    jarvis.say("Good morning, sir! Hope you have a wonderful day. How can I help?")


@plugin("good evening")
def good_evening(jarvis, s):
    """Respond to an evening greeting"""
    jarvis.say("Good evening, sir! How may I assist you tonight?")


@plugin("good afternoon")
def good_afternoon(jarvis, s):
    """Respond to an afternoon greeting"""
    jarvis.say("Good afternoon, sir! How may I help you?")


@plugin("goodbye")
def goodbye(jarvis, s):
    """Respond to a farewell"""
    jarvis.say("Goodbye, sir! It was a pleasure working with you.")


@plugin("bye")
def bye(jarvis, s):
    """Respond to a farewell"""
    jarvis.say("Goodbye! Have a great day, sir.")
