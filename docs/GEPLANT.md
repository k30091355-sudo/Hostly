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

## 2. Gesperrte Vorlagen wieder freigeben (später)
Survival, Creative, SkyBlock, OneBlock und Abenteuer sind seit 1.4.3 „Kommt bald …“ (Fehler im Betrieb, z. B. OneBlock).
Vor dem Freigeben jede Vorlage auf dem Mini-PC mit echtem Beitritt testen. Freigeben: `"soon": True` in
`hostly/extensions.py` entfernen.

