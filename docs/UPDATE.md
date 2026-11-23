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

### Version 1.5.6 (23.11.2026) – Downloads blockieren nichts mehr
Einfach Schritt 1–5 unten.
- **ZIP-Download** (Welt / alle Dateien) lief bisher als „einziger Auftrag“ des Servers – bei großen Welten
  hingen Starten, Stoppen und Neustart so lange (teils über 30 Minuten), obwohl die Knöpfe klickbar waren.
  Jetzt läuft das Packen nebenher. Es wird höchstens ein ZIP gleichzeitig gepackt (bleibt leise).

### Version 1.5.5 (23.11.2026) – Weitere Fehlersuche
Einfach Schritt 1–5 unten.
- **Wartung:** Wurde eine geplante Wartung früher von Hand beendet, hat Hostly eine spätere, von Hand
  eingeschaltete Wartung sofort wieder ausgeschaltet. Behoben.
- **Server übertragen:** Der alte Besitzer behielt OP-Rechte im Spiel – jetzt werden sie entfernt.
- **Adresse kopieren** auf der Startseite: Nach dem Klick verlor der Knopf sein Aussehen. Behoben.
- **Admin-Übersicht:** Einige Ereignisse (Wartung geplant, Server-Einstellungen, neue Welt, Start-Coins)
  standen als Code-Text da – jetzt verständlich. Fehlende englische Texte ergänzt.

### Version 1.5.4 (23.11.2026) – Fehlersuche
Einfach Schritt 1–5 unten.
- **Konsole:** Die Sperre für `stop`/`restart`/`reload` ließ sich mit `execute … run stop` umgehen – jetzt gesperrt.
- **Statistik:** Nach einem Absturz blieben Spieler im Verlauf „online“, ihre Spielzeit lief endlos weiter.
  Jetzt werden offene Sitzungen beim nächsten Serverstart geschlossen.
- **Minecraft-Name ändern:** Der alte Name behielt auf deinen Servern die OP-Rechte – jetzt werden sie entfernt.
- **Account löschen:** Der einzige Admin kann seinen Account nicht mehr löschen (sonst gäbe es keinen Admin mehr).
- **Gewinnspiele:** Gelöschte Accounts können nicht mehr gewinnen (die Coins wären verloren gewesen).
- **Welten:** Namen wie „plugins“, „config“ oder „logs“ sind als Weltname gesperrt – vorher wurde der Ordner
  beim Hochladen durch die Welt ersetzt. Welt-ZIPs dürfen entpackt höchstens 8 GB groß sein (Festplatte).
- **Nachtpause:** Wird sie während einer laufenden Pause ausgeschaltet oder geändert, startet der Server wieder
  (vorher blieb er aus, bis man ihn selbst startete).

### Version 1.5.3 (23.11.2026) – Modpack enthält alle Mods
Einfach Schritt 1–5 unten. Spieler sollten das Modpack danach **neu herunterladen**.
- Nachträglich hinzugefügte Mods (auch bei Vorlagen wie Performance-Vanilla) waren zwar in der Modpack-Datei,
  aber als „optional“ markiert – die Modrinth App und Prism haben sie deshalb nicht geladen bzw. ausgeschaltet.
  Jetzt sind alle Mods Pflicht und werden automatisch installiert.
- Die Datei wird nie zwischengespeichert und hat bei jeder Mod-Änderung eine neue Kennung → Launcher erkennen,
  dass es eine neue Fassung ist.

### Version 1.5.2 (23.11.2026) – Modpack für alle
Einfach Schritt 1–5 unten.
- Bei Fabric-Servern mit Mods gibt es jetzt für **jeden** (auch ohne Login) einen Knopf **„📦 Modpack“** in der
  öffentlichen Serverliste und **„📦 Modpack herunterladen“** auf der Statistik-Seite (`/s/<kürzel>`).
  Die Datei in der Modrinth App oder im Prism Launcher öffnen → alle Mods des Servers sind drin.
  Mods, die nur auf dem Server laufen, sind nicht im Modpack.

