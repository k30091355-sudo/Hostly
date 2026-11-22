# Hostly – Setup auf dem Mini-PC (Windows 11)

> 👉 **Für die Einrichtung bitte die ausführliche Anleitung benutzen: [ANLEITUNG.md](ANLEITUNG.md).** Diese Datei ist die technische Übersicht.

> Schritt-für-Schritt-Plan für die Einrichtung. Wird gemeinsam durchgegangen.
> **Windows bleibt installiert, keine Daten gehen verloren** (ENTSCHIEDEN).
> Befehle in `grauen Kästen` werden in **PowerShell (als Administrator)** oder im **Ubuntu-Fenster** eingegeben – steht jeweils dabei.
> Dauer gesamt: ca. 1–2 Stunden (je nach Internet).
>
> **Kurzfassung:** Kapitel 1–4 (WSL + Docker) → Kapitel 5 (Hostly starten, eigenen Account anlegen) →
> Kapitel 6 (Tailscale: Website von außen) → Kapitel 7 (playit: Minecraft von außen, Tunnel im Admin-Bereich eintragen) →
> Kapitel 8–9 (Autostart, leise) → Checkliste in Kapitel 11.

---

## 0. Vorher bereitlegen / nachschauen
- [ ] **CPU-Modell:** Einstellungen → System → Info → „Prozessor“
- [ ] **Freier Speicherplatz** auf `C:` (Explorer → Dieser PC)
- [ ] Windows-Updates einmal komplett installieren und neu starten (dann kommt in den nächsten Tagen weniger)
- [ ] Mini-PC per **LAN-Kabel** an der FRITZ!Box (stabiler als WLAN) – optional, aber empfohlen
- [ ] **Tailscale-Account** (kostenlos, z. B. mit Google/GitHub anmelden)
- [ ] **2 playit.gg-Accounts** (Zugangsdaten bereithalten)
- [ ] Optional: CurseForge-API-Schlüssel beantragen (kann ein paar Tage dauern)

---

## 1. Virtualisierung prüfen
1. `Strg + Shift + Esc` → Task-Manager → **Leistung** → **CPU**.
2. Rechts unten steht **„Virtualisierung: Aktiviert“**.
   - Falls **deaktiviert**: Im BIOS einschalten (Name meist „Intel VT-x“ / „SVM Mode“). → Gemeinsam machen.

---

## 2. WSL2 + Ubuntu installieren
**PowerShell als Administrator:**
```
wsl --install -d Ubuntu-24.04
```
- Danach **Neustart**.
- Ubuntu öffnet sich → **Linux-Benutzername und Passwort** festlegen (merken! Ist unabhängig vom Windows-Passwort).

Prüfen:
```
wsl --list --verbose
```
→ `Ubuntu-24.04` mit **VERSION 2**.

---

## 3. WSL2 einstellen (RAM, wach bleiben, leise)
**Datei** `C:\Users\<DeinName>\.wslconfig` anlegen (mit Editor), Inhalt:
```ini
[wsl2]
memory=12GB
processors=8
swap=4GB
networkingMode=mirrored
vmIdleTimeout=-1

[general]
instanceIdleTimeout=-1

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
```
(12 GB RAM, 8 Threads für Hostly; nie automatisch beenden; Festplatte schrumpft wieder. Kommentare bitte **nicht** in dieselbe Zeile schreiben.)

> Hinweis: Optionen und Werte werden beim Setup noch einmal mit der aktuellen Microsoft-Doku abgeglichen.

**Im Ubuntu-Fenster:** Datei `/etc/wsl.conf` bearbeiten:
```
sudo nano /etc/wsl.conf
```
Inhalt:
```ini
[boot]
systemd=true

[automount]
enabled=false

[interop]
appendWindowsPath=false
```
Danach in **PowerShell**:
```
wsl --shutdown
```
8 Sekunden warten, Ubuntu neu öffnen.

---

## 4. Ubuntu vorbereiten
**Ubuntu-Fenster:**
```
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl git rsync
```

### Docker installieren (Docker Engine direkt in Ubuntu, kostenlos)
```
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
```
Ubuntu-Fenster schließen und neu öffnen, dann prüfen:
```
docker run --rm hello-world
```

> Warum nicht Docker Desktop? Docker Engine direkt in Ubuntu braucht weniger RAM und läuft ohne Windows-Anmeldung zuverlässiger.

---

