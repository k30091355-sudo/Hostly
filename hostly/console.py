"""Konsole: gesperrte Befehle (TECHNIK.md 8.2) und Hilfen."""
import re

# Dafür gibt es Knöpfe
BLOCKED = {"stop", "restart", "end", "reload", "rl"}
MAX_LENGTH = 256


def is_blocked(command: str) -> bool:
    """Kleinschreiben, führende / entfernen, Namensraum (xyz:) entfernen, erstes Wort vergleichen."""
    text = command.strip().lower().lstrip("/").strip()
    if not text:
        return True
    first = text.split()[0]
    if ":" in first:
        first = first.rsplit(":", 1)[1]
    return first in BLOCKED


def clean(command: str) -> str:
    """Einzeilig, ohne Steuerzeichen, mit Längengrenze."""
    command = re.sub(r"[\x00-\x1f\x7f]", "", command).strip()
    if command.startswith("/"):
        command = command[1:]
    return command[:MAX_LENGTH]


MC_NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def valid_mc_name(name: str) -> bool:
    return bool(MC_NAME_RE.match(name))