### Version 1.5.1 (23.11.2026) – Fußzeile
Einfach Schritt 1–5 unten. Der Text „// selbst gebaut, läuft auf einem Mini-PC“ unten auf der Seite ist wieder weg.

### Version 1.5.0 (23.11.2026) – Schutz gegen Lags und Abstürze + neuer Look
Einfach Schritt 1–5 unten. Danach **jeden Server einmal neu starten** (bei Paper-Servern zeigt Hostly
„Neustart nötig“ an, sobald der Schutz bereit ist).

**Stabilere Welten (alle Server)**
- Riesige Redstone-/Sand-Kettenreaktionen werden begrenzt (Lag-Maschinen bringen den Server nicht mehr zum Hängen).
- Entities werden nur bis 80 % der Sichtweite an Spieler geschickt → weniger Daten durch den playit-Tunnel.
- Java darf für Netzwerkpuffer höchstens 256 MB extra nehmen – vorher konnte Java mehr RAM belegen als der
  Container hat, dann wurde der Server hart beendet („Absturz“ ohne Fehlermeldung).

**Zusätzlich bei Paper (auch SkyBlock/OneBlock)** – nur Werte, die noch auf Standard stehen; eigene Änderungen bleiben:
- Welt wird gleichmäßiger erzeugt (max. 40 Chunks/Sekunde pro Spieler) und langsamer gesendet → weniger Hänger
  und weniger „Timed out“ beim ersten Betreten neuer Gebiete.
- Spieler können nicht mehr in ungeladene Gebiete fliegen (häufige Lag-Spitze).
- Speichern wird auf mehr Ticks verteilt (kein Ruckler alle 5 Minuten).
- Zu viele Pfeile/XP-Kugeln in einem Chunk können ihn nicht mehr kaputt machen.
- Schnellere Berechnung von Explosionen, Redstone (Alternate Current), Trichtern und Tierfarmen
  (max. 2 Zusammenstöße pro Tier); Gegenstände/XP am Boden werden zusammengefasst.

**Neuer Look („selbst gebaut“)**
- Klare Linien und Kanten-Schatten statt weicher Schatten, Karopapier-Hintergrund, Knöpfe „drücken“ sich beim Klick ein.
- Kleine Terminal-Details: „>“ vor Überschriften, blinkender Cursor auf der Startseite, Monospace-Schrift für
  Adressen, Zahlen und Status.

### Version 1.4.3 (23.11.2026) – Einige Vorlagen vorerst gesperrt
Einfach Schritt 1–5 unten.
- **Survival mit Freunden, Creative, SkyBlock, OneBlock und Abenteuer** sind beim Kaufen grau und zeigen
  „Kommt bald …“ – man kann sie nicht mehr auswählen. Bereits gekaufte Server mit diesen Vorlagen laufen weiter.
  Freigeben später: in `hostly/extensions.py` bei der Vorlage `"soon": True` entfernen.

### Version 1.4.2 (23.11.2026) – Schnellerer Neustart, weniger Ruckler bei Paper
Einfach Schritt 1–5 unten. Danach Paper-Server (auch SkyBlock/OneBlock) **einmal neu starten**.
- **Neustart schneller und zuverlässiger:** Hostly hat vor jedem Stoppen zusätzlich „save-all“ geschickt und bei
  einem überlasteten Server bis zu 6× gewartet – der Neustart hing dann 2–3 Minuten („Aktion läuft …“).
  Jetzt speichert Minecraft beim Stoppen selbst (wie vorher auch). Ein Neustart dauert ca. 20 Sekunden.
- **Weniger Hänger beim Betreten neuer Gebiete (Paper):** Paper hat bei Holz und Eisen nur 1 Thread zum Erzeugen
  der Welt benutzt („Paper is using 1 worker threads“) – beim ersten Betreten neuer Gebiete hing der Server dann teils
  minutenlang („Timed out waiting for world statistics“). Jetzt: Holz 1, Eisen 2, Diamant 3 Threads.
