# Geplante Updates (noch nicht umgesetzt)

> Hier sammeln wir Wünsche des Besitzers, die später in einem Update umgesetzt werden.
> Wenn ein Punkt erledigt ist: hier löschen und in `docs/UPDATE.md` als Update eintragen.

## 1. Neues Logo: „Server-Rack“ (Vorschlag Nr. 3) – entschieden am 22.11.2026
- **Entwurf:** [`docs/entwuerfe/logo-server-rack.svg`](entwuerfe/logo-server-rack.svg)
  (alle 5 Vorschläge zum Vergleich: [`docs/entwuerfe/logo-vorschlaege.png`](entwuerfe/logo-vorschlaege.png))
- Aussehen: blaues abgerundetes Quadrat (`#2563eb`), drei weiße Server-Einschübe,
  links je ein grünes „läuft“-Lämpchen (`#22c55e`), rechts hellblaue Striche (`#93c5fd`).
- **Überall einsetzen:**
  - `hostly/web/static/favicon.svg` (Tab-Symbol + Logo in der Kopfzeile)
  - `hostly/web/static/icon-192.png`, `icon-512.png` (Handy-App-Symbol / PWA) – aus dem SVG neu erzeugen
  - PWA-Manifest: `theme_color` auf Blau
  - Code-Bild (Admin → Codes, `drawCodeCard` in `hostly/web/static/js/hostly.js`): Farben von Grün auf Blau
- **Website-Farben passend zum Logo auf Blau umstellen** (in `hostly/web/static/css/hostly.css`,
  Farb-Variablen für Hell- und Dunkel-Modus). Grüne Farbe nur noch für „gut/läuft/Plus“-Hinweise.
- Danach Sichttest Hell/Dunkel + Handy, Service-Worker-Cache-Version (`hostly-v1` → `hostly-v2`) erhöhen,
  damit Browser das neue Design laden.

## 2. Neues Design in Blau – entschieden am 22.11.2026
**Beispielbilder:** [`pc-light.png`](entwuerfe/pc-light.png) · [`pc-dark.png`](entwuerfe/pc-dark.png) ·
[`handy-light.png`](entwuerfe/handy-light.png) · [`handy-dark.png`](entwuerfe/handy-dark.png)
**Beispiel-Code (alle Farben/Abstände):** [`entwuerfe/design-beispiel.html`](entwuerfe/design-beispiel.html)
(Theme umschalten: im `<html>`-Tag `data-theme="dark"` setzen)

Gewünscht:
- **Blau als Hauptfarbe** (Hell: `#2563eb`, Dunkel: `#3b82f6`). Grün nur noch für „läuft / gut / Coins-Plus“.
- **Dark-Mode in Dunkelblau** (Hintergrund `#0a1324`, Karten `#111d35`) statt Grau-Schwarz.
- **Weiche Schatten unter den Karten** statt harter Rahmen, beim Drüberfahren leicht anheben.
- **Coins immer sichtbar oben rechts** mit **goldener Münze** als eigenes Bild (SVG) – kein Emoji 🪙 mehr,
  weil das auf Handys silbern aussieht. Goldenes Abzeichen (hell: helles Gold, dunkel: dunkles Gold).
  Auch an anderen Stellen mit 🪙 (z. B. Einstellungen → Coin-Verlauf) die goldene Münze nehmen.
- **Kopfzeile leicht durchsichtig mit Unschärfe** (`backdrop-filter: blur`) beim Scrollen.
- **Status als farbiger Punkt mit Text:** 🟢 Online (Punkt pulsiert leicht), 🔵 Schläft, ⚪ Aus, 🔴 Abgestürzt.
- **Server-Karten mit Balken:** Spieler „2 / 7“ als Balken (grün), Restlaufzeit als Balken
  (blau; gelb bei ≤ 7 Tagen, rot bei ≤ 3 Tagen), dazu Verbindungsadresse mit „Kopieren“.
- **Schönere Leer-Anzeigen** mit kleinem Bild (SVG, passt sich Hell/Dunkel an) und Knopf,
  z. B. „Noch kein Server → Ersten Server mieten“. Auch für: keine Benachrichtigungen, keine Codes eingelöst,
  keine Gewinnspiele, keine Backups.

Hinweis zur Umsetzung: zusammen mit Punkt 1 (Logo) machen; Farben nur über die Variablen in `hostly.css` ändern;
`prefers-reduced-motion` beachten (kein Pulsieren/Anheben, wenn der Nutzer das abgeschaltet hat).
