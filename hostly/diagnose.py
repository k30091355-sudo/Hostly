"""Fehler-Erklärer (Version 1.3.0): erkennt häufige Fehler im Server-Protokoll und erklärt sie einfach.

Liest nur Text (logs/latest.log, Absturz-Ausschnitt) – weckt keinen Server.
"""
import re
from dataclasses import dataclass, field


@dataclass
class Finding:
    key: str
    title: str
    text: str
    level: str = "error"              # error | warn
    action: str | None = None         # z. B. "fabric_api", "mods", "version", "upgrade", "restart"
    args: dict = field(default_factory=dict)


MOD_REQUIRES = re.compile(
    r"Mod '([^']+)' \(([^)]+)\) \S+ requires (?:any version|version [^ ]+?)(?: or later)? of "
    r"(?:mod )?'?([^',(]+?)'?(?: \(([^)]+)\))?, which is missing")
MOD_WRONG_MC = re.compile(r"Mod '([^']+)' \(([^)]+)\) \S+ requires (?:any )?version ([^ ,]+)[^,]* of '?(?:Minecraft|minecraft)'?")
MOD_WRONG_JAVA = re.compile(r"Mod '([^']+)' \(([^)]+)\) \S+ requires (?:any )?version ([^ ,]+)[^,]* of '?(?:Java|java)'?")
PAPER_PLUGIN_FAIL = re.compile(r"Could not load '?plugins/([^'\s]+)'?")
PAPER_DEPENDENCY = re.compile(r"Unknown/missing dependency plugins: \[([^\]]+)\]")
PAPER_API = re.compile(r"Unsupported API version (\S+)")
KEEP_UP = re.compile(r"Can't keep up! Is the server overloaded\? Running (\d+)ms")
TIMED_OUT = re.compile(r"(\w{1,16}) lost connection: Timed out")
# Hostlys Statusabfragen (RCON, 1× pro Minute) erzeugen bei Vanilla/Fabric je zwei Protokollzeilen → ausblenden
RCON_NOISE = re.compile(r"Thread RCON (Client|Listener)|RCON Client /[\d.]+ (started|shutting down)")


def without_noise(text: str) -> list[str]:
    return [line for line in text.splitlines() if not RCON_NOISE.search(line)]


MIXIN = re.compile(r"Mixin apply(?:ing)? (?:for mod )?(\S+) failed|MixinApplyError.*?mod (\S+)", re.I)


