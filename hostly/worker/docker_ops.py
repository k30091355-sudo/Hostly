"""Docker steuern. Nur der worker hat Docker-Zugriff."""
import logging

from .. import config

log = logging.getLogger("hostly.worker")


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
            return {"exists": False, "running": False, "health": None}
        s = c.attrs.get("State", {})
        return {
            "exists": True,
            "running": bool(s.get("Running")),
            "health": (s.get("Health") or {}).get("Status"),
        }

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
