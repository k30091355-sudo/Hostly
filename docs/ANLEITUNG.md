# Hostly einrichten – ausführliche Schritt-für-Schritt-Anleitung

> Für Anfänger geschrieben. Mach die Teile **genau in dieser Reihenfolge**.
> Dauer: ca. 2 Stunden (viel davon ist Warten auf Downloads).
> Tipp: Öffne diese Anleitung auf dem Handy, während du am Mini-PC arbeitest.

**So liest du die Anleitung**
- 🪟 **PowerShell** = Windows-Fenster für Befehle (wird unten erklärt).
- 🐧 **Ubuntu** = das Linux-Fenster, in dem Hostly läuft.
- Graue Kästen = Befehle. **Einen Kasten nach dem anderen** kopieren, einfügen, `Enter` drücken und warten, bis der Befehl fertig ist (die Eingabezeile erscheint wieder).
- ✅ = so siehst du, dass es geklappt hat.

**Kopieren & Einfügen**
- In PowerShell und Ubuntu: Text markieren und **Rechtsklick** = einfügen (oder `Strg + V`).
- Wenn nach einem **Passwort** gefragt wird: Beim Tippen erscheint **nichts** (keine Sternchen) – das ist normal. Einfach tippen und `Enter`.

---

## Teil A – Vorbereitung (Browser, 15 Minuten)

### A1. Tailscale-Account (für die Website von außen)
1. Öffne **tailscale.com** → oben rechts **„Get started“**.
2. Mit Google, Microsoft oder GitHub anmelden. Kostenlos, keine Kreditkarte.
3. Fertig – den Rest machen wir später.

### A2. Zwei playit.gg-Accounts (für Minecraft von außen)
1. Öffne **playit.gg** → **„Sign up“** / „Register“.
2. Account 1 mit deiner E-Mail anlegen, Passwort merken.
3. Für Account 2 eine **andere E-Mail-Adresse** benutzen (z. B. eine zweite Gmail-Adresse).
4. Zugangsdaten beider Accounts aufschreiben.

> Warum zwei? Kostenlos gibt es pro Account nur wenige Tunnel. Jeder laufende Minecraft-Server braucht einen eigenen Tunnel.
> Du kannst auch erst mal mit **einem** Account anfangen.

### A3. Mini-PC vorbereiten
- [ ] Mini-PC per **LAN-Kabel** an die FRITZ!Box (stabiler als WLAN).
- [ ] **Windows-Updates**: Einstellungen → Windows Update → „Nach Updates suchen“ → alles installieren → neu starten. Wiederholen, bis nichts mehr kommt.

---

## Teil B – Linux in Windows einrichten (WSL)

### B1. Prüfen, ob Virtualisierung an ist
1. `Strg + Shift + Esc` drücken → **Task-Manager** öffnet sich.
2. Links **Leistung** → **CPU** anklicken.
3. Rechts unten muss stehen: **Virtualisierung: Aktiviert**.
   - Steht dort „Deaktiviert“: im BIOS einschalten (Option heißt meist „Intel Virtualization Technology“ / „VT-x“). Melde dich dann, das machen wir zusammen.

### B2. PowerShell als Administrator öffnen
1. Auf **Start** (Windows-Symbol) **rechtsklicken**.
2. **„Terminal (Administrator)“** auswählen → Frage „Änderungen zulassen?“ mit **Ja** beantworten.
3. Ein blaues/schwarzes Fenster öffnet sich. Das ist 🪟 **PowerShell**.

### B3. Ubuntu installieren
🪟 PowerShell:
```
wsl --install -d Ubuntu-24.04
```
- Das dauert ein paar Minuten.
- Wenn es fertig ist: **PC neu starten** (Start → Ein/Aus → Neu starten).

Nach dem Neustart öffnet sich automatisch ein Fenster „Ubuntu“ (falls nicht: Start → „Ubuntu“ suchen und öffnen):
1. **„Enter new UNIX username“**: einen kurzen Namen in Kleinbuchstaben eingeben, z. B. `kevin` → `Enter`.
2. **„New password“**: ein Passwort ausdenken (wird beim Tippen nicht angezeigt) → `Enter` → nochmal eingeben → `Enter`.
3. **Benutzername und Passwort aufschreiben!** Das Passwort brauchst du bei jedem `sudo`-Befehl.
   - Tipp: Passwort **nur aus Buchstaben und Zahlen** (z. B. `Minecraft2026`), keine Umlaute/Sonderzeichen.
   - Test im Ubuntu-Fenster: `sudo -v` → Passwort eingeben. Kommt **„Sorry, try again“**, wurde das Passwort nicht gespeichert. Dann: `Strg + C`, PowerShell (Administrator) öffnen, `wsl -d Ubuntu-24.04 -u root` eingeben, dann `passwd DEINNAME` → neues Passwort 2× eingeben → `exit`.

