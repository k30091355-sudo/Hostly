# Hostly – Anweisungen für Claude

Kostenlose Minecraft-Hosting-Plattform auf einem Mini-PC. Spieler lösen Codes ein → Coins → mieten Minecraft-Server.
**Vollständige Regeln:** `KONZEPT.md` (was), `docs/TECHNIK.md` (wie), `docs/SEITEN-UND-ABLAEUFE.md` (Seiten/Abläufe), `docs/ANLEITUNG.md` (Einrichtung für den Besitzer), `docs/SETUP-MINI-PC.md` (Setup-Technik).
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
- Mods/Plugins nur **Modrinth** (CurseForge gestrichen). Eigene Dateien nur über Support (Admin lädt hoch).
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

**Aktueller Stand:** Stufe 1–9 fertig (Code in `hostly/`, Tests in `tests/`). Erster registrierter Account = Admin.
Entscheidungen des Besitzers (Nov. 2026): **nur Modrinth** (kein CurseForge); eigene Plugins/Mods nur über Support, Admin lädt Dateien hoch; **keine Leise-Grenze** – Backups/ZIPs immer gedrosselt; alle *Vorschläge* im Konzept sind bestätigt; Passwort ändern ohne aktuelles Passwort; keine Login-Sperre. Update-Anleitung für den Besitzer: `docs/UPDATE.md` (bei jedem Update mit besonderen Hinweisen pflegen). Geplante, noch nicht umgesetzte Wünsche: `docs/GEPLANT.md`.
**Versionsnummern** (`VERSION` in `hostly/config.py`, steht unten auf der Website): GROSS.NEU.KLEIN – GROSS nur bei etwas Riesigem, NEU bei großen Neuerungen, KLEIN bei kleinen Updates/Fehlerbehebungen. Bei jedem Update erhöhen und in `docs/UPDATE.md` als „Version x.y.z“ eintragen. Aktuell: **1.5.4** (Fehlersuche: execute-run-stop gesperrt, offene Sitzungen bei Serverstart schließen, deop alter MC-Name, letzter Admin nicht löschbar, Gewinnspiel ohne gelöschte Accounts, reservierte Weltnamen + ZIP-8-GB-Grenze, Nachtpause aus → Start; davor 1.5.3: Modpack: alle Mods env.client „required“, versionId mit Hash, no-store; davor 1.5.2: Modpack-Knopf öffentlich: Serverliste + /s/<kürzel>, `extensions.has_modpack`; davor 1.5.1: Fußzeilen-Text „selbst gebaut“ entfernt; davor 1.5.0: Lag-/Absturz-Schutz: `files.PAPER_TUNING` + `yaml_set` (nur Standardwerte ändern), Env MAX_CHAINED_NEIGHBOR_UPDATES/ENTITY_BROADCAST/MaxDirectMemorySize; Look „selbst gebaut“ (CSS-Block „Look 1.5“); davor 1.4.3: Vorlagen Survival/Creative/SkyBlock/OneBlock/Abenteuer gesperrt = `"soon": True`, „Kommt bald“; davor 1.4.2: Neustart ohne save-all-Wartezeit, nur eingefrorene Server per RCON wecken; Paper chunk-system.worker-threads = Kerne−1; davor 1.4.1: Fehlerbehebungen: BentoBox-Addons nach `plugins/BentoBox/addons/` (Spalte `subfolder`), Server-Reste gleicher Nummer → `verwaist/`, Icon nur mit `icon_path`, Paper-Join-Zeilen, Gamerules nur passende Namen; alle Vorlagen echt getestet; davor 1.4.0: neue Startseite im Stil „Idee D“ für Besucher + Eingeloggte; anonym: keine Gewinner-/Benutzernamen für andere sichtbar; davor 1.3.1: Hinweis „Neue Version – Seite aktualisieren“; davor 1.3.0: Einstellungen/Gamerules, Fehler-Erklärer, Leistung, Whitelist-Anfragen, Startbonus, Einführung, Admin-Grafik/Warnungen, Wartung planen).

## Code-Aufbau
- `hostly/db.py`: SQLite + Migrationen (neue Tabellen = neuer Eintrag in `MIGRATIONS`, nie alte ändern).
- `hostly/security.py`: Argon2id, Sitzungen (nur Token-Hash in DB), Login-Sperre, CSRF (Double-Submit-Cookie, Feld `csrf`).
- `hostly/web/deps.py`: `Ctx` pro Anfrage (`ctx.require_login()`, `ctx.require_admin()`, `ctx.check_csrf()`, `ctx.render()`).
- `hostly/web/routes/`: Seiten. Texte nur über `hostly/locales/de.json` + `en.json`.
- `hostly/cli.py`: Admin setzen / Passwort zurücksetzen per Kommandozeile.
- `hostly/coins.py`, `codes.py`, `pricing.py`, `servers.py`: Regeln (Ledger, Codes, Preise, Kauf/Verlängern/Reaktivieren/Löschen). Laufen in `db.transaction()`.
- `hostly/minecraft.py`: itzg-Container-Einstellungen. `hostly/worker/`: Aufträge (`jobs`), Docker, Status (nie bei `.paused`), Ablauf, Downloads.
- Web → worker nur über `db.add_job()`. Web liest Server-Dateien nur (Konsole = `logs/latest.log`).
- Neue Texte: `t('Deutscher Text')` – deutscher Text ist der Schlüssel, englische Übersetzung in `hostly/locales/en.json` ergänzen.
- `hostly/modrinth.py`, `extensions.py`: Modrinth-Suche, Abhängigkeiten, Vorlagen, Versionswechsel-Plan. `hostly/nightpause.py`, `promotions.py`, `stats.py`, `filemanager.py`.
- Worker-Dateiarbeit in `hostly/worker/files.py` (Plugin-Abgleich, rsync-Backups, Welt-Upload, `/trigger code`-Datapack).
- Tests: `pytest` (alle müssen grün sein).

## Werkzeuge in diesem Repo
- `caveman`-Plugin (über `.claude/settings.json`) für kürzere Antworten. Für Erklärungen an den Besitzer trotzdem verständlich bleiben.
- `archify`-Skill (wird per SessionStart-Hook installiert) für Architektur-Diagramme.
