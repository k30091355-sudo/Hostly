"""hostly-worker: führt Aufträge aus und erledigt zeitgesteuerte Aufgaben.

Start: python -m hostly.worker
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.blocking import BlockingScheduler

from .. import config, db
from . import tasks
from .docker_ops import DockerOps
from .jobs import Worker, claim_jobs

log = logging.getLogger("hostly.worker")
MAX_PARALLEL = 3


def fix_db_owner() -> None:
    """Die Datenbank soll dem normalen Benutzer (1000) gehören, damit die Website schreiben kann."""
    if os.geteuid() != 0:
        return
    for path in [config.DB_PATH.parent, config.DB_PATH]:
        try:
            if path.exists() and path.stat().st_uid == 0:
                os.chown(path, 1000, 1000)
        except OSError:
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # nicht alle 2 Sekunden ins Protokoll schreiben (leise, schont die SSD)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    db.init_db()
    fix_db_owner()
    for d in (config.SERVERS_DIR, config.ARCHIVES_DIR, config.DOWNLOADS_DIR, config.UPLOADS_DIR / "icons",
              config.DATA_DIR / "backups"):
        d.mkdir(parents=True, exist_ok=True)

    w = Worker(DockerOps())
    w.ops.ensure_network()

    # Aufträge, die beim letzten Beenden mitten drin waren, nochmal ausführen
    conn = db.connect()
    conn.execute("UPDATE jobs SET status = 'pending' WHERE status = 'running'")
    conn.close()

    pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
    running: set = set()

    def poll_jobs():
        running.difference_update({f for f in running if f.done()})
        free = MAX_PARALLEL - len(running)
        if free <= 0:
            return
        c = db.connect()
        try:
            for job in claim_jobs(c, free):
                running.add(pool.submit(w.run, job))
        finally:
            c.close()

    sched = BlockingScheduler(timezone=config.TIMEZONE)
    sched.add_job(poll_jobs, "interval", seconds=2, max_instances=1, coalesce=True)
    sched.add_job(tasks.status_all, "interval", seconds=60, args=[w], max_instances=1, coalesce=True)
    sched.add_job(tasks.check_expiry, "interval", seconds=60, args=[w], max_instances=1, coalesce=True)
    sched.add_job(tasks.cleanup_downloads, "interval", hours=1, max_instances=1, coalesce=True)
    sched.add_job(tasks.cleanup_db, "cron", hour=4, minute=17, args=[w])
    for func in (tasks.night_pauses, tasks.draw_giveaways, tasks.end_ram_promotions, tasks.notify_waitlist):
        sched.add_job(func, "interval", seconds=60, args=[w], max_instances=1, coalesce=True)
    sched.add_job(tasks.nightly_backups, "interval", minutes=10, args=[w], max_instances=1, coalesce=True)
    sched.add_job(tasks.cleanup_backups, "cron", hour=6, minute=30, args=[w])
    sched.add_job(tasks.backup_database, "cron", hour=2, minute=3)
    sched.add_job(tasks.disk_usage, "cron", hour=5, minute=41, args=[w])
    log.info("hostly-worker läuft")
    # beim Start sofort einmal prüfen (holt Verpasstes nach, z. B. nach Stromausfall)
    tasks.check_expiry(w)
    tasks.status_all(w)
    sched.start()


if __name__ == "__main__":
    main()