✅ Du siehst eine Zeile wie `kevin@MINIPC:~$` – das ist 🐧 **Ubuntu**.

Prüfen – 🪟 PowerShell:
```
wsl --list --verbose
```
✅ Dort steht `Ubuntu-24.04` und bei VERSION eine **2**.

### B4. WSL einstellen (12 GB RAM, nie einschlafen)
1. Taste `Windows + R` → `notepad %USERPROFILE%\.wslconfig` eintippen → `Enter`.
2. Frage „Neue Datei erstellen?“ → **Ja**.
3. Diesen Text **komplett** hineinkopieren:
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
4. `Strg + S` (speichern) → Editor schließen.

> Was bedeutet das? 12 GB RAM und 8 Prozessor-Threads für Hostly (der Rest bleibt für Windows), Linux schläft nie ein, und gelöschte Daten machen die virtuelle Festplatte wieder kleiner.

---

## Teil C – Ubuntu vorbereiten

### C1. Linux-Einstellungen
🐧 Ubuntu:
```
sudo nano /etc/wsl.conf
```
- Passwort eingeben (dein Ubuntu-Passwort aus B3).
- Es öffnet sich ein Text-Editor (**nano**). Meist steht dort schon etwas, z. B. `[boot]` / `systemd=true` und `[user]` / `default=DEINNAME`.
  ⚠️ **Nichts davon löschen!** (`[user]` sorgt dafür, dass Ubuntu als dein Benutzer startet.)
- Mit `Strg + Ende` ans Ende springen, 2× `Enter` drücken und diesen Text darunter einfügen (Rechtsklick):
```ini
[automount]
enabled=false

[interop]
appendWindowsPath=false
```
- Falls `[boot]` / `systemd=true` noch **nicht** in der Datei steht, das auch noch dazuschreiben.
- So sieht die Datei am Ende aus (mit deinem Benutzernamen):
```ini
[boot]
systemd=true

[user]
default=DEINNAME

[automount]
enabled=false

[interop]
appendWindowsPath=false
```
- Speichern: `Strg + O` → `Enter`. Schließen: `Strg + X`.

> `automount enabled=false` heißt: Linux kann **nicht** auf deine Windows-Dateien (C:) zugreifen – sicherer.

Jetzt WSL neu starten – 🪟 PowerShell:
```
wsl --shutdown
```
10 Sekunden warten, dann Ubuntu neu öffnen (Start → „Ubuntu“).

### C2. Ubuntu aktualisieren und Werkzeuge installieren
🐧 Ubuntu (dauert ein paar Minuten):
```
sudo apt update && sudo apt upgrade -y
```
```
sudo apt install -y ca-certificates curl git rsync nano
```

### C3. Docker installieren
🐧 Ubuntu:
```
curl -fsSL https://get.docker.com | sudo sh
```
```
sudo usermod -aG docker $USER
```
```
sudo systemctl enable --now docker
```
Damit dein Benutzer Docker benutzen darf, WSL einmal neu starten – 🪟 PowerShell:
```
wsl --shutdown
```
Ubuntu neu öffnen, dann testen – 🐧 Ubuntu:
```
docker run --rm hello-world
```
✅ Es erscheint u. a. **„Hello from Docker!“**.

---

## Teil D – Hostly holen und starten

### D1. Hostly herunterladen
🐧 Ubuntu – diese Befehle nacheinander:
```
sudo mkdir -p /srv/hostly
```
```
sudo chown $USER:$USER /srv/hostly
```
```
mkdir -p /srv/hostly/db /srv/hostly/uploads /srv/hostly/servers /srv/hostly/archives /srv/hostly/downloads /srv/hostly/backups /srv/hostly/db-backups
```
```
cd /srv/hostly && git clone https://github.com/k30091355-sudo/Hostly.git app
```
✅ Es steht dort „Cloning into 'app'... done“.

