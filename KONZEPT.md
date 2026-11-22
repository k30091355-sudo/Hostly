# Hostly – Ausführliches Konzept

> **Status:** Brainstorming abgeschlossen bis auf wenige offene Punkte (siehe Kapitel 22).
> **Wichtig:** Das hier sind reine Notizen und Planung, **noch kein Code**.
> Programmiert wird erst, wenn der Besitzer ausdrücklich **„fang an“** sagt.
> **Prinzip:** klein anfangen und Schritt für Schritt erweitern (siehe Kapitel 21, Umsetzungs-Reihenfolge).

**Weitere Dokumente:**
- [`docs/TECHNIK.md`](docs/TECHNIK.md) – wie Hostly technisch gebaut wird (Aufbau, Datenbank, Backups, Sicherheit, Risiken)
- [`docs/SEITEN-UND-ABLAEUFE.md`](docs/SEITEN-UND-ABLAEUFE.md) – alle Seiten mit Skizzen und alle Abläufe Schritt für Schritt
- [`docs/SETUP-MINI-PC.md`](docs/SETUP-MINI-PC.md) – Einrichtungs-Anleitung für den Mini-PC (Windows 11 + WSL2)

Kennzeichnung in diesem Dokument:
- **ENTSCHIEDEN** – vom Besitzer festgelegt
- *Vorschlag* – von Claude vorgeschlagen, noch nicht ausdrücklich bestätigt
- **OFFEN** – muss noch geklärt werden

---

## Inhaltsverzeichnis
1. Idee in einem Satz
2. Grundvoraussetzungen
3. Begriffe
4. Technik & Aufbau
5. Name, Design, Sprache
6. Zugriff (eingeloggt / nicht eingeloggt)
7. Login & Account
8. Startseite & Navigation
9. Codes & Coins
10. Gewinnspiele
11. Server-Modelle & Kauf
12. Preise, Rabatte & Berechnungen
13. Nachtpause
14. „Meine Server“ – Server-Verwaltung für User
15. Plugins, Mods, Welten, Resourcepacks, Versionen
16. Backups
17. Ablauf, Archiv & Reaktivieren
18. User-Einstellungen
19. Admin-Bereich
20. Support, Wartungsmodus, Rechtliches
20a. Zusatz-Funktionen (Dateimanager, Absturz-Schutz, Vorlagen, Kürzel, Serverliste)
21. Umsetzungs-Reihenfolge (klein anfangen)
22. Offene Punkte
23. Bewusst (noch) nicht enthalten

---

## 1. Idee in einem Satz
**Hostly** ist eine eigene, kostenlose Minecraft-Hosting-Plattform auf einem Mini-PC: Spieler lösen **Codes** ein, erhalten dafür **Coins** und mieten damit **Minecraft-Server** in verschiedenen Stärken. Abgelaufene Server werden **archiviert** und können mit neuen Coins **reaktiviert** werden.

---

## 2. Grundvoraussetzungen (ENTSCHIEDEN)
- **Komplett kostenlos:** keine Abos, keine Einmalzahlungen, keine gekaufte Domain, keine kostenpflichtigen Dienste.
- **Hardware:** ein Mini-PC mit **16 GB RAM**.
  - CPU: **Intel Core i5-12400T** (6 Kerne / 12 Threads, 35 W Spar-Version → eher kühl und leise), Grafik Intel UHD 730
  - Festplatte: **477 GB**, davon 96 GB belegt (~380 GB frei)
- **Internet:** Telekom-Anschluss mit **FRITZ!Box**.
- Hostly läuft **vollständig auf dem Mini-PC** (Website, Datenbank, Minecraft-Server).
- **Windows bleibt installiert** (ENTSCHIEDEN): Der Besitzer will den Mini-PC nebenbei selbst nutzen. Hostly läuft im Hintergrund über **WSL2** (Linux in Windows), siehe 4.5.

---

## 3. Begriffe
| Begriff | Bedeutung |
|---|---|
| **Admin** | Der Besitzer von Hostly (genau eine Person). |
| **User** | Ein registriertes Konto auf der Hostly-Website. |
| **Coins** | Die interne Währung von Hostly. Gibt es nur über Codes, Gewinnspiele, Erstattungen und Übertragungen – nicht für echtes Geld. |
| **Code** | Ein vom Admin erzeugter Gutschein-Code, der in Coins umgewandelt wird. |
| **Modell** | Die Stärke eines Servers: Holz, Eisen oder Diamant. |
| **Server-Typ** | Die Server-Software: Vanilla, Paper oder Fabric. |
| **Miete** | Ein gekaufter Zeitraum für einen Server (in Tagen). |
| **Archiv** | Gespeicherte Daten eines abgelaufenen Servers, aus denen er reaktiviert werden kann. |
| **Backup** | Tägliche Sicherung eines laufenden Servers, die wiederhergestellt werden kann. |
| **Tunnel** | Eine öffentliche playit.gg-Adresse, über die Spieler einen Server erreichen. |
| **Nachtpause** | Ein vom User gewählter Zeitraum, in dem der Server automatisch aus ist – dafür gibt es Coins zurück. |

---

## 4. Technik & Aufbau

### 4.1 Gesamtbild
```
 Spieler-Browser / Handy (PWA)                 Minecraft-Client
            │                                          │
            ▼                                          ▼
   Tailscale Funnel (HTTPS)                    playit.gg-Tunnel
   https://hostly.<tailnet>.ts.net             (2 Accounts, je Server 1 Tunnel)
            │                                          │
┌───────────┼──────── Mini-PC: Windows 11 (16 GB) ─────┼───────────┐
│  Windows + eigene Programme (~4 GB)                  │           │
│  ┌────────┼──────────── WSL2 / Ubuntu (12 GB) ───────┼────────┐  │
│  │        ▼                                          │        │  │
│  │  ┌─────────────────────┐   Aufträge  ┌──────────────────┐  │  │
│  │  │ hostly-web           │───────────▶│ hostly-worker     │  │  │
│  │  │ Website + Login      │  (Datenbank)│ Zeitsteuerung,    │  │  │
│  │  │ Coins, Kauf, Admin   │            │ Backups, Docker   │  │  │
│  │  └─────────────────────┘            └────────┬─────────┘  │  │
│  │          SQLite-Datenbank                     │ steuert     │  │
│  │                                               ▼            │  │
│  │  ┌──────────────┐   ┌───────────────────────────────────┐  │  │
│  │  │ playit-Agent │──▶│ Minecraft-Server (itzg-Container)  │  │  │
│  │  │ 1 und 2      │   │ Vanilla / Paper / Fabric           │  │  │
│  │  └──────────────┘   └───────────────────────────────────┘  │  │
│  │  Speicher: Backups (7 Tage) · Archive (für immer)           │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```
Details: [`docs/TECHNIK.md`](docs/TECHNIK.md).

