# Hostly – Technisches Konzept

> Ergänzung zu [`KONZEPT.md`](../KONZEPT.md). Dort steht, **was** Hostly kann. Hier steht, **wie** es technisch gebaut wird.
> Stand: Planung, **noch kein Code**. Gebaut wird erst nach „fang an“.
> Kennzeichnung: **ENTSCHIEDEN** · *Vorschlag* · **OFFEN** · ⚠️ = wichtige Erkenntnis aus der Recherche

---

## Inhaltsverzeichnis
1. Überblick & Leitlinien
2. Komponenten
3. Verzeichnisstruktur auf dem Mini-PC
4. Netzwerk: Website, Minecraft, Tunnel
5. Minecraft-Server mit `itzg/minecraft-server`
6. RAM- und CPU-Planung
7. Einfrieren (Auto-Pause) & Leise-Betrieb
8. Konsole & gesperrte Befehle
9. Zeitgesteuerte Aufgaben (Scheduler)
10. Lebenszyklus eines Servers (Zustände)
11. Backups im Schnecken-Tempo
12. Archiv & Reaktivieren
13. Modrinth & CurseForge
14. Modpack für Spieler (`.mrpack`)
15. Resourcepacks
16. Status, Statistiken, öffentliche Serverliste
17. Server-Kürzel & `/code`
18. Datenmodell (Datenbank)
19. Coins: Buchhaltung ohne Fehler
20. Sicherheit
21. Website-Technik (Oberfläche)
22. Schnittstellen (API-Übersicht)
23. Admin-Dashboard: Datenquellen
24. Wartungsmodus technisch
25. Tests
26. Risiken & Gegenmaßnahmen
27. Offene technische Fragen

---

## 1. Überblick & Leitlinien
- **Alles kostenlos**, alles auf **einem Mini-PC** (16 GB RAM, Windows 11, Hostly in WSL2 mit 12 GB).
- **Windows bleibt nutzbar**: Hostly ist abgeschottet und darf Windows nicht stören.
- **Leise**: Leerlauf = praktisch keine CPU-Last (Einfrieren, Schnecken-Backups, keine unnötigen Abfragen).
- **Einfach**: so wenige bewegliche Teile wie möglich (kein Pelican, kein Kubernetes, keine großen Datenbanken).
- **Robust**: Stromausfall, Windows-Neustart oder Absturz dürfen keine Coins oder Welten kaputt machen.

---

## 2. Komponenten
```
┌──────────────────────── Windows 11 ─────────────────────────────┐
│  Aufgabenplanung: startet WSL beim Hochfahren                    │
│  Energieoptionen: kein Standby, Turbo aus (leise)                │
│                                                                  │
│  ┌──────────────────── WSL2 (Ubuntu, 12 GB) ──────────────────┐  │
│  │ systemd                                                     │  │
│  │  ├─ tailscaled ──── Funnel :443 → hostly-web :8000           │  │
│  │  ├─ docker                                                   │  │
│  │  │   ├─ hostly-web      (Website + API, FastAPI)             │  │
│  │  │   ├─ hostly-worker   (Zeitsteuerung, Docker-Steuerung)    │  │
│  │  │   ├─ playit-agent-1  (playit-Account 1)                   │  │
│  │  │   ├─ playit-agent-2  (playit-Account 2)                   │  │
│  │  │   └─ mc-<server-id>  (je Minecraft-Server ein Container)  │  │
│  │  └─ Daten: /srv/hostly/...                                   │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

| Komponente | Aufgabe | Technik (*Vorschlag*) |
|---|---|---|
| **hostly-web** | Website, Login, alle Seiten, API für die Oberfläche | Python 3.12+, FastAPI, Jinja2-Templates, HTMX |
| **hostly-worker** | Abläufe, Nachtpausen, Backups, Gewinnspiel-Ziehung, Status-Abfragen, Docker steuern | Python, APScheduler, Docker-SDK für Python |
| **Datenbank** | Alle Daten (User, Coins, Server …) | SQLite im WAL-Modus (eine Datei, kein eigener Dienst) |
| **mc-*** | Minecraft-Server | `itzg/minecraft-server` (ENTSCHIEDEN) |
| **playit-agent-1/2** | Tunnel nach außen | offizieller playit-Agent als Container |
| **tailscaled** | Website per HTTPS erreichbar | Tailscale Funnel (ENTSCHIEDEN) |

**Warum zwei Teile (web + worker)?**
- Nur der **worker** darf Docker steuern (Docker-Zugriff = sehr mächtig). Die Website selbst bekommt **keinen** Docker-Zugriff → wird die Website angegriffen, kommt niemand an Docker heran.
- Die Website schreibt Aufträge in die Datenbank (z. B. „Server 12 starten“), der worker führt sie aus.

---

## 3. Verzeichnisstruktur auf dem Mini-PC (in WSL2)
```
/srv/hostly/
├── app/                  Hostly-Programmcode (aus diesem Repo)
├── db/hostly.sqlite      Datenbank
├── db-backups/           tägliche Kopie der Datenbank (klein, wichtig!)
├── servers/<server-id>/  Daten laufender Server (= /data im Container)
├── backups/<server-id>/<datum>/   tägliche Backups (inkrementell)
├── archives/<server-id>/ Daten abgelaufener Server
├── uploads/              Profilbilder, Server-Icons (Original + 64×64)
├── resourcepacks/        bereitgestellte Resourcepacks (mit SHA-1)
├── downloads/            temporäre ZIPs für Downloads (werden aufgeräumt)
└── logs/                 Hostly-Protokolle
```
- **Alles liegt im Linux-Dateisystem von WSL2** (nicht unter `/mnt/c`): viel schneller, und Windows-Laufwerke bleiben abgeschaltet (ENTSCHIEDEN).
- ⚠️ Die WSL2-Festplatte ist eine Datei (`ext4.vhdx`), die mitwächst. Gelöschte Daten machen sie nicht automatisch kleiner → `sparseVhd=true` einschalten (*Vorschlag*, siehe Setup).

---

## 4. Netzwerk

### 4.1 Website (Tailscale Funnel, ENTSCHIEDEN)
- `tailscale funnel --bg 8000` → öffentlich unter `https://hostly.<tailnet>.ts.net`.
- ⚠️ Funnel erlaubt nur die öffentlichen Ports **443, 8443, 10000** – wir nutzen 443, passt.
- ⚠️ Funnel hat eine **nicht veröffentlichte Bandbreiten-Grenze**. Für eine Website reicht das. Große Downloads (Welt-ZIPs, Resourcepacks) könnten langsam sein → im Auge behalten.

