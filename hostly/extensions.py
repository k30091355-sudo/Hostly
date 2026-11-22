"""Plugins, Mods, Datapacks auf einem Server (KONZEPT.md 15). Quelle: nur Modrinth (+ Admin-Uploads).

Die Website trägt Wünsche in `server_extensions` ein, der worker gleicht die Dateien ab (Auftrag "ext_sync").
"""
import sqlite3

from . import db, modrinth

# Templates: Server-Vorlagen (KONZEPT.md 20a). Verfügbarkeit wird beim Kauf über Modrinth geprüft.
TEMPLATES = {
    "vanilla": {"name": "Vanilla pur", "type": "VANILLA", "projects": [],
                "text": "Original-Minecraft ohne Extras."},
    "vanilla_plus": {"name": "Vanilla+", "type": "VANILLA", "projects": [("afk-display", "datapack"), ("veinminer", "datapack")],
                     "text": "Vanilla mit kleinen Komfort-Datapacks (AFK-Anzeige, Erz-Abbau in einem Rutsch)."},
    "survival": {"name": "Survival mit Freunden", "type": "PAPER",
                 "projects": [("essentialsx", "plugin"), ("luckperms", "plugin"), ("coreprotect", "plugin")],
                 "text": "Homes & Teleport (EssentialsX), Rechte (LuckPerms), Grief-Schutz (CoreProtect)."},
    "creative": {"name": "Creative", "type": "PAPER", "projects": [("worldedit", "plugin"), ("worldguard", "plugin")],
                 "text": "Bauen mit WorldEdit, Bereiche schützen mit WorldGuard."},
    "skyblock": {"name": "SkyBlock", "type": "PAPER", "projects": [("bentobox", "plugin"), ("bskyblock", "plugin")],
                 "text": "Klassisches SkyBlock mit BentoBox."},
    "oneblock": {"name": "OneBlock", "type": "PAPER", "projects": [("bentobox", "plugin"), ("aoneblock", "plugin")],
                 "text": "Ein einziger Block, aus dem alles kommt (BentoBox AOneBlock)."},
    "performance": {"name": "Performance-Vanilla", "type": "FABRIC",
                    "projects": [("lithium", "mod"), ("ferrite-core", "mod"), ("chunky", "mod")],
                    "text": "Schneller und sparsamer – ideal für Holz."},
    "adventure": {"name": "Abenteuer", "type": "FABRIC",
                  "projects": [("terralith", "mod"), ("yungs-better-dungeons", "mod"), ("lithium", "mod"),
                               ("ferrite-core", "mod")],
                  "text": "Neue Landschaften und Dungeons + Performance. Mit Modpack für Spieler."},
}

FABRIC_API = "fabric-api"   # Modrinth-Kürzel der Fabric API

FOLDERS = {"plugin": "plugins", "mod": "mods", "datapack": "datapacks"}


class ExtensionError(Exception):
    def __init__(self, message: str):
        self.message = message


def entry_from_version(server_type: str, kind: str, proj: dict, v: dict, is_dependency: bool = False) -> dict:
    f = modrinth.primary_file(v)
    return {
        "source": "modrinth", "kind": kind, "project_id": proj["id"], "slug": proj.get("slug"),
        "title": proj.get("title") or proj.get("slug"), "version_id": v["id"], "version_number": v.get("version_number"),
        "filename": f["filename"], "url": f["url"], "sha1": f.get("hashes", {}).get("sha1"),
        "sha512": f.get("hashes", {}).get("sha512"), "size": f.get("size", 0),
        "client_side": proj.get("client_side"), "is_dependency": int(is_dependency),
    }