### 4.2 Bausteine
| Baustein | Lösung | Status |
|---|---|---|
| Betriebssystem | **Windows bleibt**, Hostly läuft in **WSL2 (Ubuntu)** mit Docker | ENTSCHIEDEN |
| Server-Verwaltung im Hintergrund | Hostly steuert Docker **direkt** mit dem kostenlosen Image `itzg/minecraft-server` statt Pelican (siehe 4.5) | ENTSCHIEDEN (Claude hat entschieden) |
| Eigene Website + API | Python (FastAPI) + SQLite, aufgeteilt in **hostly-web** (Website) und **hostly-worker** (Zeitsteuerung, Docker) | *Vorschlag* |
| Website-Oberfläche | Moderne Web-Oberfläche als **PWA** (auf dem Handy „Zum Startbildschirm hinzufügen“ → wirkt wie eine App, kein App Store nötig) | **ENTSCHIEDEN** (App oder Website, Hauptsache kostenlos) |
| Website von außen erreichbar | **Tailscale Funnel** | **ENTSCHIEDEN** |
| Minecraft-Server von außen erreichbar | **playit.gg** mit 2 Accounts | **ENTSCHIEDEN** |
| Installation | Alles per **Docker Compose**, möglichst mit einem Befehl | *Vorschlag* |
| Plugin-/Mod-Quellen | **Modrinth** und **CurseForge** (APIs) | **ENTSCHIEDEN** |

> Hinweis: Der Ordner/Repo-Name ist `MC-Plugim`, das Produkt heißt **Hostly**.

### 4.3 Website-Erreichbarkeit: Tailscale Funnel (ENTSCHIEDEN)
- Kostenlos für private Nutzung, kein Abo.
- **Echtes HTTPS** (wichtig, damit Passwörter verschlüsselt übertragen werden).
- Keine Domain und keine Portfreigabe nötig.
- Adresse: `https://hostly.<tailnet-name>.ts.net`
  - `hostly` = Gerätename des Mini-PCs
  - `<tailnet-name>` = von Tailscale vergebener Name (aus Vorschlägen wählbar)
- Der Besitzer braucht einen **kostenlosen Tailscale-Account**; die Einrichtung erfolgt gemeinsam beim Start.
- Eine eigene Domain (z. B. `hostly.de`) kann später ohne Umbau nachgerüstet werden (kostet dann aber Geld).

Verglichene Alternativen (verworfen):
| Möglichkeit | Grund für Ablehnung |
|---|---|
| playit.gg für die Website | kein HTTPS, verbraucht einen Tunnel |
| Cloudflare Tunnel | feste Adresse nur mit gekaufter Domain |
| FRITZ!Box + DuckDNS | Portfreigabe nötig, eigene IP sichtbar |
| GitHub Pages | nur statische Seiten, kein Login/keine Datenbank |

### 4.4 Minecraft-Erreichbarkeit: playit.gg (ENTSCHIEDEN)
- Kostenloser playit-Plan erlaubt nur ca. 3–4 Tunnel pro Account → Besitzer nutzt **2 Accounts**.
  - Hinweis (vom Besitzer zur Kenntnis genommen): Mehrere Accounts können gegen die playit-Regeln verstoßen; Risiko einer Sperre.
- Der **Besitzer erstellt die Tunnel selbst** und trägt sie im Admin-Bereich ein:
  - öffentliche Adresse (z. B. `abc-def.joinmc.link` oder `xyz.ply.gg:12345`)
  - zugehöriger lokaler Port auf dem Mini-PC
  - zu welchem playit-Account der Tunnel gehört (zur Übersicht)
- Hostly **weist jedem neuen oder reaktivierten Server automatisch einen freien Tunnel zu**.
- Ist **kein Tunnel frei** → „Kauf aktuell nicht möglich“ (zusätzlich zur RAM-Prüfung, siehe 11.3).
- Bei Ablauf/Archivierung/Löschung wird der Tunnel wieder **frei**.
- Admin-Dashboard zeigt: Tunnel **belegt / frei**.
- Fallback für später: Portfreigabe in der FRITZ!Box + DuckDNS (Telekom hat sehr wahrscheinlich eine öffentliche IPv4).
- Warum kein gemeinsamer Proxy (Velocity)? Vanilla-Server können nicht hinter einem Velocity-Proxy laufen.

---

### 4.5 Betrieb unter Windows (ENTSCHIEDEN: Windows bleibt)
- Hostly läuft in **WSL2** (Ubuntu in Windows) mit **Docker**.
- **ENTSCHIEDEN:** Statt Pelican steuert Hostly die Server **direkt über Docker** mit dem kostenlosen Image **`itzg/minecraft-server`**:
  - kann Vanilla, Paper, Fabric, Versionen wählen
  - lädt Mods/Plugins direkt von **Modrinth und CurseForge**
  - setzt MOTD, Icon, Whitelist, OPs, max. Spieler, RAM per Einstellung
  - Konsole über RCON
  - weniger Teile, die unter WSL2 Probleme machen könnten
- **Windows 11** (normal/Home)
- **RAM-Grenze für WSL2** per `.wslconfig`: **12 GB für Hostly** (ENTSCHIEDEN), ~4 GB bleiben für Windows
  - Reserve innerhalb dieser 12 GB: **1,5 GB** (ENTSCHIEDEN) → ca. 10,5 GB für Minecraft, z. B. 4× Holz oder 2× Diamant + 1× Holz
- **Autostart:** Hostly startet nach jedem Windows-Neustart automatisch, auch ohne Anmeldung (Windows-Aufgabenplanung)
- **Windows-Updates:** Nutzungszeit einstellen, damit Neustarts nachts passieren; Hostly startet danach selbst wieder
- **Energieoptionen:** Ruhezustand/Standby aus, damit der PC nie einschläft
- Virtualisierung muss im BIOS aktiviert sein (meist schon an)
- **Datensicherheit Windows:** keine Neuinstallation, Windows-Dateien bleiben unberührt; in WSL2 wird der automatische Zugriff auf Windows-Laufwerke (`/mnt/c` usw.) **abgeschaltet**; Container bekommen keinen Zugriff auf Windows-Dateien
- Hinweis: Wenn der Besitzer den PC stark nutzt (z. B. Spiele), können die Minecraft-Server langsamer werden