def analyse(log: str, server_type: str = "") -> list[Finding]:
    """Liefert erkannte Probleme (wichtigste zuerst, jedes nur einmal)."""
    found: dict[str, Finding] = {}

    def add(f: Finding) -> None:
        found.setdefault(f.key, f)

    for m in MOD_REQUIRES.finditer(log):
        mod, missing, missing_id = m.group(1), m.group(3).strip(), (m.group(4) or m.group(3)).strip()
        if missing_id in ("fabric-api", "fabric") or missing.lower() in ("fabric api", "fabric-api"):
            add(Finding("fabric_api", "Die Fabric API fehlt",
                        f"Die Mod „{mod}“ braucht die Fabric API. Ohne sie startet der Server nicht.",
                        action="fabric_api"))
        else:
            add(Finding(f"missing:{missing_id}", f"„{mod}“ braucht „{missing}“",
                        f"Installiere „{missing}“ im Reiter „Plugins/Mods“ oder deaktiviere „{mod}“.",
                        action="mods", args={"query": missing}))
    for m in MOD_WRONG_MC.finditer(log):
        add(Finding(f"mc:{m.group(2)}", f"„{m.group(1)}“ passt nicht zu dieser Minecraft-Version",
                    f"Die Mod braucht Minecraft {m.group(3)}. Wähle im Reiter „Plugins/Mods“ eine passende Version "
                    "oder deaktiviere sie.", action="mods"))
    for m in MOD_WRONG_JAVA.finditer(log):
        add(Finding(f"java:{m.group(2)}", f"„{m.group(1)}“ braucht eine andere Java-Version",
                    "Wähle eine andere Version der Mod oder eine passende Minecraft-Version.", action="mods"))
    if "Incompatible mods found" in log and not found:
        add(Finding("incompatible", "Mods passen nicht zusammen",
                    "Fabric hat Mods gefunden, die nicht zusammen funktionieren. Im Reiter „Konsole“ steht weiter "
                    "oben, welche – deaktiviere zuletzt hinzugefügte Mods nacheinander.", action="mods"))
    for m in MIXIN.finditer(log):
        mod = m.group(1) or m.group(2)
        add(Finding(f"mixin:{mod}", f"Die Mod „{mod}“ verträgt sich nicht mit anderen Mods",
                    "Deaktiviere diese Mod oder wähle eine andere Version.", action="mods"))
    if "UnsupportedClassVersionError" in log:
        add(Finding("java_version", "Ein Plugin/eine Mod ist für eine neuere Java-Version gebaut",
                    "Meist ist die Erweiterung für eine neuere Minecraft-Version. Wähle eine ältere Version davon.",
                    action="mods"))
    for m in PAPER_DEPENDENCY.finditer(log):
        add(Finding(f"dep:{m.group(1)}", "Einem Plugin fehlt ein anderes Plugin",
                    f"Benötigt wird: {m.group(1)}. Installiere es im Reiter „Plugins/Mods“.",
                    action="mods", args={"query": m.group(1).split(",")[0].strip()}))
    for m in PAPER_API.finditer(log):
        add(Finding("paper_api", "Ein Plugin ist für eine andere Minecraft-Version",
                    f"Das Plugin verlangt API-Version {m.group(1)}. Wähle eine passende Plugin-Version.",
                    action="mods"))
    for m in PAPER_PLUGIN_FAIL.finditer(log):
        add(Finding(f"plugin:{m.group(1)}", f"Das Plugin „{m.group(1)}“ konnte nicht geladen werden",
                    "Es passt wahrscheinlich nicht zur Server-Version oder ihm fehlt ein anderes Plugin.",
                    action="mods"))
    if "java.lang.OutOfMemoryError" in log:
        add(Finding("memory", "Der Server hat zu wenig Arbeitsspeicher",
                    "Entferne große Mods/Plugins, verkleinere die Sichtweite (Reiter „Einstellungen“) oder "
                    "wechsle im Reiter „Miete“ auf ein größeres Modell.", action="upgrade"))
    if re.search(r"newer version of Minecraft|was saved with a newer version|Outdated server", log):
        add(Finding("world_newer", "Die Welt ist von einer neueren Minecraft-Version",
                    "Stelle im Reiter „Version“ mindestens die Version ein, mit der die Welt gespielt wurde.",
                    action="version"))
    if "AccessDeniedException" in log:
        add(Finding("access", "Minecraft durfte eine Datei nicht öffnen",
                    "Starte den Server einmal neu – Hostly repariert die Ordner-Rechte dabei automatisch.",
                    action="restart"))
    if "FAILED TO BIND TO PORT" in log:
        add(Finding("port", "Der Server konnte nicht starten (Port belegt)",
                    "Meist hilft es, den Server zu stoppen, 30 Sekunden zu warten und wieder zu starten.",
                    action="restart"))
    if "Exception in server tick loop" in log or "This crash report has been saved" in log:
        add(Finding("crash", "Der Server ist abgestürzt",
                    "Oft ist eine Mod oder ein Plugin schuld. Deaktiviere zuletzt hinzugefügte Erweiterungen "
                    "und starte neu. Im Ordner „crash-reports“ (Reiter „Dateien“) stehen Details."))
    lag = [int(x) for x in KEEP_UP.findall(log)]
    if len(lag) >= 3 or any(x > 10_000 for x in lag):
        add(Finding("lag", "Der Server kommt nicht hinterher (Ruckler)",
                    "Verkleinere die Sichtweite (Reiter „Einstellungen“), entferne aufwendige Mods/Plugins oder "
                    "wechsle auf ein größeres Modell.", level="warn", action="upgrade"))
    timeouts = TIMED_OUT.findall(log)
    if len(timeouts) >= 3:
        add(Finding("timeouts", "Spieler verlieren oft die Verbindung („Timed out“)",
                    "Das liegt meist an der Internetverbindung oder am Tunnel. Eine kleinere Sichtweite "
                    "(Reiter „Einstellungen“) hilft oft.", level="warn"))
    order = {"error": 0, "warn": 1}
    return sorted(found.values(), key=lambda f: order.get(f.level, 2))[:5]
