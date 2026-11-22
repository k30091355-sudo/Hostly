"""Übersetzungen: Texte stehen in locales/de.json und locales/en.json.

Fehlt ein Text im Englischen, wird der deutsche genommen.
"""
import json
from functools import lru_cache
from pathlib import Path

from . import config

_DIR = Path(__file__).parent / "locales"


@lru_cache
def _load(lang: str) -> dict[str, str]:
    return json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def translate(lang: str, key: str, **values) -> str:
    if lang not in config.LANGUAGES:
        lang = config.DEFAULT_LANGUAGE
    text = _load(lang).get(key) or _load(config.DEFAULT_LANGUAGE).get(key) or key
    return text.format(**values) if values else text