### 4.6 Leise im Leerlauf (ENTSCHIEDEN: keine Lüftergeräusche, wenn nichts los ist)
- **Auto-Pause (ENTSCHIEDEN, Besitzer: „super“):** Ist kein Spieler auf einem Server, wird er nach kurzer Zeit eingefroren (Funktion von `itzg/minecraft-server`) → fast 0 % CPU. Beim Joinen wacht er automatisch auf (dauert 1–2 Sekunden).
- **CPU-Grenze pro Server** (Docker), damit kein Server die CPU dauerhaft voll auslastet.
- **Backups nur nachts zwischen 02:00 und 06:00 Uhr**, im **„Schnecken-Tempo“** (ENTSCHIEDEN: so langsam wie möglich, keine spürbare Belastung):
  - immer nur **ein Backup gleichzeitig**, Server nacheinander
  - niedrigste CPU- und Festplatten-Priorität (`nice 19`, `ionice idle`)
  - nur **1 CPU-Kern** und zusätzlich stark gedrosselt (z. B. max. 10–20 % eines Kerns)
  - Lese-/Schreibgeschwindigkeit begrenzt
  - **keine oder nur ganz leichte Komprimierung**
  - Backups schlafender (eingefrorener) Server ohne sie aufzuwecken
  - **Nicht bis 06:00 fertig → ab 06:00 „normales“ Tempo**, bis das Backup fertig ist – aber weiterhin **so, dass der Lüfter nicht angeht** (ENTSCHIEDEN):
    - CPU-Nutzung bleibt unter einer **„Leise-Grenze“** (z. B. max. 1 Kern zu ~50 %), weiterhin ein Backup nach dem anderen, niedrigste Priorität
    - Die genaue Leise-Grenze wird beim Setup **gemeinsam ausprobiert** (Last langsam erhöhen, bis der Lüfter hörbar wird → knapp darunter einstellen)
    - Optional: Wenn Windows die CPU-Temperatur liefert, wird bei steigender Temperatur automatisch wieder gebremst
- **Windows-Energieoptionen:** max. Prozessorleistung z. B. 90–99 % → Turbo aus, deutlich kühler und leiser, kaum Leistungsverlust.
- Hostly-Website selbst verbraucht im Leerlauf praktisch nichts.
- Hinweis: Wenn Spieler online sind oder der Besitzer den PC stark nutzt, kann der Lüfter hörbar werden.

## 5. Name, Design, Sprache (ENTSCHIEDEN)
- **Name:** Hostly
- **Stil:** modern und clean, **normale Schrift** (keine Pixel-/Minecraft-Schrift)
- **Dark Mode und Light Mode**, umschaltbar
- **Sprachen:** **Deutsch (Standard)** und Englisch

---

## 6. Zugriff (ENTSCHIEDEN)
**Ohne Login** darf man alles **ansehen**:
- Startseite
- Modelle, Preise, Vergleichstabelle
- Rabatte / Aktionen
- Gewinnspiele

**Ohne Login** darf man **nichts tun**: nicht kaufen, keinen Code einlösen, nicht an Gewinnspielen teilnehmen.
- Klickt man auf eine solche Aktion → Weiterleitung zum Login.

**Nur eingeloggt** erreichbar: Meine Server, Einstellungen, Coin-Verlauf, Code einlösen usw.
- Wer ohne Login einen dieser Bereiche aufruft, wird zum Login weitergeleitet.

**Nur Admin** erreichbar: Admin-Bereich.

---

## 7. Login & Account

### 7.1 Registrierung (ENTSCHIEDEN)
- **Benutzername + Passwort**
- Keine E-Mail-Adresse (E-Mail-Funktionen sind vorerst komplett weggelassen).

### 7.2 Sicherheit (ENTSCHIEDEN: „sicher gespeichert“)
- Passwörter werden mit **Argon2 gehasht**, **niemals im Klartext** gespeichert.
- **Auch der Admin kann Passwörter nicht sehen** (bewusste Entscheidung aus Sicherheits- und Datenschutzgründen).
- *Vorschlag:* Begrenzte Fehlversuche beim Login (Schutz gegen Durchprobieren), z. B. kurze Sperre nach mehreren Fehlversuchen.
- *Vorschlag:* Mindestlänge für Passwörter (z. B. 8 Zeichen).

### 7.3 Passwort ändern (ENTSCHIEDEN)
- In den Einstellungen: **altes Passwort + neues Passwort**.

### 7.4 Passwort vergessen (ENTSCHIEDEN)
- Auf der Login-Seite steht: **„Passwort vergessen? Schreib eine E-Mail an k3009135@gmail.com“**
- Der Admin öffnet den User im Admin-Bereich und klickt **„Passwort zurücksetzen“** → Hostly erzeugt ein **zufälliges neues Passwort**, das der Admin kopiert und dem User schickt.
- *Vorschlag:* Der User muss das zufällige Passwort beim nächsten Login ändern.

### 7.5 Später nachrüstbar
- E-Mail hinterlegen, Bestätigungsmail, Passwort-Reset per E-Mail-Code (wurde besprochen, aber vorerst gestrichen; Gmail-SMTP wäre die kostenlose Lösung, Resend scheidet ohne eigene Domain aus).

---

## 8. Startseite & Navigation (ENTSCHIEDEN)

### 8.1 Startseite
- **Groß hervorgehoben:**
  - aktuelle **Rabatte / Aktionen** (Rabatt-Wochen, RAM-Aktionen)
  - laufende **Gewinnspiele** (mit Teilnehmen-Knopf)
- **Knöpfe:**
  - **„Code einlösen“** (öffnet die Code-Eingabe)
  - **„Server kaufen“** (öffnet das Kauf-Menü)
  - nicht eingeloggt: **„Login“**
  - eingeloggt: **„Meine Server“**
- **Warnungen** (nur eingeloggt):
  - **Ablauf-Warnung**: immer auf der Startseite, ab **3 Tage vor Ablauf** eines Servers
  - **Auto-Verlängern fehlgeschlagen** (zu wenig Coins)
  - Gewinnspiel gewonnen (Meldung)
- *Vorschlag:* Coin-Stand des Users sichtbar (z. B. oben in der Leiste).

### 8.2 Navigation: Dropdown-Menü rechts oben
- **Eingeloggt:** Meine Server · Server kaufen · Code einlösen · Gewinnspiele · Einstellungen · (Admin-Bereich, nur Admin) · Support · Abmelden
- **Nicht eingeloggt:** Login · Account erstellen

---

## 9. Codes & Coins (ENTSCHIEDEN)

### 9.1 Code-Format
- **16 Zeichen**, Zahlen und **Kleinbuchstaben**, in 4er-Gruppen mit Bindestrich:
  - Beispiel: `1234-jsh8-9hs2-34kl`
- Werden **zufällig** erzeugt.
- *Vorschlag:* verwechselbare Zeichen (z. B. `0`/`o`, `1`/`l`) weglassen, damit Abtippen leichter ist.

### 9.2 Code erstellen (nur Admin)
Im Erstell-Panel einstellbar:
| Einstellung | Werte |
|---|---|
| Coins | **50 bis 1000** |
| Wie oft gültig | Anzahl Einlösungen insgesamt (z. B. 1× oder 20×) |
| Ablaufdatum | optional |

