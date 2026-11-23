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

## 2. Neue Startseite im Stil von Idee D (gewählt, wartet auf „bauen“)
**Vorschau:** [`entwuerfe/startseite-ideen.html`](entwuerfe/startseite-ideen.html) ·
Besucher [`PC`](entwuerfe/startseite-d.png) [`Handy`](entwuerfe/startseite-d-handy.png) ·
Eingeloggt [`hell`](entwuerfe/startseite-d-eingeloggt.png) [`dunkel`](entwuerfe/startseite-d-eingeloggt-dunkel.png) [`Handy`](entwuerfe/startseite-d-eingeloggt-handy.png)
(Ideen A–C liegen auch noch dort, wurden aber nicht gewählt.)
- **Besucher:** große Überschrift „Dein eigener Minecraft-Server. Komplett kostenlos.“, Live-Zahlen
  (Spieler heute, Server aktiv, 0 €), Registrieren-Knopf mit Startbonus, die 3 Modelle, öffentliche Server, „So geht's“.
- **Eingeloggt:** gleicher Stil: „Willkommen zurück, Name!“, Knöpfe Kaufen/Code/Meine Server, Warnungen als Streifen,
  Zahlen (Coins ≈ Wochen, deine Server, Spieler online, Tage übrig), „Deine Server“ als Karten + Karte „Neuer Server“
  (zeigt, welche Modelle gerade Platz haben), Aktion als Streifen mit Countdown, öffentliche Server, „Was ist passiert?“
  (Beitritte, Whitelist-Anfragen, Gewinnspiele, Meldungen).
- Aufwand: mittel → **Version 1.4.0**.