### D2. Hostly starten
🐧 Ubuntu:
```
cd /srv/hostly/app && docker compose up -d --build
```
- Beim ersten Mal dauert das **5–10 Minuten** (es wird alles heruntergeladen und gebaut).
- ✅ Am Ende steht `Container hostly-web Started` und `Container hostly-worker Started`.

Prüfen:
```
docker compose ps
```
✅ `hostly-web` und `hostly-worker` stehen auf **Up** (bzw. „running“).

### D3. Deinen Admin-Account erstellen – SOFORT!
> ⚠️ **Wichtig:** Der **allererste** Account wird automatisch Admin. Mach das **jetzt**, bevor die Website im Internet erreichbar ist (Teil E).

1. Am Mini-PC einen Browser öffnen (Edge/Chrome) → Adresse **`http://localhost:8000`**.
2. ✅ Die Hostly-Startseite erscheint.
3. Oben rechts **Menü** → **Account erstellen** → Benutzername + Passwort (mind. 8 Zeichen) → **Account erstellen**.
4. ✅ Oben steht ein gelbes **„Admin“**-Schild. Im Menü gibt es jetzt **„Admin-Bereich“**.

> Seite lädt nicht? Siehe **Teil J – Hilfe bei Problemen**.

---

## Teil E – Website im Internet erreichbar machen (Tailscale Funnel)

### E1. Tailscale installieren
🐧 Ubuntu:
```
curl -fsSL https://tailscale.com/install.sh | sh
```
```
sudo tailscale up --hostname=hostly
```
- Es erscheint ein Link (`https://login.tailscale.com/a/...`).
- Link markieren, kopieren, im Browser öffnen → mit deinem Tailscale-Account (A1) anmelden → **„Connect“**.
- ✅ In Ubuntu steht danach „Success“.

### E2. Funnel einschalten (Website öffentlich machen)
🐧 Ubuntu:
```
sudo tailscale funnel --bg 8000
```
- Beim **ersten Mal** erscheint ein Link, weil HTTPS und Funnel erst erlaubt werden müssen.
  → Link im Browser öffnen → **erlauben** („Enable HTTPS“ / „Enable Funnel“) → danach den Befehl oben **nochmal** eingeben.
- ✅ Es erscheint eine Adresse wie **`https://hostly.tail1234.ts.net`** – das ist die Adresse von Hostly!
- Adresse aufschreiben. Die gibst du später deinen Spielern.

Adresse später nochmal anzeigen:
```
sudo tailscale funnel status
```

### E3. Testen
- Am **Handy**: WLAN **ausschalten** (mobile Daten) → die `https://hostly.….ts.net`-Adresse öffnen.
- ✅ Hostly erscheint. Mit deinem Admin-Account einloggen.
- Tipp: Browser-Menü → **„Zum Startbildschirm hinzufügen“** → Hostly ist wie eine App auf dem Handy.

> Die ersten Minuten kann es sein, dass die Adresse noch nicht geht (das HTTPS-Zertifikat wird erstellt). Kurz warten und neu laden.

---

## Teil F – Minecraft von außen erreichbar machen (playit.gg)

So funktioniert es: Jeder Minecraft-Server bekommt in Hostly einen festen „Platz“ (`172.30.0.11`, `172.30.0.12`, …). Ein playit-**Tunnel** verbindet eine öffentliche Adresse (z. B. `blue-cat.joinmc.link`) mit genau einem Platz. Der **playit-Agent** ist ein kleines Programm, das bei Hostly mitläuft und die Tunnel betreibt.

### F1. Geheim-Schlüssel für Account 1 holen
1. Im Browser auf **playit.gg** mit **Account 1** einloggen.
2. Links im Menü **„Agents“** öffnen → **„Add Agent“** (bzw. „Create Agent“ / „+“).
3. Als Art **„Docker“** auswählen.
4. playit zeigt jetzt einen **Secret Key** an – das ist eine lange Zeichenkette.
   - Manchmal zeigt playit stattdessen einen ganzen Befehl wie `docker run ... -e SECRET_KEY=abc123...`. Dann brauchst du **nur den Teil nach `SECRET_KEY=`** (bis zum nächsten Leerzeichen).
5. Schlüssel kopieren. ⚠️ **Niemandem zeigen** – wer ihn hat, kann deine Tunnel benutzen.