- Hinweis: Die Meldung „spark … NumberFormatException: Infinite or NaN“ nach dem Aufwachen aus dem Einfrieren ist
  harmlos (Fehler im mitgelieferten Profiler spark, nicht in Hostly oder deiner Welt).

### Version 1.4.1 (23.11.2026) – Fehlerbehebungen vor dem Release
Einfach Schritt 1–5 unten. Danach **jeden laufenden Server einmal neu starten** (Knopf „Neustarten“), damit
die Korrekturen bei Plugins und Gamerules greifen. Die Datenbank wird beim Start automatisch erweitert.

Alle 8 Vorlagen wurden mit echten Minecraft-Servern getestet (Vanilla pur, Vanilla+, Survival, Creative,
SkyBlock, OneBlock, Performance, Abenteuer) – plus normale Vanilla-/Paper-/Fabric-Server in alter und neuer Version.

- **SkyBlock und OneBlock starten jetzt richtig.** BSkyBlock und AOneBlock sind Erweiterungen von BentoBox und
  müssen im Ordner `plugins/BentoBox/addons/` liegen – Hostly hat sie bisher direkt in `plugins/` gelegt, dort lädt
  Paper sie nicht („Could not load plugin“). Bestehende Server werden beim nächsten Neustart automatisch repariert.
- **Altes Server-Bild bei neuem Server behoben.** Nach dem Zurücksetzen aller Accounts bekommen neue Server wieder
  die Nummern 1, 2, 3 … – und haben das Bild (und sogar die Welt!) des alten Servers mit derselben Nummer geerbt.
  Jetzt zeigt ein neuer Server immer das Hostly-Logo, bis der Besitzer ein eigenes Bild hochlädt. Reste alter Server
  werden beim Erstellen nicht gelöscht, sondern nach `/srv/hostly/verwaist/` verschoben (kannst du später löschen).
  ⚠️ Server, die schon **vor** diesem Update erstellt wurden, können noch eine alte Welt haben – dann im Reiter
  „Einstellungen“ → „Neue Welt“ drücken.
- **Spieler-Verlauf bei Paper-Servern repariert.** „Wer war online“, „Was ist passiert?“ auf der Startseite und die
  Spielernamen in der Statistik waren bei Paper-Servern (auch SkyBlock, OneBlock, Survival, Creative) immer leer.
- **Gamerules ohne Fehlermeldung:** Hostly schickt nur noch die Namen, die zur Minecraft-Version passen
  (vorher stand bei jedem Start „Failed to load function hostly_rules:old“ rot in der Konsole).
- **`/trigger code` funktioniert jetzt auch auf älteren Versionen** (z. B. 1.21.4 – vorher Fehler beim Laden).
- **Resourcepacks:** Der Link für die Spieler zeigt immer auf die öffentliche Adresse – auch wenn du die Seite
  zu Hause über die lokale IP geöffnet hast (vorher konnten Spieler das Pack dann nicht laden).
- Die aktive Welt (auch Nether/End) kann nicht mehr aus Versehen gelöscht werden; leere Konsolen-Befehle werden
  nicht mehr gesendet.

### Version 1.4.0 (23.11.2026) – Neue Startseite + anonym
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten.
- **Neue Startseite für Besucher:** große Überschrift „Dein eigener Minecraft-Server. Komplett kostenlos.“, Live-Zahlen
  (Spieler heute, Server aktiv, 0 €), Registrieren-Knopf mit Startbonus, die 3 Modelle (das meistgemietete ist „beliebt“),
  öffentliche Server zum Mitspielen und „So geht's“.
- **Neue Startseite für eingeloggte Spieler:** „Willkommen zurück, Name!“, Coins (mit „reicht ca. … Wochen“) und Anzahl
  deiner Server, „Deine Server“ als große Karten (Adresse mit einem Klick kopieren) + Karte „Neuer Server“
  (zeigt, welche Modelle gerade Platz haben), Aktionen als Streifen mit Countdown, öffentliche Server und
  **„Was ist passiert?“** (wer in den letzten 24 Std. beigetreten ist, offene Whitelist-Anfragen).
