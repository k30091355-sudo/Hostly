"""Einstellungen von Hostly (aus Umgebungsvariablen, mit sinnvollen Standardwerten)."""
import os
from pathlib import Path

# Hauptordner für alle Daten (auf dem Mini-PC: /srv/hostly)
DATA_DIR = Path(os.environ.get("HOSTLY_DATA_DIR", "/srv/hostly"))

# Datenbank-Datei
DB_PATH = Path(os.environ.get("HOSTLY_DB_PATH", str(DATA_DIR / "db" / "hostly.sqlite")))

# Support-Adresse (siehe KONZEPT.md 20.1)
SUPPORT_EMAIL = "k3009135@gmail.com"

# Versionsnummer: GROSS.NEU.KLEIN – GROSS nur bei etwas Riesigem, NEU bei großen Neuerungen,
# KLEIN bei kleinen Updates/Fehlerbehebungen. Bei jedem Update erhöhen + in docs/UPDATE.md eintragen.
VERSION = "1.5.0"

# Sitzung: wie lange man eingeloggt bleibt
SESSION_DAYS = 30
SESSION_COOKIE = "hostly_session"
CSRF_COOKIE = "hostly_csrf"

# Regeln für Benutzername und Passwort
USERNAME_MIN = 3
USERNAME_MAX = 20
PASSWORD_MIN = 8
PASSWORD_MAX = 200

LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"
THEMES = ("system", "light", "dark")

# ---------- Ordner (Stufe 3+) ----------
SERVERS_DIR = DATA_DIR / "servers"      # Daten laufender Server (= /data im Container)
ARCHIVES_DIR = DATA_DIR / "archives"    # Daten abgelaufener Server
UPLOADS_DIR = DATA_DIR / "uploads"      # Server-Icons, Profilbilder
DOWNLOADS_DIR = DATA_DIR / "downloads"  # temporäre ZIPs
# Pfad desselben Ordners auf dem Mini-PC (für Docker-Bind-Mounts der Minecraft-Container)
HOST_DATA_DIR = Path(os.environ.get("HOSTLY_HOST_DATA_DIR", str(DATA_DIR)))

# ---------- Minecraft / Docker ----------
MC_IMAGE = os.environ.get("HOSTLY_MC_IMAGE", "itzg/minecraft-server:latest")
MC_NETWORK = "hostly-mc"
MC_NETWORK_PREFIX = "172.30.0."   # feste Tunnel-Plätze ab .11
MC_FIRST_SLOT = 11
RCON_PORT = 25575
SERVER_TYPES = ("VANILLA", "PAPER", "FABRIC")

# ---------- Coins & Codes ----------
CODE_MIN_COINS = 50
CODE_MAX_COINS = 1000
# ohne verwechselbare Zeichen (0/o, 1/l/i)
CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"

# ---------- Kapazität (Standardwerte, Admin kann sie ändern) ----------
DEFAULT_RAM_TOTAL_GB = 12.0     # RAM für WSL
DEFAULT_RAM_RESERVE_GB = 1.5    # muss nach jedem Kauf frei bleiben
CONTAINER_EXTRA_GB = 0.5        # Container-Grenze = Modell-RAM + 0,5 GB

TIMEZONE = "Europe/Berlin"
