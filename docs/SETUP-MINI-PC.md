# Hostly – Setup auf dem Mini-PC (Windows 11)

> Schritt-für-Schritt-Plan für die Einrichtung. Wird gemeinsam durchgegangen.
> **Windows bleibt installiert, keine Daten gehen verloren** (ENTSCHIEDEN).
> Befehle in `grauen Kästen` werden in **PowerShell (als Administrator)** oder im **Ubuntu-Fenster** eingegeben – steht jeweils dabei.
> Dauer gesamt: ca. 1–2 Stunden (je nach Internet).

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
memory=12GB              # ENTSCHIEDEN: 12 GB für Hostly
processors=8             # i5-12400T hat 12 Threads, 4 bleiben für Windows
swap=4GB
networkingMode=mirrored  # Windows 11: einfacheres Netzwerk
vmIdleTimeout=-1         # VM nie automatisch beenden

[general]
instanceIdleTimeout=-1   # Ubuntu nie automatisch beenden

[experimental]
autoMemoryReclaim=gradual  # ungenutzten RAM langsam an Windows zurückgeben
sparseVhd=true             # virtuelle Festplatte schrumpft wieder, wenn Daten gelöscht werden
```
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
enabled=false            # ENTSCHIEDEN: kein Zugriff auf Windows-Laufwerke

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
git clone https://github.com/k30091355-sudo/hostly.git app
```

### Hostly starten (ab Stufe 1)
```
mkdir -p /srv/hostly/db
cd /srv/hostly/app
docker compose up -d --build
```
- Test im Windows-Browser: `http://localhost:8000`
- Auf der Website **sofort deinen eigenen Account erstellen**, dann im Ubuntu-Fenster zum Admin machen:
```
docker compose exec web python -m hostly.cli admin DEIN_BENUTZERNAME
```
- Eigenes Passwort vergessen? Neues zufälliges Passwort erzeugen:
```
docker compose exec web python -m hostly.cli passwort DEIN_BENUTZERNAME
```

### Hostly aktualisieren (nach jeder neuen Stufe)
```
cd /srv/hostly/app
git pull
docker compose up -d --build
```
Die Datenbank (`/srv/hostly/db`) bleibt dabei erhalten.

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
- Zwei playit-Agenten laufen später als Docker-Container (je Account einer).
- Beim ersten Start zeigt jeder Agent einen **Link zum „Claimen“** → mit Account 1 bzw. 2 anmelden.
- Im playit-Dashboard Tunnel anlegen:
  - Typ: **Minecraft Java**
  - Lokale Adresse: fester Tunnel-Platz, z. B. `172.30.0.11`, Port `25565` (siehe TECHNIK.md Kapitel 4.2)
- Öffentliche Adressen notieren → im Hostly-Admin-Bereich eintragen.

---

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

## 10. Leise-Grenze ermitteln (gemeinsam)
1. Alles läuft, keine Spieler online, alle Server eingefroren → Lüfter sollte leise sein.
2. Hostly startet einen Testlauf mit 10 % CPU, dann 20 %, 30 % … (je 2 Minuten).
3. Du sagst, ab wann der Lüfter hörbar wird.
4. Eine Stufe darunter = **Leise-Grenze** → wird gespeichert (für Backups ab 06:00 und Downloads).

---

## 11. Abschluss-Checkliste
- [ ] `wsl --list --verbose` zeigt Ubuntu, VERSION 2
- [ ] `docker run --rm hello-world` klappt
- [ ] Windows-Laufwerke in Ubuntu **nicht** sichtbar (`ls /mnt` ist leer)
- [ ] Tailscale verbunden
- [ ] playit-Agenten geclaimt, Tunnel angelegt, Adressen notiert
- [ ] Autostart nach Neustart getestet (ohne Anmeldung)
- [ ] Energieoptionen gesetzt, Leise-Grenze ermittelt
- [ ] Nutzungszeit 06:00–24:00 gesetzt

---

## 12. Rückgängig machen (falls gewünscht)
**PowerShell als Administrator:**
```
wsl --unregister Ubuntu-24.04
```
→ Ubuntu und alle Hostly-Daten darin sind weg, Windows ist wie vorher. (Vorher Daten sichern, falls gewünscht.)
