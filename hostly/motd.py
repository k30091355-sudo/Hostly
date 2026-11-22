"""MOTD (Text in der Minecraft-Serverliste) mit §-Farbcodes."""
from markupsafe import Markup, escape

COLORS = {
    "0": "#000000", "1": "#0000AA", "2": "#00AA00", "3": "#00AAAA", "4": "#AA0000", "5": "#AA00AA",
    "6": "#FFAA00", "7": "#AAAAAA", "8": "#555555", "9": "#5555FF", "a": "#55FF55", "b": "#55FFFF",
    "c": "#FF5555", "d": "#FF55FF", "e": "#FFFF55", "f": "#FFFFFF",
}
FORMATS = {"l": "font-weight:bold", "o": "font-style:italic", "n": "text-decoration:underline",
           "m": "text-decoration:line-through"}
MAX_LINES = 2
MAX_LINE_CHARS = 60


def visible_text(motd: str) -> str:
    out, i = [], 0
    while i < len(motd):
        if motd[i] == "§" and i + 1 < len(motd):
            i += 2
            continue
        out.append(motd[i])
        i += 1
    return "".join(out)


def check(motd: str) -> str | None:
    """Fehlermeldung oder None."""
    lines = motd.replace("\r", "").split("\n")
    if len(lines) > MAX_LINES:
        return "Höchstens 2 Zeilen."
    if any(len(visible_text(line)) > MAX_LINE_CHARS for line in lines):
        return "Höchstens 60 Zeichen pro Zeile."
    if len(motd) > 400:
        return "Zu viele Formatierungen."
    return None


def to_html(motd: str | None) -> Markup:
    """§-Codes in sicheres HTML umwandeln (für Vorschau und Listen)."""
    if not motd:
        return Markup("")
    parts, color, styles, buf = [], "#AAAAAA", [], []

    def flush():
        if buf:
            style = ";".join([f"color:{color}"] + styles)
            parts.append(f'<span style="{style}">{escape("".join(buf))}</span>')
            buf.clear()

    i = 0
    while i < len(motd):
        ch = motd[i]
        if ch == "§" and i + 1 < len(motd):
            code = motd[i + 1].lower()
            flush()
            if code in COLORS:
                color, styles = COLORS[code], []
            elif code in FORMATS:
                styles.append(FORMATS[code])
            elif code == "r":
                color, styles = "#AAAAAA", []
            i += 2
            continue
        if ch == "\n":
            flush()
            parts.append("<br>")
        else:
            buf.append(ch)
        i += 1
    flush()
    return Markup("".join(parts))