## 5. Hostly-Ordner anlegen
```
sudo mkdir -p /srv/hostly
sudo chown $USER:$USER /srv/hostly
cd /srv/hostly
git clone https://github.com/k30091355-sudo/Hostly.git app
```

### Hostly starten
Ordner anlegen (einmalig):
```
mkdir -p /srv/hostly/db /srv/hostly/uploads /srv/hostly/servers /srv/hostly/archives /srv/hostly/downloads /srv/hostly/backups /srv/hostly/db-backups
```
Starten:
```
cd /srv/hostly/app
docker compose up -d --build
```
- Es laufen zwei Teile: **hostly-web** (Website) und **hostly-worker** (startet/stoppt die Minecraft-Server).
- Test im Windows-Browser: `http://localhost:8000`
- **Sofort deinen eigenen Account erstellen** – der allererste Account wird automatisch Admin.
- Im Admin-Bereich → **Tunnel**: deine playit-Tunnel eintragen (ohne Tunnel kann niemand kaufen).
- Im Admin-Bereich → **Codes**: Codes erstellen und verteilen.
- Der erste Server-Kauf lädt einmalig das Minecraft-Image herunter (ca. 1 GB, dauert ein paar Minuten).
- Am Handy: Website öffnen → Browser-Menü → **„Zum Startbildschirm hinzufügen“** → Hostly ist wie eine App.

Falls nötig (Notfall-Befehle im Ubuntu-Fenster):
```
docker compose exec web python -m hostly.cli admin BENUTZERNAME
```
```
docker compose exec web python -m hostly.cli passwort BENUTZERNAME
```
(erster Befehl: jemanden zum Admin machen · zweiter: zufälliges neues Passwort, z. B. wenn du dein eigenes vergessen hast)

Logs ansehen (bei Problemen):
```
docker compose logs --tail 50 web worker
```

### Hostly aktualisieren (nach jeder neuen Stufe)
```
cd /srv/hostly/app
git pull
docker compose up -d --build
```
Die Datenbank und alle Server-Daten unter `/srv/hostly` bleiben dabei erhalten. Laufende Minecraft-Server laufen weiter.

---

## 6. Tailscale (Website von außen)
**Ubuntu-Fenster:**
```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=hostly
```
- Link öffnen, mit dem Tailscale-Account anmelden.
- In der Tailscale-Verwaltung (Browser): **HTTPS** und **Funnel** erlauben (wird beim ersten Funnel-Befehl angezeigt).
- Später, wenn Hostly läuft:
```
sudo tailscale funnel --bg 8000
```
→ Website unter `https://hostly.<tailnet>.ts.net`.

---

## 7. playit.gg (Minecraft von außen)
Die playit-Agenten laufen als Docker-Container und gehören zu Hostly (siehe `docker-compose.yml`).

**1. Schlüssel holen** (Browser, kostenloser playit-Account):
- Auf playit.gg einloggen → **Agents** → **Add Agent** → Art **Docker** wählen.
- Es wird ein **Secret Key** angezeigt (lange Zeichenkette) → kopieren.
- Für den zweiten playit-Account dasselbe nochmal (optional).

**2. Schlüssel eintragen** (Ubuntu-Fenster):
```
cd /srv/hostly/app
cp .env.example .env
nano .env
```
- Hinter `PLAYIT_SECRET_1=` den Schlüssel einfügen (Rechtsklick = Einfügen).
- Zweiter Account: Schlüssel bei `PLAYIT_SECRET_2=` einfügen und `COMPOSE_PROFILES=playit,playit2` schreiben.
- Speichern: `Strg+O`, `Enter`, dann `Strg+X`.
```
docker compose up -d
```

**3. Tunnel anlegen** (playit-Dashboard im Browser), für jeden Server-Platz einen:
- Typ: **Minecraft Java**
- Lokale Adresse: **`172.30.0.11`**, Port **`25565`** (nächster Tunnel: `172.30.0.12`, dann `.13` …)
- Die öffentliche Adresse (z. B. `blue-cat.joinmc.link`) notieren.

**4. In Hostly eintragen:** Admin-Bereich → **Tunnel** → Name, Account (1/2), öffentliche Adresse, interner Platz (Hostly schlägt den nächsten freien vor).

> Wie viele Tunnel? So viele, wie gleichzeitig Server laufen sollen. Mit 12 GB passen z. B. 4× Holz – also 4 Tunnel.

