# Geplante Updates (noch nicht umgesetzt)

> Hier sammeln wir Wünsche des Besitzers, die später in einem Update umgesetzt werden.
> Wenn ein Punkt erledigt ist: hier löschen und in `docs/UPDATE.md` als Version eintragen.

## 1. Schrift „Inter“ + sanfte Übergänge – Design-Idee (wartet auf Entscheidung)
**Vorschau:** [`entwuerfe/inter-hell.png`](entwuerfe/inter-hell.png) · [`entwuerfe/inter-dunkel.png`](entwuerfe/inter-dunkel.png)
- Schrift **Inter** (modern, sehr gut lesbar, auf allen Geräten gleich). Datei liegt **direkt auf dem Mini-PC**
  (`hostly/web/static/fonts/`, ca. 50 KB, variable Schriftstärke) – nichts wird von außen geladen.
  Adressen/Konsole bleiben in Monospace-Schrift.
- **Sanfte Übergänge:** Karten heben sich beim Drüberfahren an (gibt es schon bei Server-Karten → überall),
  Knöpfe „drücken“ sich beim Klick kurz ein, Seiteninhalt blendet beim Seitenwechsel weich ein (0,2 s),
  Reiter-Unterstrich gleitet. Alles aus, wenn „Bewegung reduzieren“ im System eingeschaltet ist.
- Aufwand: klein (nur CSS + Schriftdatei) → wäre **Version 1.3.1**.

## 2. Neue Startseite mit Widgets – 4 Ideen (wartet auf Entscheidung)
**Vorschau:** [`entwuerfe/startseite-ideen.html`](entwuerfe/startseite-ideen.html) ·
A [`hell`](entwuerfe/startseite-a.png) [`dunkel`](entwuerfe/startseite-a-dunkel.png) [`Handy`](entwuerfe/startseite-a-handy.png) ·
B [`hell`](entwuerfe/startseite-b.png) · C [`hell`](entwuerfe/startseite-c.png) [`dunkel`](entwuerfe/startseite-c-dunkel.png) · D [`Besucher`](entwuerfe/startseite-d.png)
- **A „Mein Cockpit“:** Begrüßung + Widget-Raster (Meine Server mit Balken, Coins mit Verlauf, Aktion-Countdown, Gerade online, Platz im Hostly).
- **B „Server im Mittelpunkt“:** großer blauer Hauptserver oben (Adresse, Knöpfe, Spieler, Restzeit, RAM, Umschalter), darunter „Was ist passiert?“-Verlauf.
- **C „Bento-Kacheln“:** verschieden große Kacheln (Spieler-Kurve, Coins, Online, Code direkt einlösen, Platz-Ring, beliebte Server, Gewinnspiel).
- **D Besucher-Startseite:** große Überschrift, Live-Zahlen, Modelle, öffentliche Server, „So geht's“.
- Widgets sind mischbar. Aufwand: mittel → wäre **Version 1.4.0**.
