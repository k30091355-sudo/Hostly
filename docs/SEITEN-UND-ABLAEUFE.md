# Hostly – Seiten & Abläufe

> Ergänzung zu [`KONZEPT.md`](../KONZEPT.md): Welche Seiten gibt es, was steht drauf, und wie laufen die wichtigsten Vorgänge Schritt für Schritt ab.
> Stand: Planung, noch kein Code.

---

## 1. Seitenübersicht

| Seite | Adresse (*Vorschlag*) | Ohne Login | Eingeloggt | Admin |
|---|---|---|---|---|
| Startseite | `/` | ansehen | ✅ | ✅ |
| Login | `/login` | ✅ | – | – |
| Account erstellen | `/registrieren` | ✅ | – | – |
| Server kaufen (mit Vergleich) | `/kaufen` | ansehen | ✅ | ✅ |
| Code einlösen | `/code` | → Login | ✅ | ✅ |
| Gewinnspiele | `/gewinnspiele` | ansehen | ✅ teilnehmen | ✅ |
| Öffentliche Serverliste | `/serverliste` | ✅ | ✅ | ✅ |
| Server-Statistiken (per Kürzel) | `/s/<kürzel>` | ✅ | ✅ | ✅ |
| Meine Server | `/server` | → Login | ✅ | ✅ |
| Server-Details & Einstellungen | `/server/<id>` | → Login | ✅ (eigene) | ✅ (alle) |
| Einstellungen | `/einstellungen` | → Login | ✅ | ✅ |
| Coin-Verlauf | `/einstellungen/coins` | → Login | ✅ | ✅ |
| Admin-Bereich | `/admin/...` | ❌ | ❌ | ✅ |
| Support | `mailto:k3009135@gmail.com` | ✅ | ✅ | ✅ |

---

## 2. Aufbau der Seiten

### 2.1 Kopfleiste (überall)
```
┌──────────────────────────────────────────────────────────────────┐
│ [Logo] Hostly                    🪙 1.250   [🌙/☀️]   [Menü ▾]    │
└──────────────────────────────────────────────────────────────────┘
```
- 🪙 Coin-Stand nur eingeloggt (*Vorschlag*).
- 🌙/☀️ Dark/Light umschalten.
- **Menü ▾** (Dropdown rechts, ENTSCHIEDEN):
  - eingeloggt: Meine Server · Server kaufen · Code einlösen · Gewinnspiele · Serverliste · Server-Statistiken · Einstellungen · (Admin-Bereich / User-Ansicht) · Support · Abmelden
  - nicht eingeloggt: Login · Account erstellen · Serverliste · Server-Statistiken · Support

