"""Docker steuern. Nur der worker hat Docker-Zugriff."""
import logging

from .. import config

log = logging.getLogger("hostly.worker")


def _timestamp(text: str | None) -> float | None:
    """Docker-Zeit (z. B. 2026-11-24T00:03:04.123456789Z) → Sekunden seit 1970."""
    from datetime import datetime
    if not text or text.startswith("0001"):
        return None
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


class DockerOps:
    def __init__(self):
        import docker  # erst hier, damit die Website docker nicht braucht

        self.docker = docker
        self.client = docker.from_env()

    # ---------- Grundlagen ----------

    def ensure_network(self) -> None:
        try:
            self.client.networks.get(config.MC_NETWORK)
        except self.docker.errors.NotFound:
            ipam = self.docker.types.IPAMConfig(
                pool_configs=[self.docker.types.IPAMPool(subnet=config.MC_NETWORK_PREFIX + "0/24")]
            )
            self.client.networks.create(config.MC_NETWORK, driver="bridge", ipam=ipam)

    def ensure_image(self, image: str) -> None:
        try:
            self.client.images.get(image)
        except self.docker.errors.ImageNotFound:
            log.info("Lade Image %s herunter …", image)
            repo, _, tag = image.partition(":")
            self.client.images.pull(repo, tag=tag or "latest")

    # ---------- Container ----------

    def state(self, name: str) -> dict:
        try:
            c = self.client.containers.get(name)
        except self.docker.errors.NotFound:
            return {"exists": False, "running": False, "health": None, "restart_count": 0, "started_at": None}
        s = c.attrs.get("State", {})
        return {
            "exists": True,
            "running": bool(s.get("Running")),
            "health": (s.get("Health") or {}).get("Status"),
            "restart_count": int(c.attrs.get("RestartCount") or 0),
            "started_at": _timestamp(s.get("StartedAt")),
        }

    def stats(self, name: str) -> dict | None:
        """CPU (% eines Kerns, 100 = 1 Kern) und RAM (MB, ohne Datei-Cache). Nur für wache Server aufrufen."""
        try:
            st = self.client.containers.get(name).stats(stream=False)
        except self.docker.errors.NotFound:
            return None
        cpu, pre = st.get("cpu_stats", {}), st.get("precpu_stats", {})
        delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - pre.get("cpu_usage", {}).get("total_usage", 0)
        sys_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
        cores = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
        cpu_percent = (delta / sys_delta) * cores * 100 if sys_delta > 0 and delta >= 0 else 0.0
        mem = st.get("memory_stats", {})
        cache = (mem.get("stats") or {}).get("inactive_file", 0)
        mem_mb = max(0, (mem.get("usage", 0) - cache)) // (1024 * 1024)
        return {"cpu_percent": round(cpu_percent, 1), "mem_mb": int(mem_mb)}

    def logs_tail(self, name: str, lines: int = 30) -> str:
        try:
            return self.client.containers.get(name).logs(tail=lines).decode("utf-8", errors="replace")
        except self.docker.errors.NotFound:
            return ""

    def recreate(self, spec: dict) -> None:
        """Container mit den aktuellen Einstellungen neu anlegen und starten (Daten bleiben im Ordner)."""
        self.ensure_network()
        self.ensure_image(spec["image"])
        self.remove(spec["name"])
        api = self.client.api
        host_config = api.create_host_config(
            binds={spec["host_data_dir"]: {"bind": "/data", "mode": "rw"}},
            mem_limit=spec["mem_limit"],
            memswap_limit=spec["mem_limit"],
            nano_cpus=spec["nano_cpus"],
            cpu_shares=512,  # Windows-Programme haben Vorrang
            restart_policy={"Name": "unless-stopped"},
            network_mode=config.MC_NETWORK,
            cap_add=["CAP_NET_RAW"],  # für das Aufwecken beim Einfrieren (knockd)
            log_config={"Type": "json-file", "Config": {"max-size": "5m", "max-file": "2"}},
        )
        networking = api.create_networking_config({
            config.MC_NETWORK: api.create_endpoint_config(ipv4_address=spec["ip"]),
        })
        api.create_container(
            image=spec["image"], name=spec["name"], environment=spec["env"], labels=spec["labels"],
            host_config=host_config, networking_config=networking, stop_timeout=60,
        )
        api.start(spec["name"])

    def stop(self, name: str, timeout: int = 60) -> None:
        try:
            self.client.containers.get(name).stop(timeout=timeout)
        except self.docker.errors.NotFound:
            pass

    def remove(self, name: str) -> None:
        try:
            c = self.client.containers.get(name)
        except self.docker.errors.NotFound:
            return
        if c.status == "running":
            c.stop(timeout=60)
        c.remove(force=True)
