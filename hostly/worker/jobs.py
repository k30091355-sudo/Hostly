"""Aufträge aus der Tabelle `jobs` ausführen (Start, Stopp, Konsole, Archiv …)."""
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

from .. import config, console, db, gamesettings, minecraft, rcon, servers
from ..timeutil import now_sql
from . import files

log = logging.getLogger("hostly.worker")


class Worker:
    """Bündelt Docker-Zugriff und Datenbank. `ops` kann in Tests durch eine Attrappe ersetzt werden."""

    def __init__(self, ops, rcon_func=None):
        self.ops = ops
        self.rcon = rcon_func or rcon.command_retry

    # ---------- Hilfen ----------

    def conn(self) -> sqlite3.Connection:
        return db.connect()

    def load(self, conn, server_id: int):
        return conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()

    def server_rcon(self, conn, server, cmd: str, attempts: int = 8) -> str:
        tunnel = conn.execute("SELECT * FROM tunnels WHERE id = ?", (server["tunnel_id"],)).fetchone()
        if tunnel is None:
            raise rcon.RconError("Server hat keinen Tunnel-Platz")
        return self.rcon(tunnel["internal_ip"], config.RCON_PORT, server["rcon_password"], cmd, attempts=attempts)

    def is_paused(self, server_id: int) -> bool:
        return (minecraft.data_dir(server_id) / ".paused").exists()

    def clear_stale_pause(self, server_id: int, st: dict) -> None:
        """`.paused` von einem früheren Container-Lauf entfernen. itzg legt die Datei beim Einfrieren an, löscht
        sie aber beim Containerstart nicht. Wurde der Mini-PC mit einem eingefrorenen Server heruntergefahren,
        bliebe sie liegen – Hostly hielte den laufenden Server dann für eingefroren (keine Spielerzahl, falscher
        Status). Echte Pausen entstehen immer NACH dem Containerstart."""
        flag = minecraft.data_dir(server_id) / ".paused"
        started = st.get("started_at")
        try:
            if started and st.get("running") and flag.stat().st_mtime < started:
                flag.unlink()
                log.info("Veraltete .paused-Datei von Server %s entfernt", server_id)
        except OSError:
            pass

    def spec_for(self, conn, server) -> dict:
        model = servers.model(conn, server["model_id"])
        tunnel = conn.execute("SELECT * FROM tunnels WHERE id = ?", (server["tunnel_id"],)).fetchone()
        owner = conn.execute("SELECT minecraft_name FROM users WHERE id = ?", (server["owner_id"],)).fetchone()
        ops = [owner["minecraft_name"]] if owner and owner["minecraft_name"] else []
        wl = [r[0] for r in conn.execute(
            "SELECT minecraft_name FROM whitelist WHERE server_id = ? ORDER BY minecraft_name", (server["id"],))]
        return minecraft.build_spec(server, model, tunnel, ops, wl)

    def prepare_data_dir(self, server) -> None:
        path = minecraft.data_dir(server["id"])
        path.mkdir(parents=True, exist_ok=True)
        (path / ".paused").unlink(missing_ok=True)   # der neue Container startet wach
        if minecraft.has_icon(server):
            shutil.copyfile(minecraft.icon_file(server["id"]), path / "server-icon.png")
        else:   # kein eigenes Icon → auch kein altes im Spiel anzeigen
            (path / "server-icon.png").unlink(missing_ok=True)
        _chown_tree_top(path)

    def clear_leftovers(self, server_id: int, keep_icon: bool = False) -> None:
        """Ein NEUER Server darf nichts von einem früheren Server mit derselben Nummer erben
        (Welt, Icon, Backups) – z. B. nach dem Zurücksetzen aller Accounts. Alte Reste werden nicht gelöscht,
        sondern nach /srv/hostly/verwaist/ verschoben."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = config.DATA_DIR / "verwaist" / f"server-{server_id}-{stamp}"
        for name, path in (("daten", minecraft.data_dir(server_id)), ("archiv", minecraft.archive_dir(server_id)),
                           ("backups", minecraft.backup_dir(server_id)),
                           ("dateien", config.UPLOADS_DIR / "admin-files" / str(server_id))):
            if path.exists():
                target.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target / name))
                log.warning("Reste eines früheren Servers %s nach %s verschoben", server_id, target / name)
        icon = minecraft.icon_file(server_id)
        if icon.exists() and not keep_icon:
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(icon), str(target / "icon.png"))

    def recreate(self, conn, server) -> None:
        server = self.load(conn, server["id"])
        # läuft der alte Container noch (z. B. „Starten“ bei eingefrorenem Server), erst sauber beenden –
        # sonst wartet Docker 60 s auf den eingefrorenen Prozess und beendet ihn dann hart
        self.graceful_stop(conn, server)
        self.prepare_data_dir(server)
        files.sync_extensions(conn, server)
        try:
            files.write_code_datapack(server, db.get_setting(conn, "public_url"))
        except OSError:
            log.warning("/code-Datapack für Server %s konnte nicht geschrieben werden", server["id"])
        try:
            files.write_rules_datapack(server)
        except OSError:
            log.warning("Gamerule-Datapack für Server %s konnte nicht geschrieben werden", server["id"])
        try:
            files.tune_paper(server, servers.model(conn, server["model_id"])["cpu_limit"])
        except OSError:
            log.warning("paper-global.yml für Server %s nicht anpassbar", server["id"])
        spec = self.spec_for(conn, server)
        if "WHITELIST" not in spec["env"]:
            # leere Whitelist: itzg gleicht nur ab, wenn Namen da sind – sonst blieben alte Einträge erlaubt
            wl = minecraft.data_dir(server["id"]) / "whitelist.json"
            if wl.exists():
                wl.write_text("[]", encoding="utf-8")
        files.fix_owner(minecraft.data_dir(server["id"]))   # Minecraft (Benutzer 1000) muss überall schreiben dürfen
        self.ops.recreate(spec)
        conn.execute("UPDATE servers SET needs_restart = 0, crash_locked = 0 WHERE id = ?", (server["id"],))

    def awake(self, server) -> bool:
        return (server["state"] == "active"
                and self.ops.state(minecraft.container_name(server["id"]))["running"]
                and not self.is_paused(server["id"]))

    def backup(self, conn, server, kind: str) -> int:
        """Backup anlegen (inkrementell, Schnecken-Tempo). Eingefrorene Server werden NICHT geweckt."""
        src = minecraft.data_dir(server["id"])
        if not src.exists():
            return 0
        files.check_disk_space()
        prev = conn.execute(
            "SELECT folder FROM backups WHERE server_id = ? AND status = 'fertig' ORDER BY id DESC LIMIT 1",
            (server["id"],)).fetchone()
        base = minecraft.backup_dir(server["id"])
        cur = conn.execute("INSERT INTO backups (server_id, folder, kind, status) VALUES (?, '', ?, 'laeuft')",
                           (server["id"], kind))
        backup_id = cur.lastrowid
        folder = time.strftime("%Y-%m-%d_%H%M%S") + f"_{backup_id}"   # eindeutig, auch bei 2 Backups pro Sekunde
        conn.execute("UPDATE backups SET folder = ? WHERE id = ?", (folder, backup_id))
        awake = self.awake(server)
        try:
            if awake:
                self.server_rcon(conn, server, "save-off")
                self.server_rcon(conn, server, "save-all flush")
            size = files.make_backup(src, base / folder, base / prev["folder"] if prev else None, slow=True)
            conn.execute("UPDATE backups SET status = 'fertig', size_bytes = ? WHERE id = ?", (size, backup_id))
        except Exception:
            conn.execute("UPDATE backups SET status = 'fehler' WHERE id = ?", (backup_id,))
            raise
        finally:
            if awake:
                try:
                    self.server_rcon(conn, server, "save-on")
                except rcon.RconError:
                    log.warning("save-on fehlgeschlagen für Server %s", server["id"])
        return backup_id

    def graceful_stop(self, conn, server) -> None:
        name = minecraft.container_name(server["id"])
        st = self.ops.state(name)
        if not st["running"]:
            return
        self.clear_stale_pause(server["id"], st)
        if st.get("health") == "starting" and not self.is_paused(server["id"]):
            # Server startet gerade erst: In den ersten Sekunden geht „stop“ verloren (Startskripte laufen noch) –
            # Docker würde nach 60 s hart beenden, mitten im Laden der Welt. Darum warten, bis er bereit ist
            # (antwortet auf RCON), höchstens ca. 2 Minuten.
            try:
                self.server_rcon(conn, server, "list", attempts=45)
            except rcon.RconError:
                log.warning("Server %s wurde beim Starten nicht bereit – wird trotzdem gestoppt", server["id"])
        if self.is_paused(server["id"]):
            # Eingefroren: erst aufwecken (der RCON-Versuch weckt ihn), sonst kann er beim Stoppen nicht speichern.
            # Nur kurz versuchen – hängt der Server, stoppt Docker ihn trotzdem.
            try:
                self.server_rcon(conn, server, "save-all", attempts=3)
            except rcon.RconError as exc:
                log.warning("Aufwecken von Server %s fehlgeschlagen: %s", server["id"], exc)
        # Docker schickt „stop“ an Minecraft – das speichert die Welt sauber. Ein zusätzliches save-all über RCON
        # ist nicht nötig und hat bei einem überlasteten Server den Neustart um Minuten verzögert.
        self.ops.stop(name, timeout=60)

    # ---------- Auftrag ausführen ----------

    def run(self, job: sqlite3.Row) -> None:
        conn = self.conn()
        try:
            handler = getattr(self, "job_" + job["kind"], None)
            if handler is None:
                raise RuntimeError(f"Unbekannter Auftrag {job['kind']}")
            payload = json.loads(job["payload"] or "{}")
            result = handler(conn, job, payload)
            conn.execute("UPDATE jobs SET status = 'done', result = ?, done_at = datetime('now') WHERE id = ?",
                         (result, job["id"]))
        except Exception as exc:  # Fehler wird beim Auftrag gespeichert und angezeigt
            log.exception("Auftrag %s (%s) fehlgeschlagen", job["id"], job["kind"])
            conn.execute("UPDATE jobs SET status = 'error', error = ?, done_at = datetime('now') WHERE id = ?",
                         (str(exc)[:500], job["id"]))
        finally:
            if job["server_id"]:
                try:
                    from .tasks import update_status
                    update_status(self, conn, job["server_id"])
                except Exception:
                    log.exception("Status-Aktualisierung fehlgeschlagen")
            conn.close()

    # ---------- die einzelnen Aufträge ----------

    def job_create(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if server["state"] == "active" and not self.ops.state(minecraft.container_name(server["id"]))["exists"]:
            # Auftrag wurde unterbrochen (z. B. Update während des ersten Starts) → einfach fertig machen
            self.recreate(conn, server)
            return "erstellt"
        if server["state"] != "creating":
            return "übersprungen"
        self.clear_leftovers(server["id"], keep_icon=bool(server["icon_path"]))
        # zuerst aktiv setzen: schlägt der Start fehl, kann der User ihn mit „Starten“ erneut versuchen
        conn.execute("UPDATE servers SET state = 'active' WHERE id = ? AND state = 'creating'", (server["id"],))
        self.recreate(conn, server)
        return "erstellt"

    def job_start(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if server["state"] != "active":
            return "übersprungen"
        self.recreate(conn, server)
        return "gestartet"

    def job_stop(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        self.graceful_stop(conn, server)
        return "gestoppt"

    def job_restart(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if server["state"] != "active":
            return "übersprungen"
        if payload.get("warn") and self.awake(server):
            try:
                self.server_rcon(conn, server, "say Der Server startet in 1 Minute neu.")
                time.sleep(60)
            except rcon.RconError:
                pass
        self.graceful_stop(conn, server)
        self.recreate(conn, server)
        return "neu gestartet"

    def job_reload(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        return self.server_rcon(conn, server, minecraft.reload_command(server["type"]))

    def job_command(self, conn, job, payload):
        """Befehl aus der Konsole (gesperrte Befehle werden hier ein zweites Mal geprüft)."""
        server = self.load(conn, job["server_id"])
        cmd = console.clean(payload.get("command", ""))
        if console.is_blocked(cmd):
            raise RuntimeError("Dieser Befehl ist gesperrt – bitte die Knöpfe benutzen.")
        if not self.ops.state(minecraft.container_name(server["id"]))["running"]:
            raise RuntimeError("Der Server ist offline.")
        out = re.sub(r"§[0-9a-fk-orx]", "", self.server_rcon(conn, server, cmd) or "", flags=re.I).strip()
        return out[:4000] or "(keine Ausgabe – der Befehl wurde ausgeführt)"

    def job_rcon(self, conn, job, payload):
        """Von Hostly selbst erzeugte Befehle (Whitelist, OP). Nur wenn der Server läuft."""
        server = self.load(conn, job["server_id"])
        if server["state"] != "active" or not self.ops.state(minecraft.container_name(server["id"]))["running"]:
            # Hinzufügen übernimmt itzg beim Start (OPS/WHITELIST), Entfernen aber nicht (ops.json wird nur
            # ergänzt) – sonst bliebe z. B. der alte Besitzer nach einer Übertragung OP. Darum direkt in der Datei.
            for cmd in payload.get("commands", []):
                parts = cmd.split()
                if len(parts) == 2 and parts[0] == "deop":
                    files.remove_from_userlist(server["id"], "ops.json", parts[1])
                elif len(parts) == 3 and parts[:2] == ["whitelist", "remove"]:
                    files.remove_from_userlist(server["id"], "whitelist.json", parts[2])
            return "Server offline – wird beim nächsten Start übernommen"
        out = [self.server_rcon(conn, server, cmd) for cmd in payload.get("commands", [])]
        return "\n".join(o for o in out if o)

    def job_archive(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if server["state"] != "archiving":
            return "übersprungen"
        self.archive(conn, server)
        return "archiviert"

    def archive(self, conn, server) -> None:
        self.graceful_stop(conn, server)
        self.ops.remove(minecraft.container_name(server["id"]))
        src, dst = minecraft.data_dir(server["id"]), minecraft.archive_dir(server["id"])
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            src.rename(dst)  # gleiche Festplatte: sofort fertig, keine CPU-Last
        servers.mark_archived(conn, server["id"])

    def job_reactivate(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if server["state"] == "active" and not self.ops.state(minecraft.container_name(server["id"]))["exists"]:
            self.recreate(conn, server)   # Auftrag wurde unterbrochen → fertig machen
            return "reaktiviert"
        if server["state"] != "reactivating":
            return "übersprungen"
        src, dst = minecraft.archive_dir(server["id"]), minecraft.data_dir(server["id"])
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        conn.execute("UPDATE servers SET state = 'active' WHERE id = ?", (server["id"],))
        self.recreate(conn, server)
        return "reaktiviert"

    def job_delete(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        self.ops.remove(minecraft.container_name(server["id"]))
        for path in (minecraft.data_dir(server["id"]), minecraft.archive_dir(server["id"])):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        minecraft.icon_file(server["id"]).unlink(missing_ok=True)
        shutil.rmtree(minecraft.backup_dir(server["id"]), ignore_errors=True)
        conn.execute("DELETE FROM backups WHERE server_id = ?", (server["id"],))
        shutil.rmtree(config.UPLOADS_DIR / "admin-files" / str(server["id"]), ignore_errors=True)
        conn.execute("DELETE FROM server_status WHERE server_id = ?", (server["id"],))
        return "gelöscht"

    def job_download(self, conn, job, payload):
        """ZIP erstellen – mit niedrigster Priorität, damit der PC leise bleibt."""
        server = self.load(conn, job["server_id"])
        part = "world" if payload.get("part") == "world" else "all"
        src = minecraft.data_dir(server["id"])
        if not src.exists():
            src = minecraft.archive_dir(server["id"])
        if not src.exists():
            raise RuntimeError("Keine Server-Dateien gefunden.")
        files.check_disk_space()
        config.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"server-{server['id']}-{job['id']}-{part}.zip"
        dest = config.DOWNLOADS_DIR / filename

        running = (server["state"] == "active"
                   and self.ops.state(minecraft.container_name(server["id"]))["running"]
                   and not self.is_paused(server["id"]))
        if running:
            # Welt speichern und während des Kopierens nicht weiter schreiben
            self.server_rcon(conn, server, "save-off")
            self.server_rcon(conn, server, "save-all flush")
        try:
            cmd = [sys.executable, "-m", "hostly.worker.zipper", str(src), str(dest), part]
            if shutil.which("ionice"):
                cmd = ["ionice", "-c3"] + cmd
            subprocess.run(cmd, check=True, preexec_fn=lambda: os.nice(19), timeout=6 * 3600)
        finally:
            if running:
                try:
                    self.server_rcon(conn, server, "save-on")
                except rcon.RconError:
                    log.warning("save-on fehlgeschlagen für Server %s", server["id"])
        os.chmod(dest, 0o644)
        return filename


    # ---------- Stufe 6–8b ----------

    def job_ext_sync(self, conn, job, payload):
        """Plugin-/Mod-Dateien an die Liste anpassen. Gilt nach dem nächsten Neustart."""
        server = self.load(conn, job["server_id"])
        if server["state"] not in ("active", "creating"):
            return "übersprungen"
        result = files.sync_extensions(conn, server)
        files.fix_owner(minecraft.data_dir(server["id"]))
        return result

    def job_backup(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if server["state"] != "active":
            return "übersprungen"
        return f"Backup {self.backup(conn, server, payload.get('kind', 'vor-aenderung'))}"

    def job_restore(self, conn, job, payload):
        """Backup wiederherstellen: stoppen → aktuellen Stand sichern → zurückkopieren → starten."""
        server = self.load(conn, job["server_id"])
        row = conn.execute("SELECT * FROM backups WHERE id = ? AND server_id = ? AND status = 'fertig'",
                           (payload.get("backup_id"), server["id"])).fetchone()
        if row is None or server["state"] != "active":
            raise RuntimeError("Backup nicht gefunden.")
        self.graceful_stop(conn, server)
        self.backup(conn, server, "vor-wiederherstellung")
        files.restore_backup(minecraft.backup_dir(server["id"]) / row["folder"], minecraft.data_dir(server["id"]))
        self.recreate(conn, server)
        return "wiederhergestellt"

    def job_rebuild(self, conn, job, payload):
        """Nach Versions-/Typwechsel: Backup → Dateien anpassen → neu starten."""
        server = self.load(conn, job["server_id"])
        if server["state"] != "active":
            return "übersprungen"
        self.graceful_stop(conn, server)
        self.backup(conn, server, "vor-aenderung")
        if payload.get("from_type") == "PAPER" and server["type"] != "PAPER":
            files.paper_worlds_to_vanilla(minecraft.data_dir(server["id"]), server["level_name"] or "world")
        self.recreate(conn, server)
        return "umgebaut"

    def job_gamerules(self, conn, job, payload):
        """Gamerules: Datapack schreiben (gilt bei jedem Start) und – wenn der Server läuft – sofort setzen."""
        server = self.load(conn, job["server_id"])
        if server["state"] != "active":
            return "übersprungen"
        files.write_rules_datapack(server)
        if not self.ops.state(minecraft.container_name(server["id"]))["running"]:
            return "wird beim nächsten Start übernommen"
        ok = 0
        for cmd in gamesettings.commands_for(server):
            try:
                out = self.server_rcon(conn, server, cmd)
                if "Incorrect" not in out and "Unknown" not in out:
                    ok += 1
            except rcon.RconError:
                pass
        return f"{ok} Regeln gesetzt"

    def job_world_reset(self, conn, job, payload):
        """Neue Welt: stoppen → Sicherung → alte Welt (inkl. Nether/End) löschen → neu starten."""
        server = self.load(conn, job["server_id"])
        if server["state"] != "active":
            return "übersprungen"
        self.graceful_stop(conn, server)
        self.backup(conn, server, "vor-aenderung")
        level = server["level_name"] or "world"
        data = minecraft.data_dir(server["id"])
        names = [level, f"{level}_nether", f"{level}_the_end"]
        bentobox = data / "plugins" / "BentoBox"
        if bentobox.is_dir():
            # SkyBlock/OneBlock: Insel-Welten (bei älteren Versionen eigene Ordner) + Insel-Datenbank mit löschen,
            # sonst glaubt BentoBox, die alten Inseln gäbe es noch
            names += [p.name for p in data.iterdir() if p.is_dir() and p.name != level
                      and p.name.endswith(("_world", "_world_nether", "_world_the_end"))]
            names += ["plugins/BentoBox/database"]
        for name in names:
            target = safe_path(server["id"], name)
            if target != data:
                shutil.rmtree(target, ignore_errors=True)
        seed = (payload.get("seed") or "").strip()[:64] or None
        conn.execute("UPDATE servers SET world_seed = ? WHERE id = ?", (seed, server["id"]))
        self.recreate(conn, server)
        return "neue Welt erstellt"

    def job_world_upload(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        zip_path = config.UPLOADS_DIR / "worlds" / payload["file"]
        try:
            files.check_disk_space()
        except RuntimeError:
            zip_path.unlink(missing_ok=True)
            raise
        level = server["level_name"] or "world"
        # Die gerade benutzte Welt ersetzen geht nur bei gestopptem Server – sonst schreibt Minecraft die alte
        # Welt aus dem Speicher wieder darüber (kaputte Welt). Vorher sichern, danach wieder starten.
        active = payload["name"] in (level, f"{level}_nether", f"{level}_the_end")
        was_running = active and server["state"] == "active" and \
            self.ops.state(minecraft.container_name(server["id"]))["running"]
        try:
            if active:
                self.graceful_stop(conn, server)
                if server["state"] == "active":
                    self.backup(conn, server, "vor-aenderung")
            files.extract_world(zip_path, minecraft.data_dir(server["id"]) / payload["name"])
            files.fix_owner(minecraft.data_dir(server["id"]))
        finally:
            zip_path.unlink(missing_ok=True)
            if was_running:   # auch wenn die ZIP kaputt war: Server wieder starten
                self.recreate(conn, server)
        return "Welt hochgeladen"

    def job_world_delete(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        if payload["name"] in (server["level_name"] or "world", f"{server['level_name'] or 'world'}_nether",
                               f"{server['level_name'] or 'world'}_the_end"):
            raise RuntimeError("Die aktive Welt kann nicht gelöscht werden.")
        target = safe_path(server["id"], payload["name"])
        shutil.rmtree(target, ignore_errors=True)
        return "Welt gelöscht"

    def job_file_write(self, conn, job, payload):
        target = safe_path(job["server_id"], payload["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload["content"], encoding="utf-8")
        files.fix_owner(minecraft.data_dir(job["server_id"]))
        return "gespeichert"

    def job_file_delete(self, conn, job, payload):
        target = safe_path(job["server_id"], payload["path"])
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        return "gelöscht"

    def job_file_put(self, conn, job, payload):
        """Admin-Upload: Datei aus uploads/ an die gewünschte Stelle im Server-Ordner legen."""
        src = config.UPLOADS_DIR / "admin-files" / str(job["server_id"]) / "tmp" / payload["file"]
        target = safe_path(job["server_id"], payload["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), target)
        files.fix_owner(minecraft.data_dir(job["server_id"]))
        return "hochgeladen"


def _backup_delete(w, conn, job, payload):
    b = conn.execute("SELECT * FROM backups WHERE id = ?", (payload.get("backup_id"),)).fetchone()
    if b:
        shutil.rmtree(minecraft.backup_dir(b["server_id"]) / b["folder"], ignore_errors=True)
        conn.execute("DELETE FROM backups WHERE id = ?", (b["id"],))
    return "gelöscht"


Worker.job_backup_delete = _backup_delete


def safe_path(server_id: int, rel: str):
    """Pfad innerhalb des Server-Ordners (Schutz gegen ../-Tricks)."""
    from ..filemanager import resolve
    target = resolve(server_id, rel)
    if target is None:
        raise RuntimeError("Ungültiger Pfad.")
    return target


def _chown_tree_top(path) -> None:
    """Ordner gehört dem normalen Benutzer (1000), wie im Minecraft-Container."""
    if os.geteuid() == 0:
        try:
            os.chown(path, 1000, 1000)
        except OSError:
            pass


def claim_jobs(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    """Wartende Aufträge holen – pro Server immer nur einer gleichzeitig."""
    claimed = []
    with db.transaction(conn):
        # ZIP-Downloads (können lange dauern) laufen nebenher – sonst würden Start/Stopp/Neustart
        # bis zum Ende des Packens warten. Sie blockieren nichts und werden von nichts blockiert.
        rows = conn.execute(
            """SELECT * FROM jobs j WHERE status = 'pending'
               AND (server_id IS NULL OR kind = 'download' OR NOT EXISTS (
                    SELECT 1 FROM jobs r WHERE r.status = 'running' AND r.server_id = j.server_id
                    AND r.kind != 'download'))
               ORDER BY id LIMIT 20"""
        ).fetchall()
        seen = set()
        # höchstens ein ZIP gleichzeitig (leise, und die anderen Aufträge behalten freie Plätze)
        zip_busy = conn.execute("SELECT 1 FROM jobs WHERE status = 'running' AND kind = 'download'").fetchone() is not None
        for row in rows:
            if len(claimed) >= limit:
                break
            if row["kind"] == "download":
                if zip_busy:
                    continue
                zip_busy = True
            if row["server_id"] is not None and row["kind"] != "download":
                if row["server_id"] in seen:
                    continue
                seen.add(row["server_id"])
            conn.execute("UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?", (now_sql(), row["id"]))
            claimed.append(row)
    return claimed
