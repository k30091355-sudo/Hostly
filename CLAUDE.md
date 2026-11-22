# Hostly – Anweisungen für Claude

Kostenlose Minecraft-Hosting-Plattform auf einem Mini-PC. Spieler lösen Codes ein → Coins → mieten Minecraft-Server.
**Vollständige Regeln:** `KONZEPT.md` (was), `docs/TECHNIK.md` (wie), `docs/SEITEN-UND-ABLAEUFE.md` (Seiten/Abläufe), `docs/SETUP-MINI-PC.md` (Einrichtung).
Lies den jeweils relevanten Abschnitt, bevor du eine Funktion baust – nicht alles auf einmal.

## Arbeitsweise
- Besitzer ist Anfänger, spricht **Deutsch** → Antworten auf Deutsch, einfach erklären.
- **Klein anfangen**, Stufe für Stufe (siehe „Stufen“). Jede Stufe für sich lauffähig + getestet.
- Code auf `main` committen und pushen; der Besitzer holt ihn per `git pull` auf den Mini-PC und startet mit `docker compose up -d`.
- Nichts erfinden, was dem Konzept widerspricht. Bei Unklarheit fragen. Mit *Vorschlag* markierte Punkte im Konzept sind noch nicht bestätigt.
- Keine Modell-Namen in Commits/Code.

## Feste Rahmenbedingungen
- **Komplett kostenlos**: keine Abos, keine Domain, keine kostenpflichtigen Dienste.
- Mini-PC: **Windows 11** bleibt, Hostly läuft in **WSL2 (Ubuntu 24.04)**, **12 GB RAM** für WSL, CPU **i5-12400T** (WSL: 8 Threads), 477 GB SSD.
- **Leise**: Leerlauf ≈ keine CPU-Last. Server einfrieren (`itzg` Auto-Pause), Status nie bei eingefrorenen Servern abfragen (weckt sie), Backups 02–06 Uhr im Schnecken-Tempo.

## Technik (entschieden)
- Python 3.12, **FastAPI**, Jinja2 + **HTMX**, SQLite (WAL), APScheduler, Docker-SDK.
- Zwei Dienste: **hostly-web** (Website, KEIN Docker-Zugriff) und **hostly-worker** (Zeitsteuerung, Docker, Backups). Web → worker über Auftrags-Tabelle `jobs`.
- Minecraft: **`itzg/minecraft-server`** (kein Pelican). Typen: Vanilla, Paper, Fabric.
- Website extern: **Tailscale Funnel** (`https://hostly.<tailnet>.ts.net`). Minecraft extern: **playit.gg** (2 Accounts), feste Tunnel-Plätze im Docker-Netz `hostly-mc` (z. B. `172.30.0.11:25565`).
- Mods/Plugins nur **Modrinth + CurseForge**. Eigene Dateien nur über Support (Admin lädt hoch).
- Daten unter `/srv/hostly/` (db, servers, backups, archives, uploads, resourcepacks).

## Kernregeln (Kurzfassung)
- **Login**: Benutzername + Passwort (Argon2id), keine E-Mail-Funktionen. Passwort vergessen → Hinweis „E-Mail an k3009135@gmail.com“, Admin erzeugt zufälliges Passwort. Admin kann Passwörter nie sehen.
- **Zugriff**: ohne Login alles ansehen, nichts kaufen/einlösen/teilnehmen.
- **Codes**: Format `xxxx-xxxx-xxxx-xxxx` (Zahlen + Kleinbuchstaben), 50–1000 Coins, max. Einlösungen, optional Ablaufdatum, pro User nur 1× („Code bereits eingelöst“).
- **Modelle**: Holz 2 GB/3 Spieler/10 Coins/Tag · Eisen 3 GB/7/30 · Diamant 4 GB/15/50.
- **RAM-Prüfung**: Container-Grenze = Modell-RAM + 0,5 GB; nach Kauf müssen in WSL **≥ 1,5 GB frei** bleiben; zusätzlich freier Tunnel nötig, sonst „Kauf aktuell nicht möglich“ (+ „Benachrichtige mich“).
- **Preise**: Tage frei wählbar; Tage-Rabatt = Tage in % (ab 2 Tagen, max. 50 %); Rabatt-Aktionen addieren; **Gesamtrabatt max. 75 %**; **immer abrunden** (Ausnahme: Nachtpausen-Erstattung aufrunden). Coins einmalig beim Kauf abgebucht.
- **Nachtpause**: frei wählbar, max. 15 h, 1 %/h; Erstattung erst nach jeder vollständig beendeten Pause; manueller Start in der Pause → keine Erstattung.
- **Upgrade**: Differenz × Resttage × (1 − ursprünglicher Rabatt). **Downgrade/Löschen**: anteilige Erstattung (abgerundet). Admin löscht mit oder ohne Erstattung.
- **Auto-Verlängern**: am Ablauftag immer 7 Tage, Rabatte gelten; zu wenig Coins → Ablauf + Warnung.
- **Ablauf**: Warnung 3 Tage vorher (Startseite) → archivieren (Ordner verschieben) → reaktivierbar. Archive für immer.
- **Backups**: täglich 02–06 Uhr, inkrementell (`rsync --link-dest`), stark gedrosselt; ab 06 Uhr nur bis zur „Leise-Grenze“; älter als 7 Tage löschen (außer angepinnt).
- **Konsole**: Befehle per RCON; `stop/restart/end/reload` in allen Schreibweisen gesperrt (`minecraft:stop`, `rl`, `bukkit:reload` …) – dafür Knöpfe.
- **Coins**: Kontostand = Summe des Ledgers, Transaktionen atomar, nie negativ, Doppelklick-Schutz.
- **Statistiken**: per Server-Kürzel öffentlich, inkl. Spielernamen. Öffentliche Serverliste: opt-in (Standard aus).
- **Design**: Name „Hostly“, modern/clean, normale Schrift, Dark/Light, Deutsch (Standard) + Englisch, PWA, Handy zuerst.

## Stufen (Reihenfolge)
0. Setup Mini-PC (Besitzer, mit Anleitung)
1. Grundgerüst: Website, Design Dark/Light, Registrieren, Login, Einstellungen, Admin-Umschalter
2. Coins: Codes, Einlösen, Coin-Verlauf, Admin-User-Menü
3. Erster Server: itzg-Anbindung, Modelle, Kauf + Preisberechnung, RAM-/Tunnel-Prüfung, Tunnel-Verwaltung, Start/Stopp, Konsole
4. Ablauf: Warnungen, Archiv, Reaktivieren, Verlängern, Auto-Verlängern, Löschen
5. Komfort: MOTD, Icon-Zuschnitt, Whitelist, Join-Verlauf, OP, Profilbild, Download
6. Aktionen: Gewinnspiele, Rabatt-/RAM-Aktionen, Nachtpause, Up-/Downgrade, Übertragungen
7. Backups & Admin-Dashboard, Wartungsmodus
8. Erweiterungen: Modrinth/CurseForge, Versionen, Typwechsel, Welten, Resourcepacks, Modpack
8b. Dateimanager, Absturz-Schutz, Vorlagen, Kürzel & Statistik, Serverliste
9. Feinschliff: Englisch, PWA, Installations-Anleitung

**Aktueller Stand:** Konzept fertig. Nächster Schritt: **Stufe 1**.

## Werkzeuge in diesem Repo
- `caveman`-Plugin (über `.claude/settings.json`) für kürzere Antworten. Für Erklärungen an den Besitzer trotzdem verständlich bleiben.
- `archify`-Skill (wird per SessionStart-Hook installiert) für Architektur-Diagramme.