### F2. Schlüssel in Hostly eintragen
🐧 Ubuntu:
```
cd /srv/hostly/app && cp .env.example .env && nano .env
```
- Der Editor zeigt die Datei `.env`.
- Mit den Pfeiltasten in die Zeile `PLAYIT_SECRET_1=` gehen, ganz ans Ende (Taste `Ende`) und den Schlüssel **einfügen** (Rechtsklick).
- So soll es aussehen (mit deinem Schlüssel):
```
COMPOSE_PROFILES=playit
PLAYIT_SECRET_1=abc123deinlangerschluessel
PLAYIT_SECRET_2=
```
- Speichern: `Strg + O` → `Enter`. Schließen: `Strg + X`.

### F3. playit-Agent starten
🐧 Ubuntu:
```
docker compose up -d
```
```
docker compose ps
```
✅ Jetzt läuft zusätzlich **`hostly-playit-1`**.

Kontrolle:
```
docker compose logs --tail 20 playit-1
```
- Im playit-Dashboard (Browser) unter **Agents** sollte dein Agent nach kurzer Zeit als **online** erscheinen.
- Falls in den Logs ein **Link zum „Claimen“** steht: Link im Browser öffnen und mit Account 1 bestätigen.

### F4. Tunnel anlegen (im playit-Dashboard)
Für **jeden** Minecraft-Server, der gleichzeitig laufen soll, einen Tunnel:
1. playit.gg → **„Tunnels“** → **„Add Tunnel“** / „Create Tunnel“.
2. **Tunnel-Typ:** **„Minecraft Java (game)“**.
3. **Agent:** deinen Docker-Agent aus F1 auswählen.
4. **Local Address / Lokale Adresse:** `172.30.0.11`
5. **Local Port:** `25565`
6. Speichern / „Create“.
7. playit zeigt die **öffentliche Adresse**, z. B. `blue-cat.joinmc.link` → aufschreiben.

Für den **zweiten** Tunnel genauso, aber mit `172.30.0.12`, den dritten mit `172.30.0.13` usw.

> Wie viele? Mit 12 GB passen z. B. 4× Holz gleichzeitig → 4 Tunnel (Plätze `.11` bis `.14`). Wenn ein Account keine weiteren Tunnel erlaubt → Account 2 benutzen (F6).

### F5. Tunnel in Hostly eintragen
1. Hostly öffnen → **Menü → Admin-Bereich → Tunnel**.
2. Ausfüllen:
   - **Name:** z. B. `Tunnel A`
   - **playit-Account:** `1`
   - **Öffentliche Adresse:** die Adresse aus F4 (z. B. `blue-cat.joinmc.link`)
   - **Interner Platz:** muss **genau** zu F4 passen (Hostly schlägt `172.30.0.11` vor, dann `.12` …)
3. **Eintragen**.
4. Für jeden weiteren Tunnel wiederholen.

✅ Unter „Alle Tunnel“ stehen deine Tunnel mit „frei“.

### F6. (Optional) Account 2 dazunehmen
1. Mit **Account 2** auf playit.gg einloggen → wie in F1 einen Docker-Agent anlegen und Schlüssel kopieren.
2. 🐧 Ubuntu:
```
cd /srv/hostly/app && nano .env
```
3. Schlüssel hinter `PLAYIT_SECRET_2=` einfügen **und** die erste Zeile ändern zu:
```
COMPOSE_PROFILES=playit,playit2
```
4. Speichern (`Strg + O`, `Enter`, `Strg + X`) und starten:
```
docker compose up -d
```
5. ✅ `docker compose ps` zeigt auch **`hostly-playit-2`**.
6. Tunnel für Account 2 wie in F4 anlegen – mit den **nächsten freien Plätzen** (z. B. `172.30.0.15`), Agent = der von Account 2.
7. In Hostly eintragen wie in F5, aber **playit-Account: 2**.

---

## Teil G – Erster Test-Server

1. **Code erstellen:** Admin-Bereich → **Codes** → Coins `1000` → **Erstellen** → Code kopieren.
2. **Code einlösen:** Menü → **Code einlösen** → einfügen → **Einlösen**. ✅ „+1000 Coins gutgeschrieben 🎉“, oben steht 🪙 1.000.
3. **Server kaufen:** Menü → **Server kaufen**
   - Modell **Holz**, „Selbst wählen“ → **Vanilla**, **1** Tag, Name z. B. `Test`
   - **Jetzt kaufen**.