### 4.2 Minecraft (playit.gg, ENTSCHIEDEN)
**Idee: feste „Tunnel-Plätze“** (*Vorschlag*)
- Ein eigenes Docker-Netz `hostly-mc` mit festen Adressen, z. B. `172.30.0.11`, `172.30.0.12`, …
- Jeder playit-Tunnel zeigt auf **einen festen Platz** (z. B. Tunnel A → `172.30.0.11:25565`).
- Bekommt ein Server einen Tunnel zugewiesen, startet Hostly seinen Container **mit genau dieser Adresse**.
- Vorteil: Tunnel müssen nie umgestellt werden, alle Server nutzen intern Port 25565, **keine Ports am Windows-PC offen**.

**Admin trägt pro Tunnel ein:**
| Feld | Beispiel |
|---|---|
| Name | „Tunnel A“ |
| playit-Account | 1 oder 2 |
| Öffentliche Adresse | `blue-cat.joinmc.link` |
| Interner Platz | `172.30.0.11` (Hostly schlägt den nächsten freien vor) |
| Aktiv | ja/nein |

⚠️ Recherche: Bei playit muss als lokale Adresse die **Container-Adresse** eingetragen werden, nicht `localhost`. Mit festen Plätzen ist das einmalig erledigt.

### 4.3 Hostly intern
- `hostly-web` und `hostly-worker` im Netz `hostly-int`.
- Der worker ist zusätzlich in `hostly-mc` (für RCON und Status-Abfragen).
- Minecraft-Container sind **nur** in `hostly-mc`, sehen die Website-Datenbank nicht.

---

## 5. Minecraft-Server mit `itzg/minecraft-server` (ENTSCHIEDEN)

### 5.1 Zuordnung Hostly-Einstellung → Container-Einstellung
| Hostly | Umgebungsvariable | Bemerkung |
|---|---|---|
| Server-Typ | `TYPE=VANILLA` / `PAPER` / `FABRIC` | |
| Minecraft-Version | `VERSION=1.21.x` | |
| RAM (Java) | `MEMORY=2G` usw. | siehe Kapitel 6 |
| Max. Spieler | `MAX_PLAYERS=3/7/15` | fest pro Modell, User kann es nicht erhöhen |
| MOTD | `MOTD=...` | unterstützt §-Farbcodes und `\n` für 2 Zeilen |
| Server-Icon | `ICON=<pfad>` + `OVERRIDE_ICON=true` | Hostly erzeugt 64×64-PNG |
| Whitelist | `WHITELIST=...`, `ENFORCE_WHITELIST=true` | zusätzlich live per RCON `whitelist add/remove` |
| OP für Besitzer | `OPS=<minecraft-name>` | aus User-Einstellungen |
| Welt / Seed / Typ | `LEVEL`, `SEED`, `LEVEL_TYPE` | Weltenwechsel = `LEVEL` ändern |
| Resourcepack | `RESOURCE_PACK`, `RESOURCE_PACK_SHA1`, `RESOURCE_PACK_ENFORCE` | Kapitel 15 |
| Modrinth | `MODRINTH_PROJECTS=...`, `MODRINTH_DOWNLOAD_DEPENDENCIES=required` | Kapitel 13 |
| CurseForge | `CURSEFORGE_FILES=...`, `CF_API_KEY` | Kapitel 13 |
| Online-Modus | `ONLINE_MODE=true` | nur echte Minecraft-Accounts |
| Einfrieren | `ENABLE_AUTOPAUSE=true` u. a. | Kapitel 7 |
| Konsole | `ENABLE_RCON=true`, `RCON_PASSWORD_FILE` | Kapitel 8 |

### 5.2 Container-Grundeinstellungen
- Neustart-Regel: `restart: unless-stopped` (Absturz → automatischer Neustart; Hostly zählt Abstürze, siehe KONZEPT 20a).
- Keine Ports am Host veröffentlicht (Zugriff nur über Tunnel-Platz).
- Speicher- und CPU-Grenzen (Kapitel 6).
- `stop_grace_period: 60s`, damit beim Stoppen die Welt sauber gespeichert wird.
- Health-Check des Images (`mc-health`) nutzen, um „online“ korrekt zu erkennen.

### 5.3 Typ- und Versionswechsel
1. Automatisches Backup (Kapitel 11, hier ausnahmsweise sofort, aber trotzdem gedrosselt).
2. Prüfen, welche Mods/Plugins es für Ziel-Typ/-Version gibt (Modrinth-/CurseForge-Abfrage).
3. Liste anzeigen („werden aktualisiert“ / „werden deaktiviert“), User bestätigt.
4. Container mit neuen Einstellungen neu erstellen, Daten bleiben im Ordner.

---

## 6. RAM- und CPU-Planung

### 6.1 ⚠️ Wichtige Erkenntnis: Java braucht mehr als „sein“ RAM
`MEMORY=2G` legt nur den Java-Speicher (Heap) fest. Der Prozess braucht zusätzlich ca. **0,3–0,8 GB** (Java selbst, Threads, Netzwerk). Daraus folgt eine Entscheidung:

| Variante | Beschreibung | Folge |
|---|---|---|
| **A** (ENTSCHIEDEN) | User bekommt den beworbenen RAM als Java-Speicher. Container-Grenze = Modell-RAM + 0,5 GB. RAM-Prüfung rechnet mit der Container-Grenze. | Ehrlich gegenüber dem User, aber weniger Server passen drauf. |
| B | Container-Grenze = Modell-RAM, Java bekommt etwas weniger (z. B. 2 GB → 1,6 GB Java). | Mehr Server passen, aber User bekommt real weniger. |

### 6.2 ⚠️ Wie viel passt drauf?
- WSL2 bekommt **12 GB** (ENTSCHIEDEN). Windows behält 4 GB **außerhalb** von WSL.
- Hostly selbst (web, worker, playit, Docker, Linux) braucht ca. **1–1,5 GB**.
- Die Regel „nach dem Kauf **mind. 4 GB frei**“ wurde beschlossen, **als noch die ganzen 16 GB gemeint waren**. Jetzt sind Windows' 4 GB schon außerhalb abgezogen.

| Reserve in WSL | Nutzbar für Minecraft | Beispiel-Belegung (Variante A) |
|---|---|---|
| 4 GB (wörtlich wie beschlossen) | ca. 8 GB | 3× Holz **oder** 1× Diamant + 1× Eisen |
| **1,5 GB (ENTSCHIEDEN)** | ca. 10,5 GB | 4× Holz **oder** 2× Diamant + 1× Holz |

