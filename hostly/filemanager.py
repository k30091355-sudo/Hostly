"""Dateimanager: sichere Pfade und gesperrte Dateien (KONZEPT.md 20a, TECHNIK.md 20)."""
from pathlib import Path

from . import minecraft

# Diese Dateien darf niemand ändern (sonst könnte man Limits umgehen)
LOCKED_FILES = {"eula.txt", ".rcon-cli.env", ".rcon-cli.yaml", ".knockd.cfg", ".hostly-managed.json",
                "ops.json", "whitelist.json"}
LOCKED_DIRS = {"hostly-disabled", "libraries", "versions", ".fabric", "cache"}
# Diese Einstellungen in server.properties setzt Hostly selbst
PROTECTED_PROPERTIES = {"max-players", "server-port", "server-ip", "enable-rcon", "rcon.port", "rcon.password",
                        "query.port", "enable-query", "online-mode", "white-list", "enforce-whitelist",
                        "level-name", "motd", "resource-pack", "resource-pack-sha1", "require-resource-pack"}
MAX_EDIT_BYTES = 1024 * 1024
TEXT_SUFFIXES = {".properties", ".yml", ".yaml", ".json", ".json5", ".toml", ".txt", ".cfg", ".conf", ".ini",
                 ".mcmeta", ".mcfunction", ".log", ".md", ".csv", ".sk", ".js", ".lang"}


def resolve(server_id: int, rel: str) -> Path | None:
    base = minecraft.data_dir(server_id).resolve()
    rel = (rel or "").replace("\\", "/").strip("/")
    target = (base / rel).resolve()
    if target != base and not str(target).startswith(str(base) + "/"):
        return None
    return target


def is_locked(rel: str) -> bool:
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    if not parts:
        return True
    return parts[-1] in LOCKED_FILES or parts[0] in LOCKED_DIRS


def is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in ("server.properties",)


def parse_properties(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def protected_changes(old: str, new: str) -> list[str]:
    """Welche geschützten Einstellungen wurden geändert?"""
    a, b = parse_properties(old), parse_properties(new)
    return sorted(k for k in PROTECTED_PROPERTIES if a.get(k) != b.get(k))