4. Die Server-Seite zeigt **„wird erstellt …“**.
   - ⏳ Beim **allerersten** Server lädt Hostly das Minecraft-Programm (ca. 1 GB) herunter → **5–15 Minuten**. Danach geht es viel schneller.
5. Reiter **Konsole**: Hier siehst du, wie der Server startet. ✅ Wenn `Done (…)! For help, type "help"` erscheint, ist er bereit.
6. **In Minecraft verbinden:** Minecraft Java öffnen → **Mehrspieler** → **Server hinzufügen** → Adresse aus der Übersicht (z. B. `blue-cat.joinmc.link`) → **Fertig** → verbinden.
7. ✅ Du bist auf deinem Server! 🎉
8. Tipp: Menü → **Einstellungen → Minecraft-Name** eintragen → du bekommst auf deinen Servern automatisch OP.

> Wenn niemand online ist, **friert der Server nach 5 Minuten ein** (Status „schläft“). Beim Verbinden wacht er in 1–2 Sekunden wieder auf – das ist gewollt und macht den PC leise.

---

## Teil H – Autostart und Windows-Einstellungen

### H1. Hostly startet automatisch beim Hochfahren
1. Start → **„Aufgabenplanung“** suchen und öffnen.
2. Rechts **„Aufgabe erstellen…“** (nicht „Einfache Aufgabe“).
3. Reiter **Allgemein**:
   - Name: `Hostly starten`
   - **„Unabhängig von der Benutzeranmeldung ausführen“** auswählen
   - Haken bei **„Mit höchsten Privilegien ausführen“**
4. Reiter **Trigger** → **Neu…** → „Aufgabe starten“: **Beim Start** → OK.
5. Reiter **Aktionen** → **Neu…**:
   - Programm/Skript: `wsl.exe`
   - Argumente hinzufügen: `-d Ubuntu-24.04 -u root -- sleep infinity`
   - OK.
6. Reiter **Bedingungen**: Haken bei „Aufgabe nur starten, falls Computer im Netzbetrieb ausgeführt wird“ **entfernen**.
7. Reiter **Einstellungen**: Haken bei **„Aufgabe beenden, falls Ausführung länger als …“** **entfernen**.
8. **OK** → Windows-Passwort eingeben.

**Test:**
1. PC neu starten, **nicht anmelden** (beim Sperrbildschirm bleiben).
2. 2–3 Minuten warten.
3. Am Handy die Hostly-Adresse öffnen. ✅ Hostly ist erreichbar.

> Klappt das nicht (Hostly erst nach dem Anmelden erreichbar)? Das passiert auf manchen PCs. Dann melde dich – es gibt Plan B (automatische Anmeldung mit sofortiger Bildschirmsperre, siehe `SETUP-MINI-PC.md` Kapitel 8).

### H2. Energie: nie einschlafen, leise
1. Einstellungen → **System → Netzbetrieb** (bzw. „Bildschirm und Energiesparen“):
   - Bildschirm ausschalten: nach **10 Minuten** (okay)
   - **Energiesparmodus / Standby: Nie**
2. Start → „**Energiesparplan bearbeiten**“ suchen → **„Erweiterte Energieeinstellungen ändern“**:
   - **Festplatte → Festplatte ausschalten nach: Nie** (0 eintippen)
   - **Prozessorenergieverwaltung → Maximaler Leistungszustand des Prozessors: 95 %** (macht den PC leiser)
   - OK.

### H3. Windows-Updates nachts
Einstellungen → **Windows Update → Erweiterte Optionen → Nutzungszeit** → **Manuell** → **06:00 bis 00:00**.
→ Update-Neustarts passieren meist nachts. Hostly startet danach von selbst (H1).

---

## Teil I – Im Alltag

### Hostly aktualisieren (wenn es eine neue Version gibt)
👉 Ausführliche Update-Anleitung: **[UPDATE.md](UPDATE.md)** (dort stehen auch besondere Hinweise zu einzelnen Updates).

🐧 Ubuntu:
```
cd /srv/hostly/app && git pull && docker compose up -d --build
```
Datenbank, Welten und Backups bleiben erhalten. Laufende Minecraft-Server laufen weiter.

