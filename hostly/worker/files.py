"""Datei-Arbeiten des workers: Plugins/Mods abgleichen, Backups, Welten, Dateimanager, /code-Datapack."""
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from .. import config, minecraft
from ..extensions import FOLDERS
from ..modrinth import USER_AGENT

log = logging.getLogger("hostly.worker")
MANIFEST = ".hostly-managed.json"
ALLOWED_DOWNLOAD = "https://cdn.modrinth.com/"
BACKUP_BWLIMIT = "5000"                           # KB/s ≈ 5 MB/s – Schnecken-Tempo


def chown(path: Path) -> None:
    if os.geteuid() == 0:
        try:
            os.chown(path, 1000, 1000, follow_symlinks=False)
        except OSError:
            pass


def fix_owner(path: Path) -> int:
    """Alles unter `path` dem normalen Benutzer (1000) geben – so wie im Minecraft-Container und der Website.

    Der worker läuft als root; Ordner, die er anlegt (z. B. world/, mods/, uploads/icons/), gehörten sonst
    root, und Minecraft bzw. die Website dürften dort nicht schreiben (z. B. Fehler „world/session.lock“).
    Ändert nur, was nicht schon 1000 gehört."""
    if os.geteuid() != 0 or not path.exists():
        return 0
    fixed = 0
    for root, dirs, names in os.walk(path):
        for name in [None, *dirs, *names]:
            p = root if name is None else os.path.join(root, name)
            try:
                st = os.lstat(p)
                if st.st_uid != 1000 or st.st_gid != 1000:
                    os.chown(p, 1000, 1000, follow_symlinks=False)
                    fixed += 1
            except OSError:
                pass
    return fixed


def slow_cmd(cmd: list[str]) -> list[str]:
    """Befehl mit niedrigster CPU- und Festplatten-Priorität ausführen."""
    prefix = ["nice", "-n", "19"]
    if shutil.which("ionice"):
        prefix += ["ionice", "-c3"]
    return prefix + cmd


# ---------- Plugins / Mods / Datapacks abgleichen ----------

def ext_paths(server, row) -> tuple[Path, Path]:
    data = minecraft.data_dir(server["id"])
    folder = FOLDERS[row["kind"]]
    active_dir = data / (server["level_name"] or "world") / "datapacks" if row["kind"] == "datapack" else data / folder
    sub = row["subfolder"] if "subfolder" in row.keys() and row["subfolder"] else ""
    if sub:   # z. B. BentoBox/addons – nur einfache Ordnernamen erlaubt
        sub = "/".join(p for p in sub.split("/") if p and p not in (".", ".."))
        active_dir = active_dir / sub
    return active_dir / row["filename"], data / "hostly-disabled" / folder / row["filename"]