### 2.2 Startseite
```
┌──────────────────────────────────────────────────────────────────┐
│ ⚠️ „Mein Survival“ läuft in 2 Tagen ab  [Verlängern]              │  ← nur eingeloggt
├──────────────────────────────────────────────────────────────────┤
│  🔥 RABATT-WOCHE: −20 % auf alle Diamant-Server bis Sonntag!       │  ← groß
├──────────────────────────────────────────────────────────────────┤
│  🎁 GEWINNSPIEL: 3× 500 Coins · noch 4 Tage   [Teilnehmen]         │  ← groß
├──────────────────────────────────────────────────────────────────┤
│   [ 🎟️ Code einlösen ]   [ 🛒 Server kaufen ]   [ Login / Meine Server ] │
├──────────────────────────────────────────────────────────────────┤
│  Kurz erklärt: Code einlösen → Coins → Server mieten  (*Vorschlag*)│
│  Auslastung: „Noch Platz für Holz und Eisen“          (*Vorschlag*)│
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Server kaufen
```
Schritt 1: Modell vergleichen
┌──────────┬──────────┬──────────┬──────────┐
│          │  Holz    │  Eisen   │ Diamant  │
├──────────┼──────────┼──────────┼──────────┤
│ RAM      │  2 GB    │  3 GB    │  4 GB    │
│ Spieler  │  3       │  7       │  15      │
│ Preis/Tag│  10 🪙   │  30 🪙   │  50 🪙   │
│ Aktion   │  –       │ +1 GB!   │ −20 %    │
│          │ [Wählen] │ [Wählen] │ [Wählen] │
└──────────┴──────────┴──────────┴──────────┘
Schritt 2: Vorlage oder Typ (Vanilla / Paper / Fabric) + Version
Schritt 3: Tage  [ 30 ]   → Tage-Rabatt 30 %
Schritt 4: Nachtpause  [ ] an   von [01:00] bis [08:00]  → bis zu 7 % zurück pro Nacht
Schritt 5: Name, öffentlich listen [ ] (Standard aus)
──────────────────────────────────────────
Preis:  ~~1500~~  →  1050 🪙   (−30 %)
[ Jetzt kaufen ]      bzw.  „Kauf aktuell nicht möglich“ + [Benachrichtige mich]
```

### 2.4 Meine Server
```
┌───────────────────────────────────────────────────────────────┐
│ [Icon] Mein Survival   Eisen · Paper 1.21   🟢 online 2/7       │
│        noch 12 Tage · blue-cat.joinmc.link [📋]                 │
│        [Stoppen] [Neustarten] [Verwalten ›]                     │
├───────────────────────────────────────────────────────────────┤
│ [Icon] Bauwelt         Holz · Vanilla     💤 schläft            │
├───────────────────────────────────────────────────────────────┤
│ [Icon] Alter Server    Diamant · Fabric   📦 archiviert          │
│        [Reaktivieren] [Download]                                 │
└───────────────────────────────────────────────────────────────┘
```

### 2.5 Server verwalten (Reiter)
| Reiter | Inhalt |
|---|---|
| **Übersicht** | Status, Adresse, Restlaufzeit, Knöpfe Start/Stopp/Neustart/Reload, Banner „Änderungen ausstehend“ |
| **Konsole** | Live-Ausgabe + Eingabe (gesperrte Befehle) |
| **Darstellung** | MOTD-Editor mit Vorschau, Server-Icon mit Zuschneide-Rahmen, Name |
| **Spieler** | Whitelist an/aus + Liste, Join-Verlauf |
| **Plugins/Mods** | Suche (Modrinth/CurseForge), Installierte (an/aus, Version), Modpack für Spieler |
| **Welten** | Liste, aktive Welt, neue Welt, Upload |
| **Resourcepack** | Hochladen/Auswählen, Pflicht ja/nein |
| **Dateien** | Dateimanager |
| **Backups** | Liste, Wiederherstellen |
| **Miete** | Verlängern, Auto-Verlängern (7 Tage), Nachtpause, Upgrade/Downgrade, Typ & Version, Übertragen, Löschen |
| **Statistik** | Kürzel + Link, öffentlich listen an/aus |

### 2.6 Admin-Bereich (Reiter)
Dashboard · User · Server · Codes · Gewinnspiele · Aktionen (Rabatt/RAM) · Tunnel · Backups & Archive · Einstellungen (Wartungsmodus, Leise-Grenze, RAM-Reserve)

---

## 3. Abläufe Schritt für Schritt

### 3.1 Registrieren & erster Login
1. „Account erstellen“ → Benutzername + Passwort (2× eingeben).
2. Prüfung: Benutzername frei? Passwort lang genug (*Vorschlag* ≥ 8)?
3. Konto angelegt, direkt eingeloggt → Startseite.
4. Hinweis-Banner (*Vorschlag*): „Hinterlege deinen Minecraft-Namen, damit du auf deinen Servern OP bekommst.“

### 3.2 Code einlösen
1. „Code einlösen“ → Eingabe (Groß-/Kleinschreibung und Bindestriche egal, *Vorschlag*).
2. Prüfungen in dieser Reihenfolge: existiert? aktiv? nicht abgelaufen? noch Einlösungen frei? **dieser User noch nicht eingelöst?**
3. Erfolg: Buchung „+X Coins (Code …)“, Zähler +1 → „+X Coins gutgeschrieben 🎉“.
4. Fehler: passende Meldung, z. B. **„Code bereits eingelöst“**.

### 3.3 Server kaufen
1. Modell, Typ/Vorlage, Version, Tage, Nachtpause, Name wählen → Preis live.
2. Klick „Kaufen“:
   1. Genug Coins?
   2. RAM-Prüfung (Reserve bleibt frei)?
   3. Freier Tunnel?
   4. Wenn alles ja: Coins abbuchen + Server anlegen + Tunnel reservieren (eine Transaktion).
3. worker erstellt Container → Status „wird erstellt …“ → „online“.
4. Ergebnis: Adresse, Kürzel, Hinweis „In Minecraft unter Mehrspieler → Server hinzufügen“.

### 3.4 Nachtpause (eine Nacht)
1. 01:00 → Server bekommt Ankündigung im Chat (*Vorschlag*), dann sauber gestoppt.
2. Während der Pause startet der User **nicht** → Pause gilt als vollständig.
3. 08:00 → Server startet wieder (bzw. bleibt eingefroren bis jemand kommt).
4. Erstattung: aufgerundet `Tagespreis × Stunden %` → Buchung „Nachtpause 01–08 Uhr“.
5. Hat der User zwischendurch gestartet → keine Erstattung, Eintrag „Nachtpause unterbrochen“.

### 3.5 Ablauf
1. 3 Tage vorher: Warnung auf der Startseite.
2. Ablaufzeitpunkt: Auto-Verlängern an? → 7 Tage zu 7 % Rabatt (+ Aktionen) abbuchen.
3. Nicht genug Coins / Auto-Verlängern aus → Server stoppen, Ordner ins Archiv verschieben, Container löschen, Tunnel frei, Warteliste benachrichtigen.
4. Startseite: „Mein Survival ist abgelaufen und archiviert – [Reaktivieren]“.

### 3.6 Reaktivieren
1. „Reaktivieren“ → Tage wählen → Preis wie beim Kauf.
2. RAM/Tunnel frei? Sonst „Aktuell nicht möglich“ + „Benachrichtige mich“.
3. Ordner zurück, Container neu, Start. Ggf. neue Adresse → wird angezeigt.

### 3.7 Upgrade (Beispiel Holz → Eisen, 10 Resttage, ursprünglich 0 % Rabatt)
1. Preis: 10 × (30 − 10) × 1,00 = **200 Coins**.
2. RAM-Prüfung für den Mehr-RAM.
3. Abbuchen → Server neu starten mit 3 GB / 7 Spielern.

### 3.8 Coins / Server übertragen
1. Einstellungen → Übertragen → Benutzername des Empfängers + Betrag bzw. Server wählen.
2. Bestätigen (*Vorschlag*: mit Passwort).
3. Coins: zwei Buchungen in einer Transaktion. Server: Besitzer wechselt; OP/Whitelist bleiben, neuer Besitzer-OP wird ergänzt (*Vorschlag*).

### 3.9 Account löschen
1. Hinweis: „Alle Server und Coins werden gelöscht. Vorher übertragen?“ → Link zu Übertragen.
2. Passwort eingeben → bestätigen.
3. Server werden gelöscht (Archive ebenfalls, *Vorschlag*), Konto deaktiviert, Benutzername wieder frei.

### 3.10 Passwort vergessen
1. Login-Seite: „Passwort vergessen? Schreib eine E-Mail an k3009135@gmail.com“.
2. Admin → User → „Passwort zurücksetzen“ → zufälliges Passwort wird angezeigt + kopiert.
3. Admin schickt es per E-Mail; User loggt sich ein und muss es ändern (*Vorschlag*).

### 3.11 Gewinnspiel
1. Admin legt an: Coins pro Gewinner, Anzahl Gewinner, Tage.
2. Startseite zeigt es groß; User klickt „Teilnehmen“ (1× pro Konto).
3. Ende → Zufallsziehung → Buchungen → Gewinner-Meldung auf der Website.

### 3.12 Backup wiederherstellen
1. Reiter Backups → Datum wählen → „Wiederherstellen“ → Warnung „Aktueller Stand wird ersetzt (wird vorher gesichert)“.
2. Server stoppt → Sicherung → Zurückkopieren → Start.