## 8. Autostart beim Hochfahren
**Ziel:** Nach jedem Windows-Neustart läuft Hostly wieder – auch ohne Anmeldung.

**Weg 1 (zuerst ausprobieren):** Windows-Aufgabenplanung
1. Aufgabenplanung öffnen → „Aufgabe erstellen“
2. Name: `Hostly starten`
3. **„Unabhängig von der Benutzeranmeldung ausführen“** + „Mit höchsten Privilegien“
4. Trigger: **Beim Start**
5. Aktion: Programm `wsl.exe`, Argumente: `-d Ubuntu-24.04 -u root -- sleep infinity`
6. Einstellungen: „Aufgabe beenden, falls länger als …“ **ausschalten**
→ Ubuntu startet und bleibt wach; systemd startet Docker, Tailscale und Hostly automatisch.

**Test:** PC neu starten, **nicht anmelden**, vom Handy aus die Hostly-Adresse öffnen.

⚠️ Laut Recherche klappt Weg 1 nicht auf jedem PC zuverlässig (Windows beendet WSL manchmal ohne angemeldeten Benutzer).

**Weg 2 (falls Weg 1 nicht klappt):** automatische Windows-Anmeldung + sofortige Bildschirmsperre
- Windows meldet sich nach dem Neustart selbst an (Microsoft-Tool „Autologon“), sperrt sofort den Bildschirm, und die Aufgabe startet „Bei Anmeldung“.
- Nachteil: Wer den PC physisch hat, kommt nach einem Neustart kurz an die Sitzung, bevor gesperrt wird. Wird gemeinsam abgewogen.

---

## 9. Windows leise und wach halten
**Energie:**
- Einstellungen → System → Netzbetrieb → **Bildschirm aus** nach 10 Min (okay), **Energiesparmodus: Nie**.
- Systemsteuerung → Energieoptionen → Energiesparplan ändern → Erweiterte Einstellungen →
  - Prozessorenergieverwaltung → **Maximaler Leistungszustand des Prozessors: 90–99 %** (Turbo aus → leiser, ENTSCHIEDEN „leise“)
  - Festplatte ausschalten: **Nie**
  - USB/Netzwerkkarte: Energiesparen aus (Geräte-Manager → Netzwerkadapter → Energieverwaltung)

**Windows-Update:**
- Einstellungen → Windows Update → Erweiterte Optionen → **Nutzungszeit manuell: 06:00–24:00** (max. 18 Stunden möglich).
- → Update-Neustarts passieren dann meist zwischen 0 und 6 Uhr. Hostly startet danach automatisch und holt verpasste Aufgaben nach.
- ⚠️ Wichtige Sicherheitsupdates können trotzdem außerhalb neu starten.

---

## 10. Leise-Betrieb (nichts zu tun)
Hostly ist von sich aus leise eingestellt – du musst nichts messen:
- Server ohne Spieler **frieren nach 5 Minuten ein** (praktisch 0 % CPU).
- **Backups** laufen nachts ab 2 Uhr mit niedrigster Priorität und gedrosselt (ca. 5 MB/s).
- Downloads (ZIP) werden mit niedrigster Priorität gepackt; der worker darf höchstens 1 CPU-Kern benutzen.

---

## 11. Abschluss-Checkliste
- [ ] `wsl --list --verbose` zeigt Ubuntu, VERSION 2
- [ ] `docker run --rm hello-world` klappt
- [ ] Windows-Laufwerke in Ubuntu **nicht** sichtbar (`ls /mnt` ist leer)
- [ ] Tailscale verbunden
- [ ] playit-Agenten geclaimt, Tunnel angelegt, Adressen notiert
- [ ] Autostart nach Neustart getestet (ohne Anmeldung)
- [ ] Energieoptionen gesetzt
- [ ] Hostly läuft (`docker compose ps` zeigt web, worker, playit), eigener Account ist Admin
- [ ] Tunnel im Admin-Bereich eingetragen, Test-Server gekauft und mit Minecraft verbunden
- [ ] Nutzungszeit 06:00–24:00 gesetzt

---

## 12. Rückgängig machen (falls gewünscht)
**PowerShell als Administrator:**
```
wsl --unregister Ubuntu-24.04
```
→ Ubuntu und alle Hostly-Daten darin sind weg, Windows ist wie vorher. (Vorher Daten sichern, falls gewünscht.)
