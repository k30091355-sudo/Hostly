"""Einstellungen von Hostly (aus Umgebungsvariablen, mit sinnvollen Standardwerten)."""
import os
from pathlib import Path

# Hauptordner für alle Daten (auf dem Mini-PC: /srv/hostly)
DATA_DIR = Path(os.environ.get("HOSTLY_DATA_DIR", "/srv/hostly"))

# Datenbank-Datei
DB_PATH = Path(os.environ.get("HOSTLY_DB_PATH", str(DATA_DIR / "db" / "hostly.sqlite")))

# Support-Adresse (siehe KONZEPT.md 20.1)
SUPPORT_EMAIL = "k3009135@gmail.com"

# Sitzung: wie lange man eingeloggt bleibt
SESSION_DAYS = 30
SESSION_COOKIE = "hostly_session"
CSRF_COOKIE = "hostly_csrf"

# Login-Sperre bei Fehlversuchen (Vorschlag aus TECHNIK.md 20)
LOGIN_MAX_FAILS_USER = 5
LOGIN_MAX_FAILS_IP = 20
LOGIN_LOCK_MINUTES = 15

# Regeln für Benutzername und Passwort
USERNAME_MIN = 3
USERNAME_MAX = 20
PASSWORD_MIN = 8
PASSWORD_MAX = 200

LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"
THEMES = ("system", "light", "dark")
