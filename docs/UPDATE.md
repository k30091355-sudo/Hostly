# Hostly aktualisieren – Schritt für Schritt

> Immer wenn es eine neue Hostly-Version gibt, holst du sie so auf den Mini-PC.
> Dauer: ca. 2–5 Minuten. Deine Daten (Accounts, Coins, Welten, Backups) bleiben erhalten –
> außer es steht unten bei „Besondere Hinweise“ etwas anderes.

---

## ⚠️ Besondere Hinweise zum Update vom 22.11.2026

Bei **diesem einen** Update passiert einmalig Folgendes:
- **Alle Accounts werden gelöscht** (auch dein Admin-Account, und alle Coins). Das passiert nur dieses eine Mal.
- Tunnel, Codes und Aktionen bleiben erhalten. (Codes können wieder neu eingelöst werden.)
- **Der erste Account, der danach erstellt wird, wird wieder Admin.**

👉 Deshalb: **Direkt nach dem Update** (Schritt 4 unten) sofort unter `http://localhost:8000` deinen Account neu erstellen – bevor jemand anderes es über die Internet-Adresse tun kann.

Außerdem neu in diesem Update:
- **Passwort ändern** geht jetzt ohne das aktuelle Passwort (nur neues Passwort + wiederholen).
- **Keine Login-Sperre** mehr nach vielen falschen Passwörtern.
- **Kaufmenü:** Preis und Rabatt werden wieder sofort aktualisiert, wenn du Tage oder Modell änderst.
- **Hinweis zur Nachtpause:** Der Nachtpausen-Rabatt wird nicht sofort abgezogen, sondern nachträglich erstattet.

---

## Schritt 1 – Ubuntu öffnen
Start → **„Ubuntu“** öffnen. ✅ Du siehst `praxis2@DESKTOP-…:~$` (bzw. deinen Benutzernamen).

## Schritt 2 – (Optional) Wartungsmodus einschalten
Nur nötig, wenn gerade Leute spielen oder kaufen könnten:
Hostly → **Admin-Bereich → Einstellungen → Wartungsmodus → Einschalten**.
(Minecraft-Server laufen weiter, nur auf der Website kann kurz niemand etwas kaufen.)

## Schritt 3 – Neue Version holen und starten
🐧 Ubuntu – diesen Befehl kopieren, mit Rechtsklick einfügen, `Enter`:
```
cd /srv/hostly/app && git pull && docker compose up -d --build
```
Was passiert:
1. `git pull` lädt die neue Version von GitHub. ✅ Es erscheinen Dateinamen und z. B. „3 files changed“.
   (Steht dort „Already up to date.“, gibt es nichts Neues.)
2. `docker compose up -d --build` baut Hostly neu und startet es neu (1–3 Minuten).
   ✅ Am Ende: `Container hostly-web Started` und `Container hostly-worker Started`.

> Laufende **Minecraft-Server laufen dabei weiter** – nur die Website ist für ein paar Sekunden weg.

## Schritt 4 – Prüfen
```
docker compose ps
```
✅ `hostly-web`, `hostly-worker` (und `hostly-playit-1`, falls eingerichtet) stehen auf **Up**.

Dann im Browser **`http://localhost:8000`** öffnen → Hostly erscheint.
(Bei diesem Update jetzt sofort **„Account erstellen“** – siehe oben. ✅ Oben steht das gelbe **„Admin“**-Schild.)

## Schritt 5 – Wartungsmodus wieder ausschalten
Falls du ihn in Schritt 2 eingeschaltet hast: **Admin-Bereich → Einstellungen → Wartungsmodus → Ausschalten**.

Fertig! 🎉

---

## Wenn etwas nicht klappt

**Protokolle anschauen** (die letzten Zeilen kannst du mir schicken – vorher prüfen, dass kein playit-Schlüssel darin steht):
```
cd /srv/hostly/app && docker compose logs --tail 50 web worker
```

| Problem | Lösung |
|---|---|
| `git pull` meldet „Your local changes … would be overwritten“ | Du hast versehentlich eine Datei im Ordner `app` geändert. Mit `git status` siehst du welche. Zurücksetzen: `git checkout -- DATEINAME`, dann Schritt 3 nochmal. (Deine `.env` mit den playit-Schlüsseln ist davon nicht betroffen.) |
| `permission denied` bei `docker` | In PowerShell `wsl --shutdown`, Ubuntu neu öffnen, Schritt 3 nochmal. |
| `hostly-web` steht auf „Restarting“ | Protokolle anschauen (siehe oben) und mir schicken. |
| Website lädt nicht | 30 Sekunden warten und neu laden. Dann `docker compose ps` prüfen. |
| Ich bin nach dem Update nicht Admin | 🐧 `cd /srv/hostly/app && docker compose exec web python -m hostly.cli admin DEINNAME` |

## Passwort vergessen?
Du kommst trotzdem wieder rein – 🐧 Ubuntu:
```
cd /srv/hostly/app && docker compose exec web python -m hostly.cli passwort DEINNAME
```
→ Es wird ein neues zufälliges Passwort angezeigt. Damit einloggen, dann wählst du ein eigenes.