- Nach dem Erstellen wird der Code angezeigt, mit **Kopieren-Knopf**.
- *Vorschlag:* mehrere Codes auf einmal erzeugen (z. B. „10 Codes à 100 Coins“).

### 9.3 Code-Übersicht (nur Admin)
- Liste **aller Codes** mit:
  - Status: aktiv / aufgebraucht / deaktiviert / abgelaufen
  - Einlösungen, z. B. `3 / 20`
  - Coins, Ablaufdatum, Erstelldatum
- Aktionen:
  - **Anzahl (wie oft gültig) bearbeiten**
  - **Deaktivieren** und wieder aktivieren
  - Kopieren

### 9.4 Code einlösen (User)
- Eingabefeld + „Einlösen“.
- Regeln:
  - Jeder User darf **denselben Code nur einmal** einlösen – auch wenn er mehrfach gültig ist.
  - Meldungen:
    - ✅ „+100 Coins gutgeschrieben“
    - ❌ **„Code bereits eingelöst“** (dieser User hat ihn schon benutzt)
    - ❌ „Code ungültig“ / „Code abgelaufen“ / „Code aufgebraucht“ / „Code deaktiviert“
- *Vorschlag:* Groß-/Kleinschreibung und fehlende Bindestriche bei der Eingabe tolerieren.

### 9.5 Woher Coins kommen / wohin sie gehen
| Plus | Minus |
|---|---|
| Code eingelöst | Server gemietet |
| Gewinnspiel gewonnen | Server verlängert / reaktiviert |
| Nachtpausen-Erstattung | Modell-Upgrade |
| Rückerstattung (Löschen, Downgrade) | Coins an anderen User übertragen |
| Übertragung von anderem User | |
| Admin-Gutschrift *(Vorschlag)* | Admin-Abzug *(Vorschlag)* |

Alles erscheint im **Coin-Verlauf** des Users (siehe 18).

---

## 10. Gewinnspiele (ENTSCHIEDEN)

### 10.1 Erstellen (nur Admin)
| Einstellung | Beschreibung |
|---|---|
| Coins pro Gewinner | wie viele Coins jeder Gewinner bekommt |
| Anzahl Gewinner | wie viele Gewinner gezogen werden |
| Laufzeit | in Tagen |
| *Vorschlag:* Titel/Beschreibung | Text, der auf der Startseite angezeigt wird |

### 10.2 Teilnahme (User)
- Knopf **„Teilnehmen“** auf der Startseite bzw. Gewinnspiel-Seite.
- **Einmal pro Konto**.
- Nicht eingeloggt → Knopf sichtbar, führt zum Login.

### 10.3 Auslosung
- Am Ende der Laufzeit **automatische Zufallsziehung**.
- Coins werden **direkt gutgeschrieben**.
- Gewinner bekommen eine **Meldung auf der Website** (keine E-Mail).
- *Vorschlag:* Gibt es weniger Teilnehmer als Gewinner, gewinnen alle Teilnehmer.

---

## 11. Server-Modelle & Kauf

### 11.1 Modelle (ENTSCHIEDEN)
| Modell | RAM | Max. Spieler | Preis pro Tag |
|---|---|---|---|
| **Holz** | 2 GB | 3 | 10 Coins |
| **Eisen** | 3 GB | 7 | 30 Coins |
| **Diamant** | 4 GB | 15 | 50 Coins |

- Das Spieler-Limit wird automatisch in der Server-Konfiguration gesetzt (`max-players`).
- *Vorschlag:* CPU-Anteil pro Modell festlegen, sobald das CPU-Modell bekannt ist.

### 11.2 Server-Typen (ENTSCHIEDEN)
- **Vanilla**, **Paper**, **Fabric** – der User wählt beim Kauf.
- Wechsel später erlaubt (siehe 15.6).

### 11.3 Verfügbarkeits-Prüfung (ENTSCHIEDEN)
- **Kein festes Limit** an Servern.
- Vor jedem Kauf/jeder Reaktivierung/jedem Upgrade prüft Hostly:
  1. **RAM:** Gerechnet wird mit der Container-Grenze (Modell-RAM + 0,5 GB). Nach dem Start müssen innerhalb der 12 GB von WSL noch **mindestens 1,5 GB frei** bleiben (Windows behält seine ~4 GB außerhalb).
     - Ca. 10,5 GB nutzbar → z. B. 4× Holz (je 2,5 GB) oder 2× Diamant (je 4,5 GB) + 1× Holz.
     - RAM-Aktionen (+1 GB) werden mitgerechnet.
  2. **Tunnel:** Es muss ein **freier playit-Tunnel** vorhanden sein.
- Ist eine Bedingung nicht erfüllt → **„Kauf aktuell nicht möglich“**.

### 11.4 Kauf-Menü (ENTSCHIEDEN)
1. **Vergleichstabelle** aller Modelle (RAM, max. Spieler, Preis pro Tag, aktuelle Aktionen).
2. Modell wählen.
3. Server-Typ wählen (Vanilla / Paper / Fabric).
4. Anzahl Tage frei wählen.
5. Optional: Nachtpause einstellen (Zeitraum).
6. *Vorschlag:* Servernamen eingeben.
7. **Preis wird live angezeigt:** Originalpreis durchgestrichen, Rabatt in %, Endpreis.
8. Kaufen → Coins werden **einmal komplett abgebucht** → Server wird erstellt.

---

## 12. Preise, Rabatte & Berechnungen

### 12.1 Grundregeln (ENTSCHIEDEN)
- Coins werden beim Kauf **einmal komplett abgebucht**.
- Mietdauer **frei wählbar**, **kein Maximum**.
- **Immer abrunden** (zugunsten des Spielers).
  - **Ausnahme:** Nachtpausen-Erstattung wird **aufgerundet**.
- Rabatte werden dem User **angezeigt** (durchgestrichener Originalpreis + Endpreis).

### 12.2 Rabatt-Arten
| Rabatt | Regel | Status |
|---|---|---|
| **Tage-Rabatt** | Anzahl Tage = Rabatt in %. 1 Tag = 0 %, 2 Tage = 2 %, 15 Tage = 15 %, 30 Tage = 30 %, **max. 50 %** (ab 50 Tagen) | ENTSCHIEDEN |
| **Rabatt-Wochen / Aktionen** | Admin legt Prozent, Zeitraum und Modelle fest. Gilt für **neue Mieten und Verlängerungen** | ENTSCHIEDEN |
| **Nachtpause** | 1 % pro Stunde, max. 15 %. Wird **nachträglich erstattet** (siehe 13) | ENTSCHIEDEN |
| **RAM-Aktion** | Kein Preisrabatt, sondern z. B. +1 GB RAM für ein Modell (siehe 12.5) | ENTSCHIEDEN |

