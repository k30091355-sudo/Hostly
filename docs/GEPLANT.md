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

**Fehlersuche vom 24.11.2026 (noch NICHT eingebaut – Wunsch des Besitzers):** Alle fünf Vorlagen mit echtem
Paper/Fabric, echten Plugins von Modrinth und einem Test-Spieler (Bot, tritt wie ein echter Spieler bei) geprüft.
Technisch starten alle ohne Fehler; die Probleme liegen in der Einrichtung der Plugins:

| Vorlage | Was der Spieler erlebt | Ursache | Getestete Lösung |
|---|---|---|---|
| **OneBlock** | Landet in einer ganz normalen Welt, „nichts mit OneBlock“ | AOneBlock erstellt die Insel erst nach `/ob`; `create-island-on-first-login` steht auf `false` | In `plugins/BentoBox/addons/AOneBlock/config.yml` → `island.create-island-on-first-login.enable: true`: Neuer Spieler bekommt nach 5 s automatisch seine Insel und wird hingebracht ✔. Der Block selbst funktioniert (Gras → Holz → Stein → Blätter …), auch nach Neustart ✔ |
| **SkyBlock** | Wie OneBlock; nach `/island` öffnet sich ein Auswahl-Menü | gleiche Einstellung in `plugins/BentoBox/addons/BSkyBlock/config.yml` | wie OneBlock (`enable: true`); Insel + Nether + End werden gebaut ✔ |
| **Survival** | `/home`, `/sethome`, `/tpa`, `/back` → „You do not have access to that command“ (nur der Besitzer/OP darf) | LuckPerms ist installiert, aber die Standard-Gruppe hat keine Rechte; EssentialsX nutzt dann nur LuckPerms | (a) einmalig `lp group default permission set essentials.home true` usw. (sethome, home, tpa, tpaccept, back, spawn) ✔, **oder** (b) LuckPerms weglassen und in `plugins/Essentials/config.yml` `use-bukkit-permissions: false` → EssentialsX-Liste „player-commands“ gilt ✔. `/spawn` fehlt (EssentialsXSpawn nicht dabei), Vault fehlt (Chat-Präfixe) |
| **Creative** | Spieler sind im **Überlebensmodus**; `//wand` „Unknown command“, `/rg` „no permission“ | Die Vorlage setzt keinen Spielmodus; WorldEdit/WorldGuard sind ohne Rechte-Plugin nur für OPs | Beim Kauf `gamemode = creative` setzen (+ ggf. `FORCE_GAMEMODE`) → neue Spieler im Kreativmodus ✔. WorldEdit für alle bräuchte Rechte (LuckPerms + `worldedit.*`) – oder bewusst nur für den Besitzer lassen |
| **Abenteuer** | funktioniert: normaler Minecraft-Client kann beitreten ✔, Terralith-Biome und YUNG-Dungeons sind in der Welt ✔ | – | nur noch auf dem Mini-PC mit echtem Spieler bestätigen (Speicher bei Holz beobachten) |

Gegengeprüft (freigeschaltet, funktionieren mit Test-Spieler): Performance-Vanilla, Vanilla+, Vanilla pur.
Hinweis: Hostly wählt für Creative/SkyBlock/OneBlock Minecraft 26.3, für Survival/Abenteuer 26.1.2 (dort fehlen
Plugins für 26.3). Der Test-Spieler kann nur bis 26.1.x beitreten – die 26.3-Server wurden ohne Beitritt geprüft
(Start, Plugins geladen, Welten erstellt, zweiter Start mit Lag-Schutz ohne Fehler).