def download(url: str, dest: Path, sha1: str | None) -> None:
    if not url.startswith(ALLOWED_DOWNLOAD):
        raise RuntimeError("Download nur von Modrinth erlaubt.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha1()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(65536):
            h.update(chunk)
            f.write(chunk)
    if sha1 and h.hexdigest() != sha1:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Prüfsumme falsch für {dest.name}")
    tmp.rename(dest)
    chown(dest)


def _bentobox_check(conn, server, row):
    """Sicherheitsnetz: liegt ein BentoBox-Addon (Datei mit addon.yml) direkt in plugins/, gehört es nach
    plugins/BentoBox/addons/. Dann Datenbank anpassen und die Datei verschieben."""
    from ..extensions import BENTOBOX_ADDONS, is_bentobox_addon_jar
    if row["kind"] != "plugin" or row["subfolder"]:
        return row
    active, _ = ext_paths(server, row)
    if not active.exists() or not is_bentobox_addon_jar(active):
        return row
    conn.execute("UPDATE server_extensions SET subfolder = ? WHERE id = ?", (BENTOBOX_ADDONS, row["id"]))
    row = conn.execute("SELECT * FROM server_extensions WHERE id = ?", (row["id"],)).fetchone()
    new_active, _ = ext_paths(server, row)
    new_active.parent.mkdir(parents=True, exist_ok=True)
    active.rename(new_active)
    chown(new_active.parent)
    return row


def sync_extensions(conn, server) -> str:
    data = minecraft.data_dir(server["id"])
    data.mkdir(parents=True, exist_ok=True)
    manifest_path = data / MANIFEST
    try:
        old = set(json.loads(manifest_path.read_text()))
    except (OSError, ValueError):
        old = set()
    rows = conn.execute("SELECT * FROM server_extensions WHERE server_id = ?", (server["id"],)).fetchall()
    keep, done = set(), 0
    rows = [_bentobox_check(conn, server, r) for r in rows]
    for row in rows:
        active, disabled = ext_paths(server, row)
        keep.update({str(active.relative_to(data)), str(disabled.relative_to(data))})
        want, other = (active, disabled) if row["enabled"] else (disabled, active)
        if want.exists():
            continue
        want.parent.mkdir(parents=True, exist_ok=True)
        if other.exists():
            other.rename(want)
        elif row["enabled"]:
            if row["source"] == "modrinth":
                download(row["url"], want, row["sha1"])
                if row["kind"] == "plugin" and not row["subfolder"]:
                    row = _bentobox_check(conn, server, row)
                    active, disabled = ext_paths(server, row)
                    keep.update({str(active.relative_to(data)), str(disabled.relative_to(data))})
            else:
                src = config.UPLOADS_DIR / "admin-files" / str(server["id"]) / row["filename"]
                if src.exists():
                    shutil.copyfile(src, want)
                    chown(want)
        done += 1
    for rel in old - keep:   # entfernte Erweiterungen löschen
        (data / rel).unlink(missing_ok=True)
    manifest_path.write_text(json.dumps(sorted(keep)))
    return f"{done} Dateien geändert"


# ---------- /code-Datapack (Server-Kürzel im Spiel: /trigger code) ----------

def write_rules_datapack(server) -> None:
    """Gamerules als Datapack: werden bei jedem Serverstart gesetzt – nur mit den Namen, die zur
    Minecraft-Version passen (alte camelCase-Namen bis 1.21.10, neue snake_case-Namen ab 1.21.11/26.x)."""
    from .. import gamesettings
    root = minecraft.data_dir(server["id"]) / (server["level_name"] or "world") / "datapacks" / "hostly-rules"
    cmds = gamesettings.commands_for(server)
    if not cmds:
        shutil.rmtree(root, ignore_errors=True)
        return
    meta = {"pack": {"description": "Hostly: Gamerules", "pack_format": 48,
                     "supported_formats": {"min_inclusive": 4, "max_inclusive": 999},
                     "min_format": 4, "max_format": 999}}
    shutil.rmtree(root, ignore_errors=True)   # alte Fassung (mit zwei Funktionen) entfernen
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps(meta))
    tag = {"values": ["hostly_rules:apply"]}
    for folder in ("function", "functions"):
        d = root / "data" / "hostly_rules" / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / "apply.mcfunction").write_text("\n".join(cmds) + "\n", encoding="utf-8")
        tags = root / "data" / "minecraft" / ("tags/function" if folder == "function" else "tags/functions")
        tags.mkdir(parents=True, exist_ok=True)
        (tags / "load.json").write_text(json.dumps(tag))
    for p in [root, *root.rglob("*")]:
        chown(p)


