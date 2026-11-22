"""Zeit-Hilfen. In der Datenbank steht immer UTC im Format 'YYYY-MM-DD HH:MM:SS'."""
from datetime import datetime, timedelta, timezone

FMT = "%Y-%m-%d %H:%M:%S"


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(FMT)


def parse(text: str) -> datetime:
    return datetime.strptime(text, FMT).replace(tzinfo=timezone.utc)


def now_sql() -> str:
    return fmt(now())


def full_days_left(until: str) -> int:
    """Nur volle Resttage (angebrochener Tag zählt nicht)."""
    seconds = (parse(until) - now()).total_seconds()
    return max(0, int(seconds // 86400))


def time_left(until: str) -> timedelta:
    return parse(until) - now()
