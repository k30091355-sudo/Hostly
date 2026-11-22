import json
from datetime import timedelta

from hostly import coins, db
from hostly.timeutil import fmt, now

from .conftest import conn, csrf_of, register


class FakeOps:
    """Ersetzt Docker in Tests."""

    def __init__(self):
        self.containers = {}
        self.calls = []

    def ensure_network(self):
        pass

    def state(self, name):
        c = self.containers.get(name)
        if not c:
            return {"exists": False, "running": False, "health": None}
        return {"exists": True, "running": c["running"], "health": "healthy" if c["running"] else None}

    def recreate(self, spec):
        self.calls.append(("recreate", spec["name"]))
        self.containers[spec["name"]] = {"running": True, "spec": spec}

    def stop(self, name, timeout=60):
        self.calls.append(("stop", name))
        if name in self.containers:
            self.containers[name]["running"] = False

    def remove(self, name):
        self.calls.append(("remove", name))
        self.containers.pop(name, None)


class FakeRcon:
    def __init__(self):
        self.commands = []

    def __call__(self, host, port, password, cmd, attempts=8):
        self.commands.append(cmd)
        if cmd == "list":
            return "There are 1 of a max of 7 players online: Steve"
        return f"ok: {cmd}"


def setup_shop(client, coins_amount=5000, tunnels=2):
    """Admin (erster User) mit Coins und Tunneln."""
    register(client, "admin")
    c = conn()
    with db.transaction(c):
        coins.book(c, 1, coins_amount, "admin")
        for i in range(tunnels):
            c.execute("INSERT INTO tunnels (name, public_address, internal_ip) VALUES (?, ?, ?)",
                      (f"T{i}", f"t{i}.joinmc.link", f"172.30.0.{11 + i}"))
    return c


def buy(client, model_id=2, days=7, name="Survival", server_type="PAPER", request_id="r1"):
    token = csrf_of(client, "/kaufen")
    return client.post("/kaufen", data={"model_id": model_id, "server_type": server_type, "days": days,
                                        "name": name, "request_id": request_id, "csrf": token},
                       follow_redirects=False)


def run_jobs(worker):
    from hostly.worker.jobs import claim_jobs
    c = conn()
    while True:
        jobs = claim_jobs(c, 10)
        if not jobs:
            break
        for j in jobs:
            worker.run(j)


def set_until(server_id, delta):
    conn().execute("UPDATE servers SET rented_until = ? WHERE id = ?", (fmt(now() + delta), server_id))


def payload(job):
    return json.loads(job["payload"])


__all__ = ["timedelta"]