def write_code_datapack(server, public_url: str | None) -> None:
    root = minecraft.data_dir(server["id"]) / (server["level_name"] or "world") / "datapacks" / "hostly-code"
    link = f"{public_url.rstrip('/')}/s/{server['short_code']}" if public_url else ""
    meta = {"pack": {"description": "Hostly: /trigger code", "pack_format": 48,
                     "supported_formats": {"min_inclusive": 4, "max_inclusive": 999},
                     "min_format": 4, "max_format": 999}}
    text = [{"text": "Server-Kürzel: ", "color": "gray"}, {"text": server["short_code"], "color": "green", "bold": True}]
    if link:
        text += [{"text": " – Statistiken: ", "color": "gray"},
                 {"text": link, "color": "aqua", "underlined": True,
                  "clickEvent": {"action": "open_url", "value": link}, "click_event": {"action": "open_url", "url": link}}]
    show = f"tellraw @s {json.dumps(text, ensure_ascii=False)}\nscoreboard players set @s code 0\n"
    files = {
        "load.mcfunction": "scoreboard objectives add code trigger\n",
        "tick.mcfunction": "scoreboard players enable @a code\nexecute as @a[scores={code=1..}] run function hostly:show\n",
        "show.mcfunction": show,
    }
    (root).mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(json.dumps(meta))
    for folder in ("function", "functions"):   # neue und alte Minecraft-Versionen
        d = root / "data" / "hostly" / folder
        d.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (d / name).write_text(content, encoding="utf-8")
        tags = root / "data" / "minecraft" / ("tags/function" if folder == "function" else "tags/functions")
        tags.mkdir(parents=True, exist_ok=True)
        (tags / "load.json").write_text(json.dumps({"values": ["hostly:load"]}))
        (tags / "tick.json").write_text(json.dumps({"values": ["hostly:tick"]}))
    for p in [root, *root.rglob("*")]:
        chown(p)


# ---------- Backups (rsync mit Hardlinks, Schnecken-Tempo) ----------

def make_backup(src: Path, dest: Path, previous: Path | None, slow: bool = True) -> int:
    """Inkrementelle Kopie. Liefert die Größe der neu kopierten Dateien."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--delete", "--stats", "--exclude", ".paused", "--exclude", ".skip-pause"]
    if previous and previous.exists():
        cmd.append(f"--link-dest={previous}")
    if slow:
        cmd.append(f"--bwlimit={BACKUP_BWLIMIT}")
    cmd += [f"{src}/", f"{dest}/"]
    out = subprocess.run(slow_cmd(cmd), check=True, capture_output=True, text=True, timeout=12 * 3600).stdout
    m = re.search(r"Total transferred file size: ([\d,.]+)", out)
    return int(re.sub(r"[^\d]", "", m.group(1))) if m else 0


def restore_backup(src: Path, dest: Path) -> None:
    """Zurückkopieren – mit niedriger Priorität, aber ohne Tempo-Grenze (der User wartet)."""
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(slow_cmd(["rsync", "-a", "--delete", f"{src}/", f"{dest}/"]), check=True, timeout=6 * 3600)


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        out = subprocess.run(slow_cmd(["du", "-sb", str(path)]), capture_output=True, text=True, timeout=3600).stdout
        return int(out.split()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return 0


# ---------- Welten ----------

def extract_world(zip_path: Path, dest: Path) -> None:
    """Welt-ZIP entpacken (Schutz gegen ../-Tricks). Ordner mit level.dat wird zur Welt."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        level = [n for n in names if n.endswith("level.dat") and n.count("/") <= 2]
        if not level:
            raise RuntimeError("In der ZIP-Datei ist keine Welt (level.dat fehlt).")
        prefix = min(level, key=len)[: -len("level.dat")]
        tmp = dest.with_name(dest.name + ".part")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for info in zf.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            rel = info.filename[len(prefix):]
            target = (tmp / rel).resolve()
            if not str(target).startswith(str(tmp.resolve()) + os.sep):
                raise RuntimeError("Ungültige Datei in der ZIP.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as srcf, open(target, "wb") as out:
                shutil.copyfileobj(srcf, out)
    if dest.exists():
        shutil.rmtree(dest)
    tmp.rename(dest)
    for p in [dest, *dest.rglob("*")]:
        chown(p)


def paper_worlds_to_vanilla(data: Path, level: str) -> None:
    """Paper speichert Nether/End in eigenen Ordnern (world_nether/DIM-1, world_the_end/DIM1).
    Vanilla/Fabric erwarten sie in world/DIM-1 und world/DIM1 – beim Typwechsel verschieben,
    sonst wären Nether und End scheinbar „weg“. (Andersherum wandelt Paper selbst um.)"""
    for folder, dim in ((f"{level}_nether", "DIM-1"), (f"{level}_the_end", "DIM1")):
        src, dst = data / folder / dim, data / level / dim
        if src.is_dir() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
