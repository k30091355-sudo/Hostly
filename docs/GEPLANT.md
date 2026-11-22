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