def resolve(server_type: str, mc_version: str, project_ref: str, kind: str,
            version_id: str | None = None) -> list[dict]:
    """Projekt + benötigte Abhängigkeiten auflösen. Liefert Einträge für server_extensions."""
    proj = modrinth.project(project_ref)
    if proj is None:
        raise ExtensionError("Dieses Projekt gibt es auf Modrinth nicht.")
    loaders = modrinth.loaders_for(kind, server_type)
    v = modrinth.version(version_id) if version_id else modrinth.best_version(proj["id"], loaders, mc_version)
    if v is None or mc_version not in v.get("game_versions", []):
        raise ExtensionError(f"„{proj.get('title')}“ gibt es nicht für Minecraft {mc_version}.")
    result = [entry_from_version(server_type, kind, proj, v)]
    seen = {proj["id"]}
    queue = list(v.get("dependencies") or [])
    while queue:
        dep = queue.pop(0)
        if dep.get("dependency_type") != "required" or not dep.get("project_id") or dep["project_id"] in seen:
            continue
        seen.add(dep["project_id"])
        dproj = modrinth.project(dep["project_id"])
        if dproj is None:
            continue
        dloaders = loaders if kind != "datapack" else modrinth.DATAPACK_LOADERS
        dv = modrinth.version(dep["version_id"]) if dep.get("version_id") else \
            modrinth.best_version(dproj["id"], dloaders, mc_version)
        if dv is None:
            raise ExtensionError(f"Benötigte Abhängigkeit „{dproj.get('title')}“ gibt es nicht für {mc_version}.")
        result.append(entry_from_version(server_type, kind, dproj, dv, is_dependency=True))
        queue.extend(dv.get("dependencies") or [])
    if server_type == "FABRIC" and kind == "mod" and not any(e["slug"] == FABRIC_API for e in result):
        # Fast jede Fabric-Mod braucht die Fabric API – manche tragen das auf Modrinth nicht ein
        # (z. B. TabTPS). Ohne sie startet der Server nicht ("requires fabric-api, which is missing").
        fproj = modrinth.project(FABRIC_API)
        fv = modrinth.best_version(fproj["id"], loaders, mc_version) if fproj else None
        if fv is not None:
            result.append(entry_from_version(server_type, kind, fproj, fv, is_dependency=True))
    return result


def add_entries(conn: sqlite3.Connection, server_id: int, entries: list[dict]) -> int:
    """Einträge speichern (bereits vorhandene Projekte werden aktualisiert statt doppelt angelegt)."""
    added = 0
    for e in entries:
        existing = conn.execute(
            "SELECT id FROM server_extensions WHERE server_id = ? AND project_id = ?", (server_id, e["project_id"])
        ).fetchone()
        if existing:
            if not e["is_dependency"]:
                conn.execute(
                    """UPDATE server_extensions SET version_id = ?, version_number = ?, filename = ?, url = ?,
                       sha1 = ?, sha512 = ?, size = ?, enabled = 1, is_dependency = 0 WHERE id = ?""",
                    (e["version_id"], e["version_number"], e["filename"], e["url"], e["sha1"], e["sha512"],
                     e["size"], existing["id"]),
                )
            continue
        conn.execute(
            """INSERT INTO server_extensions (server_id, source, kind, project_id, slug, title, version_id,
               version_number, filename, url, sha1, sha512, size, client_side, is_dependency)
               VALUES (:server_id, :source, :kind, :project_id, :slug, :title, :version_id, :version_number,
                       :filename, :url, :sha1, :sha512, :size, :client_side, :is_dependency)""",
            {**e, "server_id": server_id},
        )
        added += 1
    return added


def mark_changed(conn: sqlite3.Connection, server_id: int, user_id: int | None) -> None:
    conn.execute("UPDATE servers SET needs_restart = 1 WHERE id = ?", (server_id,))
    pending = conn.execute(
        "SELECT 1 FROM jobs WHERE server_id = ? AND kind = 'ext_sync' AND status = 'pending'", (server_id,)
    ).fetchone()
    if not pending:
        db.add_job(conn, "ext_sync", server_id, user_id)