- Rabatte werden **addiert** (z. B. 30 % + 10 % = 40 %).
- **Gesamtrabatt maximal 75 %.**

> Zu 1 Tag: Die Regel „Tage = Prozent“ ergibt eigentlich 1 % bei 1 Tag; besprochen und in der Tabelle festgehalten wurde 1 Tag = 0 %. *Vorschlag:* so lassen (Rabatt erst ab 2 Tagen).

### 12.3 Formel für den Mietpreis
```
tage_rabatt   = (tage >= 2) ? min(tage, 50) : 0          // in %
aktion        = Summe aktiver Rabatt-Aktionen für dieses Modell  // in %
gesamt_rabatt = min(tage_rabatt + aktion, 75)
preis         = abrunden( tage × preis_pro_tag × (1 − gesamt_rabatt / 100) )
```

### 12.4 Preisbeispiele (ohne Aktionen, abgerundet)
| Tage | Rabatt | Holz | Eisen | Diamant |
|---|---|---|---|---|
| 1 | 0 % | 10 | 30 | 50 |
| 2 | 2 % | 19 | 58 | 98 |
| 7 | 7 % | 65 | 195 | 325 |
| 15 | 15 % | 127 | 382 | 637 |
| 30 | 30 % | 210 | 630 | 1050 |
| 50 | 50 % | 250 | 750 | 1250 |
| 100 | 50 % | 500 | 1500 | 2500 |

Beispiel mit Aktion: Diamant, 30 Tage, Rabatt-Woche 20 % → 30 % + 20 % = 50 % → 30 × 50 × 0,5 = **750 Coins**.
Beispiel mit Deckel: Diamant, 60 Tage (50 %) + Aktion 30 % = 80 % → gedeckelt auf **75 %** → 60 × 50 × 0,25 = **750 Coins**.

### 12.5 RAM-Aktionen (ENTSCHIEDEN)
- Admin legt fest: Modell (z. B. Eisen), Extra-RAM (z. B. +1 GB), Zeitraum.
- Gilt **nur für neue Mieten**, die **während der Aktion** gekauft werden.
- Der Extra-RAM gilt **nur während der Aktion**; danach fällt der Server auf den normalen RAM des Modells zurück.
- Die RAM-Prüfung (11.3) rechnet den Extra-RAM mit ein.
- *Vorschlag:* Nach Ende der Aktion wird der RAM beim nächsten Neustart angepasst (Hinweis an den User).

### 12.6 Verlängern (ENTSCHIEDEN)
- Direkt im Server-Menü möglich, auch vor Ablauf.
- Die neue Zeit wird an die bestehende Restlaufzeit **angehängt**.
- Es gelten Tage-Rabatt (für die Verlängerungs-Tage) und Rabatt-Aktionen.

### 12.7 Upgrade (ENTSCHIEDEN)
- Man zahlt nur die **Differenz für die Resttage**, mit dem Rabatt der ursprünglichen Miete.
```
upgrade_preis = abrunden( resttage × (neuer_tagespreis − alter_tagespreis) × (1 − ursprünglicher_rabatt / 100) )
```
- Beispiel: noch 10 Tage Holz (0 % Rabatt) → Eisen: 10 × (30 − 10) = **200 Coins**.
- RAM-/Tunnel-Prüfung gilt auch hier.

### 12.8 Downgrade (ENTSCHIEDEN)
- Erlaubt, mit **anteiliger Rückerstattung der Differenz**:
```
erstattung = abrunden( resttage × (alter_tagespreis − neuer_tagespreis) × (1 − ursprünglicher_rabatt / 100) )
```
- *Vorschlag:* Hinweis, falls die installierten Mods/Plugins mit weniger RAM eventuell nicht mehr laufen.

### 12.9 Löschen mit Rückerstattung (ENTSCHIEDEN)
- **User löscht selbst:** anteilige Rückerstattung der Resttage.
- **Admin löscht:** wahlweise **mit** (anteilig) oder **ohne** Rückerstattung.
```
erstattung = abrunden( resttage × tatsächlich_bezahlter_tagespreis )
```
- *Vorschlag:* Es zählen nur **volle** Resttage (angebrochener Tag wird nicht erstattet).

---

## 13. Nachtpause (ENTSCHIEDEN)

### 13.1 Was ist das?
Der User legt einen täglichen Zeitraum fest (z. B. 01:00–08:00), in dem der Server **automatisch ausgeschaltet** ist. Dafür bekommt er Coins zurück.

### 13.2 Regeln
- Einstellbar **beim Kauf** oder **jederzeit später** in den Server-Optionen.
- Zeitraum **frei wählbar**, **maximal 15 Stunden**.
- **1 % pro Stunde** Pause (z. B. 7 Stunden = 7 %).
- Der Rabatt wird **nicht im Voraus abgezogen**:
  - Nach **jeder vollständig beendeten Nachtpause** bekommt der User die Coins für diese Nacht **zurückerstattet**.
- **Jederzeit an- und ausschaltbar**, keine Nachzahlung.
- Startet der User den Server **während der Pause** manuell → **keine Erstattung** für diese Nacht.
- Berechnung vom **tatsächlich bezahlten Tagespreis**, **aufgerundet**.
- Der **Gesamtrabatt von 75 %** darf nicht überschritten werden: Liegt die Miete schon nahe am Deckel, wird die Nachtpausen-Erstattung entsprechend gekürzt.
- *Vorschlag:* Zeitzone ist deutsche Zeit (Europe/Berlin).
- *Vorschlag:* Kurz vor Beginn der Pause bekommen Spieler im Spiel eine Chat-Warnung.

### 13.3 Formel
```
bezahlter_tagespreis = bezahlter_gesamtpreis / gemietete_tage
pause_prozent        = min(pause_stunden, 15, 75 − bereits_genutzter_rabatt)   // nicht unter 0
erstattung_pro_nacht = aufrunden( bezahlter_tagespreis × pause_prozent / 100 )
```

### 13.4 Beispiel
- Diamant, 30 Tage, 30 % Rabatt → 1050 Coins → 35 Coins/Tag.
- Nachtpause 6 Stunden → 6 % von 35 = 2,1 → **aufgerundet 3 Coins pro Nacht**.

---

## 14. „Meine Server“ – Server-Verwaltung für User (ENTSCHIEDEN)

### 14.1 Übersicht
- Liste **aller eigenen Server**, auch offline, abgelaufen und archiviert.
- Pro Server sichtbar:
  - Name, Modell, Server-Typ
  - **Status:** online / offline / Nachtpause / abgelaufen / archiviert
  - Restlaufzeit
  - *Vorschlag:* Server-Adresse mit Kopieren-Knopf, Spieler online (z. B. 2/7)

