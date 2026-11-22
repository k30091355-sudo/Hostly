# Hostly aktualisieren – Schritt für Schritt

> Immer wenn es eine neue Hostly-Version gibt, holst du sie so auf den Mini-PC.
> Dauer: ca. 2–5 Minuten. Deine Daten (Accounts, Coins, Welten, Backups) bleiben erhalten –
> außer es steht unten bei „Besondere Hinweise“ etwas anderes.

---

## Versionsnummern
Ab jetzt hat jedes Update eine Versionsnummer, z. B. **1.2.0**. Du siehst sie unten auf der Website neben „Hostly“.
- **1**.x.x – ändert sich nur bei etwas Riesigem
- x.**2**.x – große Neuerung
- x.x.**0** – kleine Updates und Fehlerbehebungen

## Besondere Hinweise – neueste Version zuerst

### Version 1.2.0 (22.11.2026) – Neues Design
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten.
- **Neues Logo** („Server-Rack“) – auch als Tab-Symbol und Handy-App-Symbol.
- **Blaues Design**, **Dark-Mode in Dunkelblau**, weiche Schatten unter den Karten.
- **Coins immer oben rechts mit goldener Münze** (auch auf Handys golden).
- **Kopfzeile** wird beim Scrollen leicht durchsichtig mit Unschärfe.
- **Status mit farbigem Punkt:** 🟢 Online (pulsiert), 🔵 Schläft, ⚪ Aus, 🔴 Abgestürzt.
- **„Meine Server“ als Karten** mit Balken für Spieler und Restlaufzeit (gelb ab 7, rot ab 3 Tagen) und Adresse zum Kopieren.
- **Schönere Leer-Anzeigen** mit kleinem Bild und Knopf (z. B. „Ersten Server mieten“).
- **Unten auf der Seite:** Hostly + Versionsnummer (Klick → Startseite), Support, English.
- Code-Bilder (Admin → Codes) jetzt auch in Blau.

👉 Falls im Browser oder in der Handy-App noch das alte grüne Design erscheint: Seite einmal neu laden (am PC `Strg + F5`).

### Update 6 (22.11.2026, nachts) – Codes als Bild
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten.
- **Admin → Codes:** Neu erstellte Codes gibt es jetzt auch als schlichtes Bild (Logo, „Free Java Server Hosting“, Code, Coins, wie oft einlösbar, Website) – mit den Knöpfen **„Bild kopieren“** und **„Herunterladen“**.

### Update 5 (22.11.2026, nachts) – Fabric API automatisch
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten.
- **Behoben:** Fabric-Server startete nicht mit „requires fabric-api, which is missing“ (z. B. bei TabTPS). Hostly installiert die Fabric API jetzt bei jeder Mod automatisch mit.
- Fehlt sie auf einem bestehenden Server, zeigt der Reiter „Plugins/Mods“ einen Knopf **„Fabric API jetzt hinzufügen“**. Danach den Server neu starten.

### Update 4 (22.11.2026, nachts) – playit-Verbindung + Konsole
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten.
- **Verbindungsabbrüche („Timed out“ ca. 30 Sekunden nach dem Betreten):** Der playit-Agent läuft jetzt direkt im Netz von WSL statt in einem eigenen Docker-Netz, damit große Datenpakete (Welt-Daten) nicht hängen bleiben. Außerdem hat er mehr Arbeitsspeicher (512 MB statt 128 MB), und Server schicken beim Betreten weniger Daten auf einmal (Sichtweite 8 statt 10 Chunks).
- Deine Tunnel im playit-Dashboard bleiben gleich (weiter `172.30.0.11:25565` usw.).
- **Konsole:** Die Antworten des Servers stehen jetzt immer sichtbar unter der Eingabezeile. Mit den Pfeiltasten ↑ ↓ holst du frühere Befehle zurück. Das Protokoll springt nicht mehr weg, während du etwas markierst.

👉 **Nach dem Update:** Server einmal **neu starten**, damit die neue Sichtweite gilt.

### Update 2 (22.11.2026, abends) – Fehlerbehebungen
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten. Deine Accounts und Server bleiben.
- **Behoben:** Server startete mit Fehler `AccessDeniedException: ./world/session.lock` (falsche Ordner-Rechte). Wird beim Update automatisch repariert.
- **Behoben:** „Internal Server Error“ beim Hochladen eines Server-Icons.
- **Behoben:** `docker compose up` hing ca. 90 Sekunden bei „Recreate hostly-worker“ – jetzt wenige Sekunden.
- **Schneller:** Minecraft-Server bekommen mehr CPU (Holz 2, Eisen 3, Diamant 4 Kerne; Windows hat weiter Vorrang) und optimierte Java-Einstellungen. Gilt nach dem nächsten Start/Neustart des Servers.
- **Server-Menü:** Reiter „Backups“ entfernt (Backups laufen weiter, wiederherstellen kann der Admin unter Admin-Bereich → Backups & Archive). Reiter „Statistik“ zeigt jetzt die Statistik direkt. Alle Reiter sind auch am Handy sichtbar (Zeilenumbruch).
- **Whitelist:** Server mit Whitelist erscheinen nicht in der öffentlichen Serverliste.
- Fehlgeschlagene Aktionen werden in der Server-Übersicht angezeigt; ein Server bleibt nicht mehr ewig bei „wird erstellt …“ hängen.
- Vorlagen und Versionswechsel prüfen, ob es Paper/Fabric für die Minecraft-Version schon gibt.

👉 **Nach dem Update:** Server, die mit Fehler liefen, in Hostly einmal auf **„Starten“** (bzw. „Neustarten“) drücken.

### Update 1 (22.11.2026, nachmittags) – Accounts gelöscht
Nur wichtig, falls du dieses Update noch nicht gemacht hast:
- **Alle Accounts wurden einmalig gelöscht.** Der erste danach erstellte Account wird Admin → direkt nach dem Update unter `http://localhost:8000` neu registrieren.
- Passwort ändern ohne aktuelles Passwort, keine Login-Sperre, Live-Preis im Kaufmenü repariert, Hinweis zur Nachtpause.

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
(Nur bei Update 1: jetzt sofort **„Account erstellen“** – siehe oben.)

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