def plan_change(conn: sqlite3.Connection, server: sqlite3.Row, new_type: str, new_version: str) -> dict:
    """Vorab-Prüfung für Versions-/Typwechsel: was wird aktualisiert, was deaktiviert?"""
    update, disable = [], []
    allowed = modrinth.kinds_for(new_type)
    rows = conn.execute(
        "SELECT * FROM server_extensions WHERE server_id = ? AND enabled = 1", (server["id"],)).fetchall()
    for row in rows:
        if row["source"] != "modrinth":
            if row["kind"] not in allowed:
                disable.append({"row": dict(row), "reason": "passt nicht zum Server-Typ"})
            continue
        if row["kind"] not in allowed:
            disable.append({"row": dict(row), "reason": "passt nicht zum Server-Typ"})
            continue
        v = modrinth.best_version(row["project_id"], modrinth.loaders_for(row["kind"], new_type), new_version)
        if v is None:
            disable.append({"row": dict(row), "reason": f"nicht verfügbar für {new_version}"})
        elif v["id"] != row["version_id"]:
            update.append({"row": dict(row), "version": v})
    return {"update": update, "disable": disable}


def apply_change(conn: sqlite3.Connection, server: sqlite3.Row, plan: dict) -> None:
    for item in plan["update"]:
        f = modrinth.primary_file(item["version"])
        conn.execute(
            """UPDATE server_extensions SET version_id = ?, version_number = ?, filename = ?, url = ?, sha1 = ?,
               sha512 = ?, size = ? WHERE id = ?""",
            (item["version"]["id"], item["version"].get("version_number"), f["filename"], f["url"],
             f.get("hashes", {}).get("sha1"), f.get("hashes", {}).get("sha512"), f.get("size", 0), item["row"]["id"]),
        )
    for item in plan["disable"]:
        conn.execute("UPDATE server_extensions SET enabled = 0 WHERE id = ?", (item["row"]["id"],))


def pick_template_version(template_key: str) -> tuple[str, list[dict]]:
    """Neueste Minecraft-Version, für die alle Plugins/Mods der Vorlage verfügbar sind."""
    tpl = TEMPLATES[template_key]
    if not tpl["projects"]:
        return "LATEST", []
    for mc_version in modrinth.mojang_releases(8):
        if not modrinth.server_supports(tpl["type"], mc_version):
            continue   # z. B. Paper gibt es für die allerneueste Version noch nicht
        try:
            entries = []
            for slug, kind in tpl["projects"]:
                entries.extend(resolve(tpl["type"], mc_version, slug, kind))
            return mc_version, entries
        except ExtensionError:
            continue
    raise ExtensionError("Diese Vorlage ist gerade nicht verfügbar. Bitte später erneut versuchen.")


def find_updates(conn: sqlite3.Connection, server: sqlite3.Row) -> list[dict]:
    """Neuere Versionen für installierte Modrinth-Plugins/Mods/Datapacks (gleiche Minecraft-Version)."""
    if server["mc_version"] == "LATEST":
        return []
    result = []
    rows = conn.execute("SELECT * FROM server_extensions WHERE server_id = ? AND enabled = 1 AND source = 'modrinth'",
                        (server["id"],)).fetchall()
    for row in rows:
        try:
            v = modrinth.best_version(row["project_id"], modrinth.loaders_for(row["kind"], server["type"]),
                                      server["mc_version"])
        except (modrinth.ModrinthError, KeyError):
            continue
        if v is None or v["id"] == row["version_id"]:
            continue
        if row["version_id"]:
            try:   # nur wirklich neuere Versionen (nicht, wenn jemand absichtlich eine neuere Vorabversion gewählt hat)
                cur = modrinth.version(row["version_id"])
                if cur and (cur.get("date_published") or "") > (v.get("date_published") or ""):
                    continue
            except modrinth.ModrinthError:
                pass
        result.append({"row": dict(row), "version": v})
    return result


def apply_updates(conn: sqlite3.Connection, server: sqlite3.Row, updates: list[dict]) -> int:
    apply_change(conn, server, {"update": updates, "disable": []})
    return len(updates)
