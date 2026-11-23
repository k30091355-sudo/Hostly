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
        elif key == "pvp":   # Gamerule erst ab 1.21.9 (vorher nur server.properties, siehe OLD_NAME_SINCE)
            new.append(f"gamerule pvp {'true' if value else 'false'}")
            old.append(f"gamerule pvp {'true' if value else 'false'}")
        elif key in GAMERULES:
            text = "true" if value else "false"
            new.append(f"gamerule {key} {text}")
            old.append(f"gamerule {GAMERULES[key][0]} {text}")
    return new, old


def version_tuple(mc_version: str | None) -> tuple:
    """Vergleichbare Version: „1.21.4“ → (1, 21, 4), „26.1“ → (26, 1, 0). „LATEST“/Unbekanntes → ganz neu."""
    v = (mc_version or "LATEST").strip()
    try:
        parts = [int(p) for p in v.split("-")[0].split(".")]
    except ValueError:
        return (999, 0, 0)
    return tuple((parts + [0, 0])[:3])


def uses_new_names(mc_version: str | None) -> bool:
    """Neue Gamerule-Namen (snake_case) gibt es ab Minecraft 1.21.11 und bei allen 26.x-Versionen.
    „LATEST“ ist immer die neueste Version → neue Namen."""
    return version_tuple(mc_version) >= (1, 21, 11)


# Gamerules, die es erst ab einer bestimmten Version gibt. Ein unbekannter Name im Datapack würde die ganze
# Funktion ungültig machen – dann gälte keine einzige Regel.
OLD_NAME_SINCE = {"pvp": (1, 21, 9), "locatorBar": (1, 21, 6), "playersSleepingPercentage": (1, 17, 0), "doImmediateRespawn": (1, 15, 0),
                  "doInsomnia": (1, 15, 0), "fallDamage": (1, 15, 0)}


def commands_for(server, rules: dict | None = None) -> list[str]:
    """Nur die Befehle, die zur Minecraft-Version des Servers passen (keine Fehlermeldungen im Protokoll)."""
    new, old = commands(changed_rules(server) if rules is None else rules)
    if uses_new_names(server["mc_version"]):
        return new
    v = version_tuple(server["mc_version"])
    return [c for c in old if v >= OLD_NAME_SINCE.get(c.split()[1], (0, 0, 0))]


def clamp(value, lo_hi: tuple[int, int], default: int) -> int:
    try:
        return max(lo_hi[0], min(lo_hi[1], int(value)))
    except (ValueError, TypeError):
        return default
