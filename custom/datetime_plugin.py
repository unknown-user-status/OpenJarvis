"""Date/time plugin — tell current time, date, and day of week."""

import datetime
from openjarvis.plugins import plugin


def _now() -> datetime.datetime:
    return datetime.datetime.now()


@plugin("time")
def tell_time(jarvis, s):
    """Tell the current time"""
    t = _now().strftime("%-I:%M %p") if hasattr(datetime, "_") else _now().strftime("%I:%M %p").lstrip("0")
    jarvis.say(f"The current time is {_now().strftime('%I:%M %p').lstrip('0')}.")


@plugin("date")
def tell_date(jarvis, s):
    """Tell today's date"""
    d = _now()
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10 if d.day not in (11, 12, 13) else 0, "th")
    jarvis.say(f"Today is {d.strftime('%A, %B')} {d.day}{suffix}, {d.year}.")


@plugin("day")
def tell_day(jarvis, s):
    """Tell today's day of the week"""
    jarvis.say(f"Today is {_now().strftime('%A')}.")


@plugin("what time")
def what_time(jarvis, s):
    """Tell the current time"""
    tell_time(jarvis, s)


@plugin("what day")
def what_day(jarvis, s):
    """Tell today's day"""
    tell_day(jarvis, s)


@plugin("today")
def today(jarvis, s):
    """Tell today's date and time"""
    d = _now()
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10 if d.day not in (11, 12, 13) else 0, "th")
    jarvis.say(
        f"Today is {d.strftime('%A, %B')} {d.day}{suffix}, {d.year}. "
        f"The time is {d.strftime('%I:%M %p').lstrip('0')}."
    )