### 14.2 Steuerung
- Knöpfe: **Starten · Stoppen (offline nehmen) · Neustarten · Reload**
- Die Mietzeit **läuft weiter**, auch wenn der Server offline ist.

### 14.3 Konsole
- Live-Konsole **sehen** und **Befehle eingeben** (z. B. `op`, `whitelist add`).
- In der Konsole **gesperrt:** `stop`, `restart`, `end`, `reload` – dafür gibt es die Knöpfe.

### 14.4 Verwaltung
- **Verlängern** (siehe 12.6)
- **Reaktivieren** (bei archivierten Servern, siehe 17)
- **Server-Typ festlegen/wechseln** (siehe 15.6)
- **Modell upgraden / downgraden** (siehe 12.7, 12.8)
- **Umbenennen**
- **Löschen** (mit anteiliger Rückerstattung, siehe 12.9)
- **Auto-Verlängern** an/aus (siehe 14.7)
- **Nachtpause** einstellen (siehe 13)

### 14.5 Darstellung in der Minecraft-Serverliste
- **MOTD** (Text in der Multiplayer-Liste) bearbeiten:
  - mit **Farben und Formatierung** (fett, kursiv usw.)
  - mit **Vorschau**, wie es in Minecraft aussieht
- **Server-Icon** hochladen:
  - **beliebige Bildgröße**
  - es erscheint ein **Rahmen**, der zeigt, was ins Icon kommt
  - **zoomen** und **verschieben** (hoch, runter, links, rechts)
  - Hostly erzeugt automatisch das **64×64-Pixel**-Icon für Minecraft

### 14.6 Spieler
- **Whitelist an/aus** und Spieler zur Whitelist **hinzufügen/entfernen**.
- **Spieler-Join-Verlauf:** wer war wann auf dem Server.
- Ist ein **Minecraft-Name** in den Einstellungen hinterlegt, bekommt der User auf eigenen Servern automatisch **OP** (siehe 18).

### 14.7 Auto-Verlängern (ENTSCHIEDEN)
- Pro Server in den Server-Optionen an/aus.
- Greift **am Tag des Ablaufs**.
- Verlängert **immer um 7 Tage**.
- Rabatte gelten (7 Tage = 7 % + aktive Aktionen).
- **Zu wenig Coins** → Server läuft normal ab und wird archiviert, Warnung auf der Startseite: „Auto-Verlängern fehlgeschlagen – zu wenig Coins“.

### 14.8 Download (ENTSCHIEDEN)
- **Welt** und **Server-Dateien** als ZIP herunterladen.
- **Jederzeit** möglich, auch bei laufenden Servern (Hostly speichert vorher automatisch mit `save-all`).
- Auch für archivierte Server.

---

## 15. Plugins, Mods, Welten, Resourcepacks, Versionen (ENTSCHIEDEN)
Alles im **Servereinstellungs-Menü**, Änderungen werden mit einem Neustart aktiv.

### 15.1 Quellen
- **Nur Modrinth und CurseForge**, Suche und Installation direkt in Hostly.
- Hinweis im Menü: **Eigene Dateien** (Plugins/Mods, die es dort nicht gibt) nur über den **Support** – der Admin lädt sie dann hoch.
- CurseForge benötigt einen **kostenlosen API-Schlüssel** (beantragt der Besitzer).
- Manche CurseForge-Mods verbieten Downloads über andere Seiten → können nicht automatisch installiert werden, Hostly zeigt einen Hinweis.

### 15.2 Was passt zu welchem Server-Typ?
| Server-Typ | Erweiterungen |
|---|---|
| Vanilla | Datapacks |
| Paper | Plugins (+ Datapacks) |
| Fabric | Mods (+ Datapacks) |

### 15.3 Installieren
- Suchen → „Installieren“.
- Hostly wählt automatisch die **passende Version** zur Minecraft-Version und zum Server-Typ.
- **Abhängigkeiten** werden automatisch mitinstalliert (z. B. Fabric API).

### 15.4 Aktivieren / Deaktivieren
- Schalter pro Mod/Plugin.
- Technisch: Datei wird in einen „deaktiviert“-Ordner verschoben, nichts wird gelöscht.

### 15.5 Versionen ändern
- **Minecraft-Version** des Servers ändern.
- **Versionen einzelner Mods/Plugins** ändern.
- **Vorab-Prüfung** bei Versionswechsel:
  - „12 Mods werden automatisch aktualisiert“
  - „2 Mods gibt es für diese Version nicht und werden deaktiviert“
- **Automatisches Backup** vor jedem Versionswechsel (Downgrades können Welten beschädigen).

### 15.6 Server-Typ wechseln
- Erlaubt (z. B. Paper → Fabric).
- Unpassende Plugins/Mods werden deaktiviert, die **Welt bleibt** erhalten.
- Automatisches Backup vorher.

### 15.7 Welten
- Welt als ZIP **hochladen**.
- **Neue Welt** erzeugen (Seed, Welttyp).
- Zwischen mehreren Welten **wechseln**.

### 15.8 Resourcepacks
- Hochladen oder von Modrinth/CurseForge auswählen.
- Hostly stellt die Datei selbst über die Website bereit und trägt **Link und Prüfsumme** automatisch in die Server-Konfiguration ein → Spieler bekommen das Pack beim Joinen.

### 15.9 Neustart nach Änderungen
- Statt sofort neu zu starten erscheint ein Banner: **„3 Änderungen ausstehend – Jetzt neu starten“**.
- Optional: **„Spieler warnen und in 1 Minute neu starten“** (Chat-Nachricht an alle Spieler).

### 15.10 Modpack für Spieler (Fabric)
- Problem: Bei Fabric-Servern brauchen Spieler viele Mods auch im eigenen Minecraft.
- Lösung: Knopf **„Modpack für Spieler herunterladen“** → Hostly erzeugt **eine Datei** mit allen nötigen Client-Mods in den richtigen Versionen.
- Import mit einem Klick in kostenlose Launcher wie **Modrinth App** oder **Prism Launcher**.
- Der Link kann an Freunde geschickt werden.

---

## 16. Backups (ENTSCHIEDEN)
- **Täglich automatisch** für jeden laufenden Server, **nur zwischen 02:00 und 06:00 Uhr im Schnecken-Tempo** (siehe 4.6).
- Zusätzlich automatisch **vor jedem Versions- oder Typwechsel**.
- Der User kann im Server-Menü ein Backup **wiederherstellen**.
- **Aufbewahrung:** Backups **älter als 7 Tage** werden automatisch gelöscht, **sofern neuere existieren**.
- Der Admin kann einzelne Backups **„behalten“** (anpinnen) → werden nie automatisch gelöscht.
- Der Admin kann Backups manuell löschen.
- Speicherverbrauch im Admin-Dashboard sichtbar.
- *Vorschlag:* Vor dem Wiederherstellen wird automatisch ein Backup des aktuellen Stands angelegt.

