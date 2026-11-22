"""Nachtpause (KONZEPT.md 13): Zeitfenster und Erstattung."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config

MAX_HOURS = 15


def tz() -> ZoneInfo:
    return ZoneInfo(config.TIMEZONE)


def planned_hours(start: int, end: int) -> int:
    return (end - start) % 24


def check(start: int, end: int) -> str | None:
    if not (0 <= start <= 23 and 0 <= end <= 23):
        return "Ungültige Uhrzeit."
    hours = planned_hours(start, end)
    if hours == 0:
        return "Die Nachtpause muss mindestens 1 Stunde lang sein."
    if hours > MAX_HOURS:
        return "Die Nachtpause darf höchstens 15 Stunden lang sein."
    return None


def _at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=tz())


def window_containing(now: datetime, start: int, end: int) -> tuple[datetime, datetime] | None:
    """Das Pausen-Fenster, in dem `now` gerade liegt (auch über Mitternacht), sonst None."""
    local = now.astimezone(tz())
    for offset in (0, -1):
        day = local.date() + timedelta(days=offset)
        s = _at(day, start)
        e = _at(day + timedelta(days=1 if end <= start else 0), end)
        if s <= local < e:
            return s, e
    return None


def next_start(now: datetime, start: int) -> datetime:
    local = now.astimezone(tz())
    s = _at(local.date(), start)
    return s if s > local else _at(local.date() + timedelta(days=1), start)


def real_hours(s: datetime, e: datetime) -> int:
    """Echte Stunden (bei Zeitumstellung 1 mehr oder weniger)."""
    return int((e.astimezone(ZoneInfo("UTC")) - s.astimezone(ZoneInfo("UTC"))).total_seconds() // 3600)


def refund(paid_total: int, paid_days: int, hours: int, discount_percent: int) -> int:
    """aufrunden( bezahlter Tagespreis × min(Stunden, 15, 75 − Rabatt) % )"""
    if paid_days <= 0:
        return 0
    percent = max(0, min(hours, MAX_HOURS, 75 - discount_percent))
    return -(-paid_total * percent // (paid_days * 100))   # ganzzahlig aufgerundet