- **Anonym:** Bei beendeten Gewinnspielen stehen keine Namen mehr – nur „1 Gewinner“ / „3 Gewinner“.
  Wer selbst gewonnen hat, sieht „🎉 Du hast gewonnen!“. Bei Whitelist-Anfragen sieht der Server-Besitzer nur noch
  den Minecraft-Namen, nicht mehr den Hostly-Benutzernamen. (Der Admin sieht im Admin-Bereich weiterhin alles.)

### Version 1.3.1 (22.11.2026) – Hinweis „Neue Version“
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten.
- Wer Hostly gerade offen hat (Browser oder Handy-App), sieht nach einem Update innerhalb von 1 Minute oben
  **„✨ Es gibt eine neue Hostly-Version. [Seite aktualisieren]“** – ein Klick lädt die neue Version.
- Funktioniert ab dieser Version: Seiten, die noch mit einer älteren Version geöffnet sind, einmal selbst neu laden.

### Version 1.3.0 (22.11.2026) – Großes Funktions-Update
Nichts Besonderes zu beachten, einfach Schritt 1–5 unten. Die Datenbank wird beim Start automatisch erweitert.

**Für Server-Besitzer**
- **Neuer Reiter „Einstellungen“:** Schwierigkeit, Spielmodus, PvP, Fliegen, Sichtweite und Spawn-Schutz per Formular (gilt nach Neustart).
- **Gamerules per Klick** (Inventar behalten, Tag/Nacht, Monster, Phantome, Schlaf-Prozent …) – gelten sofort, wenn der Server läuft.
- **„Neue Welt“-Knopf** (optional mit Seed). Vorher wird automatisch eine Sicherung angelegt – wie auch vor jedem Versions-/Typwechsel.
- **Mod-/Plugin-Updates:** Im Reiter „Plugins/Mods“ erscheint „🔄 Updates verfügbar“ – einzeln oder alle mit einem Klick.
- **Fehler-Erklärer:** Hostly erkennt häufige Fehler im Protokoll (z. B. „Fabric API fehlt“, fehlende Abhängigkeit, zu wenig RAM, Ruckler) und erklärt sie einfach – oft mit Knopf zum Beheben.
- **Leistung im Reiter „Statistik“:** TPS, RAM und CPU jetzt und als Grafik der letzten 24 Stunden.
- **Whitelist-Anfragen:** Server mit Whitelist dürfen wieder in die öffentliche Serverliste (mit 🔒). Spieler stellen auf der Statistik-Seite eine Anfrage, der Besitzer nimmt sie im Reiter „Spieler“ an.

**Coins**
- **100 Start-Coins** für jeden neuen Account (Admin kann die Zahl ändern) + neue Aktions-Art **„Startbonus“** für mehr Coins bei der Registrierung.
- **Countdown** bei Rabatt-Aktionen auf der Startseite.
- **Coins-Prognose** auf der Startseite (reichen die Coins fürs Auto-Verlängern?) + Erinnerung 3 Tage vorher, wenn nicht.
- **Einführung** für neue Spieler direkt nach dem Registrieren (Code einlösen / Server mieten / Überspringen).

**Für den Admin**
- **Mini-PC-Grafik** (CPU, RAM, Festplatte – letzte 7 Tage) im Admin-Bereich.
- **Warnungen**, wenn die Festplatte fast voll ist, der Mini-PC zu heiß wird oder ein playit-Agent nicht läuft.
- **Wartung planen** (Admin → Einstellungen): alle sehen einen Countdown, Hostly schaltet den Wartungsmodus automatisch an und aus.

👉 **Nach dem Update:** Bestehende Server einmal **neu starten**, damit die neuen Einstellungen greifen.

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