---

## 17. Ablauf, Archiv & Reaktivieren (ENTSCHIEDEN)

### 17.1 Ablauf-Reihenfolge
1. **3 Tage vorher:** Ablauf-Warnung auf der Startseite.
2. **Am Ablauftag:** Ist Auto-Verlängern an → Versuch, 7 Tage zu verlängern.
   - genug Coins → verlängert, fertig
   - zu wenig Coins → weiter mit 3., plus Warnung auf der Startseite
3. Server wird **gestoppt**.
4. Server-Daten werden als **Archiv** (`.tar.gz`) gespeichert (Welt, Plugins, Mods, Einstellungen).
5. Server-Container wird gelöscht → **RAM und Tunnel werden frei**.
6. Status: **archiviert**.

### 17.2 Archiv
- Archive werden **für immer** aufbewahrt.
- Der Admin kann alte Archive **manuell löschen**.
- Der User kann sein Archiv **herunterladen**.

### 17.3 Reaktivieren
- In „Meine Server“: **„Reaktivieren“** → Tage wählen → bezahlen (gleiche Preise/Rabatte wie Kauf).
- Prüfung von RAM und Tunnel (11.3). Man kann es versuchen; ist kein Platz → **„Aktuell nicht möglich“**, Server bleibt archiviert.
- Bei Erfolg: neuer Server wird erstellt, Archiv wird entpackt → **alles wieder wie vorher**.
- Neue Server-Adresse möglich (anderer Tunnel) → wird angezeigt.

---

## 18. User-Einstellungen (ENTSCHIEDEN)
| Einstellung | Beschreibung |
|---|---|
| **Passwort ändern** | altes + neues Passwort |
| **Benutzernamen ändern** | *Vorschlag:* muss eindeutig sein |
| **Minecraft-Name** | wird hinterlegt → automatisch OP auf eigenen Servern |
| **Profilbild** | eigenes Bild (mit Zuschneide-Rahmen wie beim Server-Icon) **oder** Minecraft-Kopf des hinterlegten Namens |
| **Coin-Verlauf** | Liste aller Einnahmen und Ausgaben mit Datum und Grund |
| **Coins übertragen** | **jederzeit** an andere User per Benutzername |
| **Server übertragen** | **jederzeit** an andere User per Benutzername |
| **Account löschen** | Server und Coins werden gelöscht; vorher können sie übertragen werden |
| **Sprache** | Deutsch (Standard) / Englisch |
| **Design** | Dark / Light Mode |

- *Vorschlag:* Account löschen und Übertragungen mit Passwort bestätigen.

---

## 19. Admin-Bereich (ENTSCHIEDEN)

### 19.1 Allgemein
- Genau **ein Admin** (der Besitzer).
- Der Admin kann zwischen **Admin-Ansicht** und **normaler User-Ansicht** umschalten.

### 19.2 Admin-Übersicht / Dashboard (sehr wichtig)
- **RAM:** belegt / frei / Reserve (1,5 GB in WSL)
- **CPU-Last**
- **Festplatte:** gesamt, frei, davon Backups und Archive
- **Tunnel:** belegt / frei
- **Server:** laufend / offline / Nachtpause / archiviert
- **User:** Anzahl, neue User
- **Coins:** im Umlauf, eingelöst, ausgegeben, erstattet
- **Aktive** Codes, Gewinnspiele, Aktionen
- **Letzte Ereignisse:** Käufe, Abläufe, Fehler

### 19.3 User-Menü
- Alle User sehen und bearbeiten.
- **Passwort zurücksetzen** → zufälliges Passwort erzeugen.
- *Vorschlag:* Coins gutschreiben/abziehen, User sperren.

### 19.4 Server-Menü
- Alle Server sehen, bearbeiten.
- **Löschen mit oder ohne Rückerstattung** (anteilig).

### 19.5 Weitere Verwaltung
- **Codes** (siehe 9)
- **Gewinnspiele** (siehe 10)
- **Rabatt-Wochen / Aktionen** (siehe 12.2)
- **RAM-Aktionen** (siehe 12.5)
- **Tunnel** eintragen/bearbeiten/entfernen (siehe 4.4)
- **Backups** anpinnen/löschen (siehe 16)
- **Archive** löschen (siehe 17)
- **Eigene Dateien** für User hochladen (Support-Fälle, siehe 15.1)
- **Wartungsmodus** (siehe 20.2)

---

## 20. Support, Wartungsmodus, Rechtliches

### 20.1 Support (ENTSCHIEDEN)
- Klick auf **„Support“** öffnet das E-Mail-Programm mit dem Empfänger **k3009135@gmail.com**.
- **Kein** vorausgefüllter Betreff/Text.

### 20.2 Wartungsmodus (ENTSCHIEDEN)
- Der Admin schaltet Hostly in den Wartungsmodus (z. B. für Updates).
- User sehen einen **Hinweis** und können nichts kaufen oder ändern.
- Der Admin kann weiterhin alles nutzen.
- *Vorschlag:* laufende Minecraft-Server laufen weiter; Abläufe werden nach der Wartung nachgeholt bzw. Restzeit nicht benachteiligt.

### 20.3 Rechtliches (ENTSCHIEDEN)
- **Impressum** und **Datenschutzerklärung** werden **vorerst weggelassen**.
- Können später als eigene Seiten nachgerüstet werden (Hinweis: bei öffentlichem Betrieb in Deutschland meist nötig).

---

## 20a. Zusatz-Funktionen (ENTSCHIEDEN)

### Dateimanager im Browser
- Dateien des Servers ansehen, bearbeiten (z. B. `server.properties`, Plugin-Configs), hochladen nur über Modrinth/CurseForge bzw. Support (siehe 15.1), löschen.
- *Vorschlag:* geschützte Dateien (z. B. `eula.txt`, RAM-/Port-Einstellungen) sind gesperrt, damit niemand Limits umgeht.

### Absturz-Schutz
- Stürzt ein Server ab → **automatischer Neustart**, Hinweis für den User in „Meine Server“.
- *Vorschlag:* Nach 3 Abstürzen in kurzer Zeit kein weiterer Auto-Neustart (Schleife verhindern), Hinweis mit Log-Auszug.

### „Benachrichtige mich, wenn Platz frei ist“
- Ist der Kauf nicht möglich (RAM/Tunnel voll), kann sich der User **vormerken**.
- Sobald wieder Platz ist → **Meldung auf der Website** (Startseite).
- *Vorschlag:* Wer zuerst vorgemerkt ist, wird zuerst benachrichtigt.