→ **ENTSCHIEDEN:** Reserve innerhalb von WSL = **1,5 GB** (Windows' 4 GB liegen schon außerhalb).

### 6.3 CPU
- Pro Container eine CPU-Grenze (*Vorschlag*): Holz 1 Kern, Eisen 1,5 Kerne, Diamant 2 Kerne (`cpus:`).
- CPU: **Intel Core i5-12400T** – 6 Kerne / 12 Threads, 35 W. *Vorschlag:* WSL2 bekommt **8 Threads** (`processors=8`), 4 bleiben immer für Windows. Holz 1 / Eisen 1,5 / Diamant 2 Kerne passt gut.
- Zusätzlich **niedrigere Priorität** (`cpu_shares`) für Minecraft als für Windows-Programme → der Besitzer merkt beim Arbeiten möglichst wenig.

---

## 7. Einfrieren (Auto-Pause) & Leise-Betrieb (ENTSCHIEDEN: „super“)

### 7.1 Zwei Stufen
| Stufe | Wie | CPU im Leerlauf |
|---|---|---|
| Eingebaute Minecraft-Pause (ab 1.21.2) | `pause-when-empty-seconds` – Minecraft hört auf zu „ticken“, wenn niemand online ist | niedrig, aber Java läuft noch |
| **`itzg` Auto-Pause** (*Vorschlag: nutzen*) | `ENABLE_AUTOPAUSE=true` – der ganze Java-Prozess wird **eingefroren** | **praktisch 0** |

⚠️ Die `itzg`-Doku rät seit 1.21.2 eher zur eingebauten Pause. Für das Ziel „Lüfter aus“ ist das echte Einfrieren aber besser. *Vorschlag:* `itzg` Auto-Pause nutzen und beim Setup messen; falls Probleme (z. B. mit bestimmten Fabric-Mods), auf die eingebaute Pause zurückfallen.

### 7.2 Einstellungen (*Vorschlag*)
| Variable | Wert | Bedeutung |
|---|---|---|
| `ENABLE_AUTOPAUSE` | `true` | einschalten |
| `AUTOPAUSE_TIMEOUT_EST` | `300` | 5 Min nach dem letzten Spieler einfrieren (Standard wären 60 Min) |
| `AUTOPAUSE_TIMEOUT_INIT` | `300` | 5 Min nach dem Start ohne Spieler einfrieren |
| `AUTOPAUSE_TIMEOUT_KN` | `60` | nach einem „Anklopfen“ (Statusabfrage) nur 1 Min wach |
| `MAX_TICK_TIME` | `-1` | ⚠️ Pflicht: Watchdog aus, sonst „stürzt“ der Server nach dem Aufwachen ab |
| `JVM_DD_OPTS` | `disable.watchdog:true` | ⚠️ Pflicht bei **Paper** (eigener Watchdog) |

- Beim Joinen wacht der Server automatisch auf (1–2 Sekunden).
- Die Datei `/data/.paused` zeigt an, dass der Server schläft → **Hostly liest diese Datei**, statt den Server anzupingen (Kapitel 16).
- Die Datei `/data/.skip-pause` verhindert das Einfrieren (z. B. während eines Backups, falls nötig).

### 7.3 ⚠️ Statusabfragen wecken Server auf
Eine normale Minecraft-Statusabfrage („Server-List-Ping“) gilt als „Anklopfen“ und **weckt** den Server. Würde Hostly alle Server jede Minute abfragen, wären sie nie eingefroren → Lüfter.
**Regel:** Hostly fragt **nie** einen eingefrorenen Server ab. Siehe Kapitel 16.

### 7.4 Leise-Grenze (ENTSCHIEDEN: wird beim Setup gemeinsam ermittelt)
1. Testlast erzeugen (z. B. Komprimierung mit begrenzter CPU).
2. CPU-Anteil schrittweise erhöhen: 10 % → 20 % → 30 % … eines Kerns.
3. Besitzer hört hin. Sobald der Lüfter hörbar wird → eine Stufe zurück = **Leise-Grenze**.
4. Wert wird in den Hostly-Einstellungen gespeichert (Admin kann ihn später ändern).

### 7.5 Weitere Leise-Maßnahmen
- Windows-Energieoptionen: **maximaler Prozessorzustand 90–99 %** (Turbo aus).
- Hostly-worker arbeitet ereignisgesteuert, nicht im Sekundentakt; Status-Abfragen nur für **wache** Server, höchstens alle 60 s.
- Keine Komprimierung tagsüber außer bei User-Downloads (diese mit niedriger Priorität).

---

## 8. Konsole & gesperrte Befehle (ENTSCHIEDEN)

### 8.1 Technik
- **Ausgabe:** Hostly liest das Container-Protokoll live (`docker logs --follow`) und schickt es per WebSocket an den Browser.
- **Eingabe:** Befehle gehen per **RCON** an den Server (`ENABLE_RCON=true`, Passwort pro Server zufällig, nur im internen Netz erreichbar).
- ⚠️ Ist der Server eingefroren, weckt Hostly ihn vor einem Befehl auf (Tunnel-„Anklopfen“) bzw. zeigt „Server schläft – wird geweckt …“.

### 8.2 Gesperrte Befehle (Filter)
Gesperrt, weil es dafür Knöpfe gibt: `stop`, `restart`, `end`, `reload`.
⚠️ Diese Befehle gibt es in mehreren Schreibweisen, alle müssen gesperrt sein:
| Gesperrt | Varianten |
|---|---|
| stop | `stop`, `/stop`, `minecraft:stop` |
| restart | `restart`, `spigot:restart`, `bukkit:restart` |
| reload | `reload`, `rl`, `bukkit:reload`, `bukkit:rl`, `minecraft:reload`, `reload confirm` |
| end | `end` |
- Prüfung: Befehl kleinschreiben, führenden `/` entfernen, Namensraum (`xyz:`) entfernen, erstes Wort vergleichen.
- *Vorschlag:* Außerdem sperren: Befehle, die das Spieler-Limit oder Server-Einstellungen umgehen (z. B. Plugin-Befehle zum Ändern von `max-players`). Liste wird beim Bau ergänzt.

### 8.3 Knöpfe
| Knopf | Technik |
|---|---|
| Starten | Container starten |
| Stoppen | `save-all` per RCON, dann Container stoppen (60 s Zeit zum Speichern) |
| Neustarten | wie Stoppen + Starten |
| Reload | bei Paper `reload confirm` per RCON (mit Warnhinweis), bei Vanilla/Fabric `reload` (lädt Datapacks neu) |

---

## 9. Zeitgesteuerte Aufgaben (Scheduler im hostly-worker)
| Aufgabe | Wann | Was |
|---|---|---|
| Ablauf-Prüfung | jede Minute | abgelaufene Server → Auto-Verlängern versuchen, sonst archivieren |
| Ablauf-Warnungen | stündlich | Server mit < 3 Tagen Rest → Warnung auf Startseite |
| Nachtpause Start/Ende | jede Minute | Server stoppen bzw. starten; nach vollständiger Pause Erstattung buchen |
| RAM-Aktionen Ende | jede Minute | Aktion vorbei → betroffene Server beim nächsten Neustart auf Normal-RAM |
| Gewinnspiel-Ziehung | jede Minute | beendete Gewinnspiele auslosen |
| Status-Abfrage | alle 60 s | **nur wache** Server: Spieler, Ping, MOTD (Kapitel 16) |
| Join-Verlauf | laufend | Protokoll-Zeilen „joined/left the game“ auswerten |
| Absturz-Zähler | laufend | Docker-Ereignisse beobachten |
| „Platz frei“-Benachrichtigung | bei jeder Freigabe | Warteliste prüfen |
| Backups | 02:00–06:00 (+ ggf. danach leise) | Kapitel 11 |
| Backup-Aufräumen | täglich 06:30 | älter als 7 Tage + neuere vorhanden + nicht angepinnt → löschen |
| Datenbank-Sicherung | täglich 02:00 | Kopie von `hostly.sqlite` nach `db-backups/` (30 Tage behalten) |
| Download-Aufräumen | stündlich | temporäre ZIPs älter als 24 h löschen |

- **Nach einem Neustart** (Stromausfall, Windows-Update) holt der worker verpasste Aufgaben nach (z. B. Abläufe, die in der Zwischenzeit fällig waren).
- Zeitzone: **Europe/Berlin** (*Vorschlag*), Sommer-/Winterzeit wird automatisch berücksichtigt.
- ⚠️ Nachtpause über Mitternacht (z. B. 23:00–07:00) muss korrekt funktionieren; bei der Zeitumstellung zählen die **echten** Stunden.

---

## 10. Lebenszyklus eines Servers (Zustände)
```
            Kauf
             │
             ▼
        ┌─────────┐  Start   ┌─────────┐  kein Spieler 5 Min  ┌──────────────┐
        │ erstellt │────────▶│ online   │─────────────────────▶│ eingefroren  │
        └─────────┘          └─────────┘◀─────────────────────└──────────────┘
                              │   ▲   │          Spieler joint
                       Stoppen│   │Start
                              ▼   │   │ Nachtpause beginnt
                           ┌─────────┐ └──────────────▶┌──────────────┐
                           │ offline  │                 │ Nachtpause   │
                           └─────────┘◀─────────────────└──────────────┘
                              │          Pause vorbei (→ Erstattung)
             Ablauf (ohne erfolgreiches Auto-Verlängern)
                              ▼
                        ┌────────────┐  Reaktivieren   ┌─────────┐
                        │ archiviert │───────────────▶│ erstellt │
                        └────────────┘                 └─────────┘
                              │ Admin löscht Archiv
                              ▼
                          (gelöscht)
```
Zusätzliche Zustände: **abgestürzt** (nach 3 Abstürzen in 10 Min kein Auto-Neustart mehr, *Vorschlag*), **wird umgebaut** (Typ-/Versionswechsel), **wird wiederhergestellt** (Backup).

---

## 11. Backups im Schnecken-Tempo (ENTSCHIEDEN)

### 11.1 Methode: inkrementelle Schnappschüsse (*Vorschlag*)
- Werkzeug: `rsync` mit `--link-dest` (Hardlinks).
- Jedes Backup sieht aus wie eine **vollständige Kopie**, aber **unveränderte Dateien werden nicht erneut kopiert**, sondern nur verknüpft.
- Vorteile:
  - Nach dem ersten Backup werden nur **geänderte** Dateien kopiert → sehr wenig Arbeit, ideal für Schnecken-Tempo.
  - Keine Komprimierung nötig → kaum CPU.
  - Wiederherstellen = Ordner zurückkopieren, einfach und zuverlässig.
  - Löschen alter Backups löscht nur Dateien, die sonst nirgends mehr gebraucht werden.

### 11.2 Drosselung (ENTSCHIEDEN: „Schnecken-Tempo, keine Belastung“)
- Nur **ein** Backup gleichzeitig, Server nacheinander.
- `nice -n 19` (niedrigste CPU-Priorität) und `ionice -c 3` (Festplatte nur, wenn sonst nichts passiert).
- **CPU-Deckel** über systemd: `systemd-run --scope -p CPUQuota=10% …` (Wert = Schnecken-Stufe, *Vorschlag* 10 %).
- **Festplatten-Deckel**: `rsync --bwlimit=…` (z. B. 5 MB/s, *Vorschlag*).
- **02:00–06:00** Schnecken-Tempo.
- **Ab 06:00**, falls nicht fertig: Tempo auf die **Leise-Grenze** (Kapitel 7.4) anheben, bis fertig (ENTSCHIEDEN).

### 11.3 Konsistenz (Welt darf beim Kopieren nicht „halb gespeichert“ sein)
| Server-Zustand | Ablauf |
|---|---|
| **wach** | RCON `save-off` → `save-all flush` → kopieren → `save-on` |
| **eingefroren** | Der Server schreibt nichts, solange er schläft → **direkt kopieren, ohne aufzuwecken** (ENTSCHIEDEN). ⚠️ Beim Setup testen, ob vor dem Einfrieren gespeichert wird; sonst vorher kurz `save-all` beim Einschlafen (Hostly macht das, wenn der letzte Spieler geht). |
| **offline / Nachtpause** | direkt kopieren |
| Joint jemand während des Kopierens eines eingefrorenen Servers | Server wacht auf → Hostly schaltet auf „wach“-Ablauf um (save-off) bzw. bricht ab und versucht es später erneut |

### 11.4 Aufbewahrung (ENTSCHIEDEN)
- Älter als **7 Tage** → löschen, **wenn neuere existieren**.
- **Angepinnte** Backups (Admin) werden nie automatisch gelöscht.
- Vor einer Wiederherstellung wird der aktuelle Stand gesichert (*Vorschlag*).

### 11.5 Wiederherstellen
1. Server stoppen.
2. Aktuellen Stand sichern (*Vorschlag*).
3. Gewähltes Backup zurückkopieren (mit Leise-Grenze, nicht Schnecke – der User wartet).
4. Server starten.

---

## 12. Archiv & Reaktivieren (ENTSCHIEDEN)
- **Archivieren = Ordner verschieben** (`servers/<id>` → `archives/<id>`). Auf derselben Festplatte ist das **sofort** fertig und braucht **keine CPU** → leise.
- Container wird gelöscht → RAM und Tunnel-Platz frei.
- **Reaktivieren**: RAM- und Tunnel-Prüfung → Ordner zurückschieben → neuer Container mit gespeicherten Einstellungen → Start.
- **Download** (Archiv oder laufend): ZIP wird bei Bedarf erstellt, mit niedriger Priorität und Leise-Grenze; laufende Server vorher `save-all`.
- Archive bleiben **für immer** (ENTSCHIEDEN); Admin kann löschen.

---

## 13. Modrinth & CurseForge (ENTSCHIEDEN: nur diese beiden)

### 13.1 Modrinth
- Öffentliche API (`api.modrinth.com/v2`), kostenlos, kein Schlüssel nötig.
- ⚠️ **Eindeutiger User-Agent ist Pflicht** (z. B. `hostly/1.0`), sonst kann Modrinth Anfragen blockieren.
- ⚠️ Limit ca. **300 Anfragen pro Minute** → Hostly **speichert Suchergebnisse zwischen** (z. B. 10 Minuten) und fragt nur bei Bedarf.
- Installation über `itzg`: `MODRINTH_PROJECTS` (z. B. `fabric-api`, `lithium:<version>`, `datapack:terralith`) und `MODRINTH_DOWNLOAD_DEPENDENCIES=required` → Abhängigkeiten automatisch (ENTSCHIEDEN).
- Entfernt man ein Projekt aus der Liste, löscht `itzg` die Datei → für **Deaktivieren** verschiebt Hostly die Datei stattdessen selbst in `disabled/` und nimmt sie aus der Liste.

### 13.2 CurseForge
- Braucht einen **API-Schlüssel** aus der CurseForge-Developer-Konsole (`console.curseforge.com`). Laut Recherche bringt das `itzg`-Image bereits einen Schlüssel mit; für die **Suche in Hostly** brauchen wir trotzdem einen eigenen (OFFEN: beantragen).
- Installation über `CURSEFORGE_FILES`.
- ⚠️ Mods, deren Autoren automatische Downloads verbieten, kann `itzg` nicht laden → Hostly zeigt: „Diese Mod kann nicht automatisch installiert werden – bitte Support kontaktieren“ (Admin lädt sie manuell hoch).
- ⚠️ CurseForge-Abhängigkeiten werden von `itzg` **erkannt, aber nicht automatisch geladen** → Hostly löst sie selbst über die CurseForge-API auf und ergänzt die Liste.

### 13.3 Kompatibilitäts-Prüfung
- Jede Mod-Version hat Angaben zu **Minecraft-Versionen** und **Loader** (fabric, paper …). Hostly filtert danach.
- Beim Versionswechsel: für jede installierte Mod prüfen, ob es eine Version für die Ziel-Version gibt → „aktualisieren“ oder „deaktivieren“.

---

## 14. Modpack für Spieler (`.mrpack`, ENTSCHIEDEN)
- Format: ZIP mit `modrinth.index.json` (Liste der Dateien mit Download-Link und Prüfsummen) und optionalen `overrides/`.
- ⚠️ Jede Datei hat eine Angabe `env.client` / `env.server` (`required` / `optional` / `unsupported`). Hostly nimmt **nur Mods, die auf dem Client nötig oder sinnvoll sind**, reine Server-Mods (z. B. Performance-Server-Mods) bleiben draußen.
- Import mit einem Klick in **Modrinth App** oder **Prism Launcher**.
- Link teilbar: `https://hostly.<tailnet>.ts.net/modpack/<server-kürzel>.mrpack` (*Vorschlag*).
- ⚠️ CurseForge-Mods können in `.mrpack`-Dateien eventuell nicht als Download-Link stehen → Hinweis „Folgende Mods bitte manuell installieren“ (beim Bau prüfen).

---

## 15. Resourcepacks
- Minecraft braucht einen **direkten Download-Link** und die **SHA-1-Prüfsumme** der ZIP-Datei.
- Hostly speichert hochgeladene oder von Modrinth/CurseForge geladene Packs in `resourcepacks/`, berechnet SHA-1 und stellt sie unter `https://hostly.<tailnet>.ts.net/rp/<datei>` bereit.
- Gesetzt über `RESOURCE_PACK`, `RESOURCE_PACK_SHA1`, optional `RESOURCE_PACK_ENFORCE` (Pflicht-Pack, ab 1.17).
- Änderungen erst nach **Neustart** aktiv → Banner „Änderungen ausstehend“.
- *Vorschlag:* Größenlimit 100 MB pro Pack (Funnel-Bandbreite).

---

## 16. Status, Statistiken, öffentliche Serverliste

### 16.1 Datenquellen
| Daten | Quelle |
|---|---|
| online / offline | Docker-Zustand + Health-Check |
| eingefroren | Datei `/data/.paused` |
| Spieler online, MOTD, Ping | Server-List-Ping (Python-Bibliothek `mcstatus`) – **nur bei wachen Servern** |
| Join-Verlauf, Spielzeit | Protokoll: „`<Name> joined the game`“ / „`left the game`“ |
| RAM/CPU | `docker stats` (gelegentlich, nicht im Sekundentakt) |
| TPS | Paper: per RCON `tps`; andere: nicht verfügbar |

### 16.2 ⚠️ Regel gegen Aufwecken
- **Eingefrorener Server** → kein Ping. Anzeige: „0 Spieler · schläft 💤“, MOTD/Icon aus gespeicherten Einstellungen, Ping-Balken grau.
- **Wacher Server** → Ping höchstens alle 60 s, Ergebnis wird gespeichert und von Website/Serverliste nur gelesen.
- Ein Besucher der Website löst **nie** direkt eine Abfrage aus.

### 16.3 Öffentliche Serverliste (ENTSCHIEDEN)
- Nur Server mit „öffentlich“ = an (Standard aus).
- Darstellung wie im Minecraft-Multiplayer-Menü: Icon, Name, farbige MOTD (§-Codes werden in Farben umgewandelt), `Spieler/Max`, Ping-Balken, Adresse kopieren.

### 16.4 Statistiken (öffentlich über Kürzel, ENTSCHIEDEN)
*Vorschlag* Inhalt: Spieler jetzt / Höchstwert, Spieler-Verlauf (Grafik 24 h / 7 Tage), Gesamt-Spielzeit, häufigste Spieler, Verfügbarkeit (Uptime), Modell, Typ, Version, installierte Plugins/Mods.
**ENTSCHIEDEN:** **Jeder mit dem Kürzel sieht alle Statistiken, auch die Spielernamen.**

---

## 17. Server-Kürzel & `/code` (ENTSCHIEDEN)
- Kürzel: *Vorschlag* 6 Zeichen aus Kleinbuchstaben und Zahlen ohne verwechselbare Zeichen, eindeutig.
- **Im Spiel:**
  | Typ | Befehl | Umsetzung |
  |---|---|---|
  | Paper | `/code` | kleines Hostly-Plugin (wird automatisch installiert) |
  | Fabric | `/code` | kleiner Hostly-Mod (serverseitig, Spieler brauchen ihn nicht) |
  | Vanilla | `/trigger code` | Hostly-Datapack (eigene Befehle sind in Vanilla nicht möglich) |
- Ausgabe im Chat (nur für den Fragenden): „Server-Kürzel: `k7x2pq` – Statistiken auf hostly…/s/k7x2pq“ (anklickbar).
- *Vorschlag:* Datapack funktioniert auf **allen** Typen → als Rückfallebene immer mitinstallieren.

---

## 18. Datenmodell (Datenbank, *Vorschlag*)
Vereinfachte Tabellenübersicht (SQLite):

| Tabelle | Wichtige Felder |
|---|---|
| **users** | id, username (eindeutig), password_hash (Argon2id), is_admin, minecraft_name, minecraft_uuid, avatar_mode (eigen/minecraft), avatar_path, language (de/en), theme (dark/light), must_change_password, created_at, deleted_at |
| **sessions** | id, user_id, token_hash, created_at, last_seen, ip, user_agent |
| **login_attempts** | username, ip, success, created_at (für Sperre bei Fehlversuchen) |
| **coin_ledger** | id, user_id, amount (+/−), reason (code/kauf/verlängerung/erstattung/nachtpause/gewinnspiel/übertragung/admin), ref_type, ref_id, created_at, created_by |
| **codes** | id, code (eindeutig), coins (50–1000), max_uses, uses, expires_at, active, created_at |
| **code_redemptions** | code_id, user_id, created_at (eindeutig pro Code+User) |
| **giveaways** | id, title, coins_per_winner, winner_count, ends_at, drawn_at |
| **giveaway_entries** | giveaway_id, user_id (eindeutig), created_at, is_winner |
| **models** | id, name (Holz/Eisen/Diamant), ram_gb, max_players, price_per_day, cpu_limit |
| **promotions** | id, kind (rabatt/ram), percent, extra_ram_gb, model_ids, starts_at, ends_at |
| **tunnels** | id, name, playit_account, public_address, internal_ip, active |
| **servers** | id, owner_id, name, short_code, model_id, type, mc_version, status, tunnel_id, rented_until, paid_total, paid_days, discount_percent, extra_ram_gb, extra_ram_until, auto_renew, night_pause_start, night_pause_end, public_listed, motd, icon_path, whitelist_enabled, created_at, archived_at |
| **server_rentals** | id, server_id, kind (kauf/verlängerung/reaktivierung/upgrade/downgrade), days, price, discount_parts (Tage/Aktion), created_at |
| **server_extensions** | server_id, source (modrinth/curseforge/upload), project_id, version_id, kind (plugin/mod/datapack/resourcepack), enabled |
| **worlds** | id, server_id, folder_name, seed, level_type, active |
| **whitelist** | server_id, minecraft_name, uuid |
| **player_sessions** | server_id, minecraft_name, joined_at, left_at |
| **server_status** | server_id, online, paused, players_online, players_max, latency_ms, checked_at |
| **night_pause_log** | server_id, date, planned_hours, completed (ja/nein), refund_coins |
| **backups** | id, server_id, path, created_at, size_bytes, pinned, kind (täglich/vor-änderung/vor-wiederherstellung) |
| **waitlist** | user_id, model_id, created_at, notified_at |
| **notifications** | id, user_id, kind (ablauf/auto-verlängern-fehlgeschlagen/gewinn/platz-frei/absturz), text, read_at, created_at |
| **jobs** | id, kind (start/stop/…), server_id, status, payload, created_at, done_at, error |
| **settings** | key, value (z. B. maintenance_mode, quiet_cpu_limit, ram_reserve_gb) |
| **audit_log** | id, user_id, action, details, created_at (Admin-Aktionen, Käufe, Übertragungen) |

---

## 19. Coins: Buchhaltung ohne Fehler
- **Kontostand wird nie direkt gespeichert**, sondern ist immer die **Summe aller Buchungen** in `coin_ledger` (*Vorschlag*). So kann nichts „verschwinden“, und der Coin-Verlauf ist automatisch vollständig.
- Jede Aktion mit Coins (Kauf, Übertragung, Einlösen) läuft in **einer Datenbank-Transaktion**: entweder alles oder nichts.
- **Kein Minus-Kontostand:** Vor dem Abbuchen wird in derselben Transaktion geprüft.
- **Doppelklick-Schutz:** Jeder Kauf-Knopf bekommt eine einmalige Kennung → zweimal klicken bucht nur einmal.
- Code einlösen: eindeutige Regel „ein Code pro User“ direkt in der Datenbank (nicht nur im Programm) → auch bei gleichzeitigen Klicks sicher.
- Übertragung an anderen User = zwei Buchungen (− beim Sender, + beim Empfänger) in einer Transaktion.

---

## 20. Sicherheit
| Bereich | Maßnahme |
|---|---|
| Passwörter | **Argon2id** (Bibliothek `argon2-cffi`), nie im Klartext (ENTSCHIEDEN) |
| Login | Sperre nach mehreren Fehlversuchen pro Benutzername und IP (*Vorschlag*: 5 Versuche → 15 Min) |
| Sitzung | Cookie mit `HttpOnly`, `Secure`, `SameSite=Lax`; Sitzungs-Token nur als Hash gespeichert |
| Formulare | CSRF-Schutz (Token pro Formular) |
| Admin | Admin-Seiten serverseitig geprüft, nicht nur ausgeblendet |
| Docker | Nur der worker hat Docker-Zugriff; Minecraft-Container ohne Sonderrechte, keine Ports am Host |
| Windows | WSL-Automount aus (ENTSCHIEDEN): kein Zugriff auf `C:\` |
| Dateimanager | Nur innerhalb des Server-Ordners (Schutz gegen `../`-Tricks); geschützte Dateien gesperrt (z. B. RAM-/Port-Einstellungen, `eula.txt`) |
| Uploads | Größenlimits; Bilder werden neu gespeichert (entfernt versteckte Inhalte); ZIP-Uploads auf „Zip-Slip“ geprüft |
| Eigene `.jar`-Dateien | User können keine hochladen (ENTSCHIEDEN: nur Modrinth/CurseForge, sonst Support) |
| Konsole | Befehlsfilter (Kapitel 8.2); RCON nur intern mit Zufallspasswort |
| MOTD/Namen | Eingaben werden geprüft und beim Anzeigen sicher dargestellt (kein Einschleusen von HTML) |
| Updates | `itzg`-Image und Hostly regelmäßig aktualisieren (Admin-Knopf, *Vorschlag*) |

---

## 21. Website-Technik (Oberfläche, *Vorschlag*)
- **Serverseitig erzeugte Seiten** (Jinja2) + **HTMX** für Live-Teile (Konsole, Status) → kein großes JavaScript-Projekt, kein Build-Schritt, schnell.
- **Design:** eigenes schlankes CSS mit Farb-Variablen für **Dark/Light Mode**; Standard folgt der System-Einstellung, umschaltbar, Wahl wird gespeichert.
- **Schrift:** normale, gut lesbare Systemschrift (ENTSCHIEDEN: keine Pixel-Schrift).
- **Bild-Zuschnitt** (Server-Icon, Profilbild): kleine JavaScript-Bibliothek *Cropper.js* (Zoom, Verschieben, quadratischer Rahmen).
- **MOTD-Editor:** Farbknöpfe + Live-Vorschau im Minecraft-Stil.
- **Konsole:** WebSocket, automatisches Scrollen, Eingabezeile.
- **Sprachen:** Textdateien `de.json` / `en.json`, Standard Deutsch (ENTSCHIEDEN).
- **PWA:** `manifest.json` + Service-Worker → „Zum Startbildschirm hinzufügen“ am Handy, App-Icon, Vollbild.
- **Handy zuerst:** Alle Seiten funktionieren auf dem Handy.

---

## 22. Schnittstellen (API-Übersicht, *Vorschlag*)
| Bereich | Beispiele |
|---|---|
| Auth | `POST /login`, `POST /register`, `POST /logout` |
| Account | `GET/POST /einstellungen`, `POST /einstellungen/passwort`, `POST /einstellungen/uebertragen` |
| Coins | `POST /code-einloesen`, `GET /coins/verlauf` |
| Kauf | `GET /kaufen`, `POST /kaufen/preis` (Live-Berechnung), `POST /kaufen` |
| Server | `GET /server`, `GET /server/{id}`, `POST /server/{id}/start|stop|restart|reload`, `POST /server/{id}/verlaengern|upgrade|downgrade|loeschen` |
| Konsole | `WS /server/{id}/konsole` |
| Dateien | `GET/POST /server/{id}/dateien/...` |
| Mods | `GET /server/{id}/mods/suche?q=`, `POST /server/{id}/mods` |
| Öffentlich | `GET /serverliste`, `GET /s/{kuerzel}`, `GET /modpack/{kuerzel}.mrpack`, `GET /rp/{datei}` |
| Admin | `/admin/dashboard`, `/admin/user`, `/admin/server`, `/admin/codes`, `/admin/gewinnspiele`, `/admin/aktionen`, `/admin/tunnel`, `/admin/backups`, `/admin/einstellungen` |

---

## 23. Admin-Dashboard: Datenquellen
| Anzeige | Quelle |
|---|---|
| RAM (WSL) | `/proc/meminfo` + Summe der Container-Grenzen |
| CPU | `/proc/stat` (Mittelwert über 1 Min) |
| Festplatte | Größe von `/srv/hostly` und Unterordnern (täglich berechnet, nicht live – spart Last) |
| Tunnel belegt/frei | Tabelle `tunnels` + `servers` |
| Server je Status | Tabelle `servers` + `server_status` |
| Coins | Summen aus `coin_ledger` |
| Letzte Ereignisse | `audit_log`, `jobs` (Fehler) |

---

## 24. Wartungsmodus technisch
- Einstellung `maintenance_mode` in `settings`.
- Alle Seiten zeigen für Nicht-Admins einen Hinweis; alle ändernden Aktionen sind gesperrt.
- Minecraft-Server laufen weiter (*Vorschlag*).
- Zeitgesteuerte Abläufe laufen weiter, damit nichts liegen bleibt (*Vorschlag*; Alternative: Ablaufzeiten um die Wartungsdauer verlängern).

---

## 25. Tests
- **Preisberechnung, Rabatte, Erstattungen, Nachtpause:** automatische Tests mit allen Beispielen aus dem Konzept (z. B. 2 Tage Holz = 19 Coins, 6 h Pause bei 35/Tag = 3 Coins).
- **Coins:** Tests für gleichzeitige Klicks, Minus-Schutz, Übertragungen.
- **Befehlsfilter:** Tests für alle Schreibweisen (`minecraft:stop`, `/RL`, …).
- **Docker-Abläufe:** Test-Server (Holz, Vanilla) erstellen, starten, einfrieren, archivieren, reaktivieren.
- **Oberfläche:** automatische Browser-Tests (Playwright) für Login, Kauf, Code einlösen.
- **Leise-Test:** beim Setup gemeinsam (Kapitel 7.4).

---

## 26. Risiken & Gegenmaßnahmen
| Risiko | Folge | Gegenmaßnahme |
|---|---|---|
| playit sperrt Accounts (2 Accounts) | Server nicht erreichbar | Besitzer kennt das Risiko; Rückfall: FRITZ!Box-Portfreigabe + DuckDNS |
| Windows beendet WSL / startet neu | Hostly kurz weg | `instanceIdleTimeout=-1`, Autostart-Aufgabe, worker holt Verpasstes nach |
| Windows-Update-Neustart während Backup | Backup unvollständig | Backup wird beim nächsten Lauf wiederholt (rsync macht dort weiter) |
| Stromausfall | Datenbank/Welten beschädigt | SQLite-WAL, tägliche DB-Sicherung, Welt-Backups, sauberes Speichern beim Stoppen |
| Festplatte voll | alles langsam, Fehler | Dashboard-Anzeige, Warnung ab 85 %, `sparseVhd` |
| Fabric-Mod verträgt Einfrieren nicht | Server hängt | pro Server Rückfall auf eingebaute Minecraft-Pause |
| Statusabfragen wecken Server | Lüfter | Regel aus Kapitel 16.2 |
| Modrinth/CurseForge-Limit | Suche geht kurz nicht | Zwischenspeicher, Hinweis „später erneut versuchen“ |
| Funnel-Bandbreite | große Downloads langsam | Größenlimits, Hinweis bei großen Welten |
| Besitzer nutzt PC stark | Minecraft langsamer | CPU-Grenzen, Windows-Programme haben Vorrang |

---

## 27. Offene technische Fragen
1. ~~RAM-Reserve in WSL~~ → 1,5 GB (entschieden)
2. ~~Java-Speicher~~ → Variante A (entschieden)
3. ~~CPU-Modell~~ → i5-12400T, siehe 6.3.
4. **CurseForge-API-Schlüssel** beantragen (für die Suche in Hostly).
5. ~~Statistik-Spielernamen~~ → für jeden mit Kürzel sichtbar (entschieden)
6. **Autostart ohne Anmeldung** beim Setup testen; falls unzuverlässig: automatische Windows-Anmeldung mit sofortiger Bildschirmsperre (siehe Setup-Anleitung).