### Wichtige Admin-Aufgaben in Hostly
| Was | Wo |
|---|---|
| Codes erstellen | Admin-Bereich → Codes |
| Passwort eines Users zurücksetzen | Admin-Bereich → User → Name anklicken → „Passwort zurücksetzen“ |
| Gewinnspiel / Rabatt-Woche | Admin-Bereich → Gewinnspiele / Aktionen |
| Eigene Plugins für einen User (Support) | Server öffnen → Plugins/Mods → „Admin: eigene Datei hochladen“ |
| Wartung (z. B. vor Updates) | Admin-Bereich → Einstellungen → Wartungsmodus |
| Backups behalten / Archive löschen | Admin-Bereich → Backups & Archive |

### Notfall-Befehle
Eigenes Passwort vergessen – 🐧 Ubuntu:
```
cd /srv/hostly/app && docker compose exec web python -m hostly.cli passwort DEIN_BENUTZERNAME
```
→ zeigt ein neues zufälliges Passwort an.

Jemanden zum Admin machen:
```
cd /srv/hostly/app && docker compose exec web python -m hostly.cli admin BENUTZERNAME
```

Hostly komplett neu starten:
```
cd /srv/hostly/app && docker compose restart
```

---

## Teil J – Hilfe bei Problemen

**Zuerst immer die Protokolle anschauen** – 🐧 Ubuntu:
```
cd /srv/hostly/app && docker compose logs --tail 50 web worker
```
(Die letzten Zeilen kannst du mir schicken – **aber vorher prüfen, dass kein playit-Schlüssel darin steht.**)

| Problem | Lösung |
|---|---|
| `docker: permission denied` | Teil C3: `sudo usermod -aG docker $USER`, dann in PowerShell `wsl --shutdown`, Ubuntu neu öffnen. |
| `http://localhost:8000` lädt nicht | `docker compose ps` – läuft `hostly-web`? Wenn nicht: `docker compose up -d`. Prüfen, ob in `.wslconfig` die Zeile `networkingMode=mirrored` steht. |
| `hostly-web` startet immer neu, Logs: „Permission denied“ / „unable to open database“ | Ordner gehören dem falschen Benutzer: `sudo chown -R $USER:$USER /srv/hostly` und `docker compose restart`. |
| Funnel-Adresse geht nicht | `sudo tailscale funnel status` – steht dort `:8000`? Sonst `sudo tailscale funnel --bg 8000` erneut. In der Tailscale-Verwaltung HTTPS + Funnel erlaubt? |
| Server bleibt bei „wird erstellt …“ | Beim ersten Server normal (Download ~1 GB). Nach 20 Minuten: Logs anschauen (`docker compose logs --tail 50 worker`). |
| „Kauf aktuell nicht möglich“ | Kein freier Tunnel (Teil F5) oder RAM voll. Admin-Bereich → Übersicht zeigt RAM und Tunnel. |
| Minecraft: „Verbindung fehlgeschlagen“ | playit-Dashboard: Agent online? Tunnel-Platz (`172.30.0.11`) gleich wie in Hostly → Tunnel? Server-Status in Hostly „online“ oder „schläft“? |
| playit-Agent startet nicht | `docker compose logs --tail 30 playit-1` – Schlüssel richtig in `.env`? Erste Zeile `COMPOSE_PROFILES=playit`? |
| Nach Windows-Neustart ist Hostly weg | Teil H1 prüfen (Aufgabenplanung). Notfalls Ubuntu einmal öffnen – dann startet alles. |

---

## Checkliste – alles fertig?
- [ ] `wsl --list --verbose` zeigt Ubuntu-24.04 mit VERSION 2
- [ ] `docker run --rm hello-world` klappt
- [ ] `docker compose ps` zeigt `hostly-web`, `hostly-worker`, `hostly-playit-1` auf **Up**
- [ ] Erster Account erstellt → ist **Admin**
- [ ] Website über `https://hostly.….ts.net` vom Handy (mobile Daten) erreichbar
- [ ] playit-Agent im Dashboard **online**, Tunnel angelegt **und** in Hostly eingetragen
- [ ] Test-Server gekauft und mit Minecraft verbunden
- [ ] Autostart getestet (Neustart ohne Anmeldung → Hostly erreichbar)
- [ ] Energiesparplan und Windows-Update-Nutzungszeit eingestellt

🎉 Fertig! Jetzt kannst du Codes an deine Freunde verteilen.
