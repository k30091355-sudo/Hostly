"""Server-Einstellungen per Formular und Gamerules per Klick (Version 1.3.0)."""
import json

DIFFICULTIES = {"peaceful": "Friedlich", "easy": "Einfach", "normal": "Normal", "hard": "Schwer"}
GAMEMODES = {"survival": "Überleben", "creative": "Kreativ", "adventure": "Abenteuer"}
VIEW_DISTANCE = (4, 12)        # mehr kostet viel CPU/RAM und bremst die Verbindung über playit
SPAWN_PROTECTION = (0, 64)

# Gamerules: neuer Name (ab Minecraft 1.21.11 / 26.x, geprüft mit 26.3) → alter Name (ältere Versionen).
# Hostly schickt nur die Namen, die zur Version des Servers passen (uses_new_names).
GAMERULES = {
    "keep_inventory": ("keepInventory", False, "Inventar nach dem Tod behalten"),
    "advance_time": ("doDaylightCycle", True, "Tag und Nacht wechseln"),
    "advance_weather": ("doWeatherCycle", True, "Wetter wechselt"),
    "spawn_mobs": ("doMobSpawning", True, "Monster und Tiere erscheinen"),
    "mob_griefing": ("mobGriefing", True, "Monster zerstören Blöcke (z. B. Creeper)"),
    "spawn_phantoms": ("doInsomnia", True, "Phantome erscheinen, wenn man nicht schläft"),
    "fall_damage": ("fallDamage", True, "Fallschaden"),
    "natural_health_regeneration": ("naturalRegeneration", True, "Leben regeneriert sich"),
    "immediate_respawn": ("doImmediateRespawn", False, "Sofort wiederbeleben (ohne Todesbildschirm)"),
    "show_death_messages": ("showDeathMessages", True, "Todesnachrichten im Chat"),
    "locator_bar": ("locatorBar", True, "Ortungsleiste (zeigt andere Spieler an)"),
}
SLEEP_RULE = ("players_sleeping_percentage", "playersSleepingPercentage", 100)


def load_rules(server) -> dict:
    try:
        data = json.loads(server["gamerules"] or "{}")
    except (ValueError, TypeError):
        data = {}
    rules = {key: bool(data.get(key, default)) for key, (_, default, _) in GAMERULES.items()}
    try:
        rules[SLEEP_RULE[0]] = max(0, min(100, int(data.get(SLEEP_RULE[0], SLEEP_RULE[2]))))
    except (ValueError, TypeError):
        rules[SLEEP_RULE[0]] = SLEEP_RULE[2]
    return rules


def changed_rules(server) -> dict:
    """Nur die Regeln, die vom Minecraft-Standard abweichen oder ausdrücklich gesetzt wurden."""
    try:
        return {k: v for k, v in json.loads(server["gamerules"] or "{}").items()}
    except (ValueError, TypeError):
        return {}


def commands(rules: dict) -> tuple[list[str], list[str]]:
    """(Befehle mit neuen Namen, Befehle mit alten Namen)."""
    new, old = [], []
    for key, value in rules.items():
        if key == SLEEP_RULE[0]:
            new.append(f"gamerule {key} {int(value)}")
            old.append(f"gamerule {SLEEP_RULE[1]} {int(value)}")
        elif key == "pvp":   # gibt es als Gamerule erst ab 26.x (vorher server.properties)
            new.append(f"gamerule pvp {'true' if value else 'false'}")
        elif key in GAMERULES:
            text = "true" if value else "false"
            new.append(f"gamerule {key} {text}")
            old.append(f"gamerule {GAMERULES[key][0]} {text}")
    return new, old


def uses_new_names(mc_version: str | None) -> bool:
    """Neue Gamerule-Namen (snake_case) gibt es ab Minecraft 1.21.11 und bei allen 26.x-Versionen.
    „LATEST“ ist immer die neueste Version → neue Namen."""
    v = (mc_version or "LATEST").strip()
    if not v[:1].isdigit():
        return True
    try:
        parts = [int(p) for p in v.split("-")[0].split(".")]
    except ValueError:
        return True
    if parts[0] >= 2:          # 26.1, 26.3 … (neues Versionsschema)
        return True
    minor = parts[1] if len(parts) > 1 else 0
    patch = parts[2] if len(parts) > 2 else 0
    return (minor, patch) >= (21, 11)


def commands_for(server, rules: dict | None = None) -> list[str]:
    """Nur die Befehle, die zur Minecraft-Version des Servers passen (keine Fehlermeldungen im Protokoll)."""
    new, old = commands(changed_rules(server) if rules is None else rules)
    return new if uses_new_names(server["mc_version"]) else old


def clamp(value, lo_hi: tuple[int, int], default: int) -> int:
    try:
        return max(lo_hi[0], min(lo_hi[1], int(value)))
    except (ValueError, TypeError):
        return default
