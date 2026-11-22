"""Aufträge aus der Tabelle `jobs` ausführen (Start, Stopp, Konsole, Archiv …)."""
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys

from .. import config, console, db, minecraft, rcon, servers
from ..timeutil import now_sql

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

    def spec_for(self, conn, server) -> dict:
        model = servers.model(conn, server["model_id"])
        tunnel = conn.execute("SELECT * FROM tunnels WHERE id = ?", (server["tunnel_id"],)).fetchone()
        owner = conn.execute("SELECT minecraft_name FROM users WHERE id = ?", (server["owner_id"],)).fetchone()
        ops = [owner["minecraft_name"]] if owner and owner["minecraft_name"] else []
        wl = [r[0] for r in conn.execute(
            "SELECT minecraft_name FROM whitelist WHERE server_id = ? ORDER BY minecraft_name", (server["id"],))]
        return minecraft.build_spec(server, model, tunnel, ops, wl)

    def prepare_data_dir(self, server_id: int) -> None:
        path = minecraft.data_dir(server_id)
        path.mkdir(parents=True, exist_ok=True)
        icon = minecraft.icon_file(server_id)
        if icon.exists():
            shutil.copyfile(icon, path / "server-icon.png")
        _chown_tree_top(path)

    def recreate(self, conn, server) -> None:
        self.prepare_data_dir(server["id"])
        self.ops.recreate(self.spec_for(conn, server))
        conn.execute("UPDATE servers SET needs_restart = 0 WHERE id = ?", (server["id"],))

    def graceful_stop(self, conn, server) -> None:
        name = minecraft.container_name(server["id"])
        st = self.ops.state(name)
        if not st["running"]:
            return
        try:
            # eingefrorene Server wachen beim RCON-Versuch auf, dann wird sauber gespeichert
            self.server_rcon(conn, server, "save-all", attempts=6)
        except rcon.RconError as exc:
            log.warning("save-all für Server %s fehlgeschlagen: %s", server["id"], exc)
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
        if server["state"] != "creating":
            return "übersprungen"
        self.recreate(conn, server)
        conn.execute("UPDATE servers SET state = 'active' WHERE id = ? AND state = 'creating'", (server["id"],))
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
        return self.server_rcon(conn, server, cmd) or "(keine Ausgabe)"

    def job_rcon(self, conn, job, payload):
        """Von Hostly selbst erzeugte Befehle (Whitelist, OP). Nur wenn der Server läuft."""
        server = self.load(conn, job["server_id"])
        if server["state"] != "active" or not self.ops.state(minecraft.container_name(server["id"]))["running"]:
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
        if server["state"] != "reactivating":
            return "übersprungen"
        src, dst = minecraft.archive_dir(server["id"]), minecraft.data_dir(server["id"])
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        self.recreate(conn, server)
        conn.execute("UPDATE servers SET state = 'active' WHERE id = ?", (server["id"],))
        return "reaktiviert"

    def job_delete(self, conn, job, payload):
        server = self.load(conn, job["server_id"])
        self.ops.remove(minecraft.container_name(server["id"]))
        for path in (minecraft.data_dir(server["id"]), minecraft.archive_dir(server["id"])):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        minecraft.icon_file(server["id"]).unlink(missing_ok=True)
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
        rows = conn.execute(
            """SELECT * FROM jobs j WHERE status = 'pending'
               AND (server_id IS NULL OR NOT EXISTS (
                    SELECT 1 FROM jobs r WHERE r.status = 'running' AND r.server_id = j.server_id))
               ORDER BY id LIMIT 20"""
        ).fetchall()
        seen = set()
        for row in rows:
            if len(claimed) >= limit:
                break
            if row["server_id"] is not None:
                if row["server_id"] in seen:
                    continue
                seen.add(row["server_id"])
            conn.execute("UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?", (now_sql(), row["id"]))
            claimed.append(row)
    return claimed