### Server-Vorlagen (Claude sucht gute aus)
Ein Klick → fertiger Server mit passenden Plugins/Mods. Erste Auswahl (*Vorschlag*, Verfügbarkeit auf Modrinth/CurseForge wird beim Bau geprüft):
| Vorlage | Typ | Inhalt |
|---|---|---|
| Vanilla pur | Vanilla | Nichts extra |
| Vanilla+ | Vanilla | Datapacks für mehr Komfort (z. B. Vanilla Tweaks: mehr Schlaf-Komfort, Kopf-Drops …) |
| Survival mit Freunden | Paper | EssentialsX (Homes, Teleport), LuckPerms (Rechte), CoreProtect (Grief-Schutz/Rückgängig) |
| Creative | Paper | WorldEdit, Plot-Plugin, Creative-Einstellungen |
| SkyBlock / OneBlock | Paper | BentoBox mit BSkyBlock bzw. AOneBlock |
| Performance-Vanilla | Fabric | Lithium, FerriteCore, Chunky (schneller, weniger RAM – gut für Holz) |
| Abenteuer | Fabric | Ausgewählte Content-Mods + Performance-Mods + Modpack für Spieler |

### Server-Kürzel & Statistiken
- Beim **Erstellen eines Servers** wird automatisch ein **Server-Kürzel** erzeugt (*Vorschlag:* 6 Zeichen, z. B. `k7x2pq`).
- Im **Dropdown-Menü**: Punkt **„Server-Statistiken“** → Kürzel eingeben → alle Statistiken des Servers werden angezeigt.
- **Im Spiel:** Befehl im Chat zeigt das Kürzel an.
  - Paper: `/code` (über ein kleines Hostly-Plugin)
  - Fabric: `/code` (über einen kleinen Hostly-Mod) oder Datapack
  - Vanilla: eigene Befehle sind dort technisch nicht möglich → `/trigger code` (über ein Hostly-Datapack)
- *Vorschlag* Statistiken: Spieler online (jetzt + Verlauf als Grafik), Spitzenwert, Gesamt-Spielzeit, meistgesehene Spieler, Uptime, Auslastung (RAM/CPU/TPS), Modell, Typ, Version, installierte Plugins/Mods.
- **Jeder** mit dem Kürzel darf die Statistiken sehen, **auch ohne Login** (ENTSCHIEDEN).

### Öffentliche Serverliste
- In Hostly eine Seite, die Server **so anzeigt wie im Minecraft-Multiplayer-Menü**:
  - Server-Icon, Name, MOTD/Beschreibung (mit Farben), Spieler online / max., Ping-Balken
  - Adresse zum Kopieren
- Der Server-Besitzer entscheidet **beim Erstellen** und **jederzeit später** in den Server-Optionen, ob sein Server öffentlich gelistet wird. **Standard: aus** (ENTSCHIEDEN).

## 21. Umsetzungs-Reihenfolge – klein anfangen (*Vorschlag*)
Erst wenn der Besitzer „fang an“ sagt. Jede Stufe ist für sich lauffähig.

| Stufe | Inhalt |
|---|---|
| **0 – Setup Mini-PC** | WSL2 + Ubuntu, Docker, Autostart, Energieoptionen (leise), Tailscale, playit |
| **1 – Grundgerüst** | Website mit Design (Dark/Light), Registrierung, Login, Einstellungen (Passwort, Benutzername), Admin-Rolle mit Umschalter |
| **2 – Coins** | Codes erstellen/verwalten, Code einlösen, Coin-Verlauf, Admin-User-Menü (Passwort zurücksetzen) |
| **3 – Erster Server** | Docker/`itzg/minecraft-server` anbinden, Modelle, Kauf-Menü mit Vergleich und Preisberechnung, RAM- und Tunnel-Prüfung, Tunnel-Verwaltung, Starten/Stoppen/Neustarten, Konsole |
| **4 – Ablauf** | Ablauf-Warnung, Archivieren, Reaktivieren, Verlängern, Auto-Verlängern, Löschen mit Erstattung |
| **5 – Komfort** | MOTD, Server-Icon-Zuschnitt, Whitelist, Join-Verlauf, Minecraft-Name/OP, Profilbild, Download |
| **6 – Aktionen** | Gewinnspiele, Rabatt-Wochen, RAM-Aktionen, Nachtpause, Upgrade/Downgrade, Übertragungen |
| **7 – Backups & Admin** | Tägliche Backups, Wiederherstellen, Admin-Dashboard, Wartungsmodus |
| **8 – Erweiterungen** | Modrinth/CurseForge, Versionen, Typwechsel, Welten, Resourcepacks, Modpack für Spieler |
| **8b – Zusatz** | Dateimanager, Absturz-Schutz, Vormerken, Vorlagen, Server-Kürzel & Statistiken, öffentliche Serverliste |
| **9 – Feinschliff** | Englische Übersetzung, PWA (App-Installation), Installations-Anleitung für den Mini-PC |

---

## 22. Offene Punkte
**Entschieden (Nov. 2026):**
1. **RAM-Reserve:** innerhalb der 12 GB für WSL bleiben **1,5 GB** frei (Windows hat seine 4 GB schon außerhalb) → ca. **10,5 GB für Minecraft-Server** (Claude hat entschieden).
2. **Java-Speicher: Variante A** – User bekommt den vollen beworbenen RAM, Container-Grenze = Modell-RAM + 0,5 GB, RAM-Prüfung rechnet mit der Container-Grenze (ENTSCHIEDEN).
3. **Statistiken:** **Jeder mit dem Kürzel sieht alles**, auch die Spielernamen (ENTSCHIEDEN).

**Noch zu bestätigen:**
- Alle mit *Vorschlag* markierten Punkte.

**Vom Besitzer nachzureichen:**
- **playit-Tunnel** (beim Setup)
- **Tailscale-Account** (kostenlos)
- **CurseForge-API-Schlüssel** (kostenlos, für die Suche in Hostly)

**Beim Setup zu testen:**
- Autostart von WSL ohne Windows-Anmeldung (sonst Plan B, siehe SETUP-MINI-PC.md Kapitel 8)
- Leise-Grenze (gemeinsam hinhören)
- Einfrieren mit Paper/Fabric (Watchdog-Einstellungen)

## 23. Bewusst (noch) nicht enthalten
- Geplante Aufgaben (zeitgesteuerte Befehle/Neustarts)
- Coins als Geschenk-Code verschenken (Übertragen per Benutzername gibt es aber)
- Freunde einladen / Werbe-Belohnung
- Discord-Benachrichtigungen
- Ankündigungen / News-Banner
- Zwei-Faktor-Login
- Bedrock-Unterstützung (Geyser)
- Freunde / Mitverwalter für Server (später)
- E-Mail-Funktionen (Bestätigungsmail, Passwort-Reset per Mail)
- „Überall abmelden“
- Standard-Nachtpause in den Einstellungen
- Impressum / Datenschutzerklärung (später)
- Eigene Domain
- Kauf von Coins mit echtem Geld
