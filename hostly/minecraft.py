"""Einstellungen für den itzg/minecraft-server-Container (TECHNIK.md 5–7). Reine Berechnung, kein Docker."""
import sqlite3

from . import config


def container_name(server_id: int) -> str:
    return f"hostly-mc-{server_id}"


def data_dir(server_id: int):
    return config.SERVERS_DIR / str(server_id)


def archive_dir(server_id: int):
    return config.ARCHIVES_DIR / str(server_id)


def icon_file(server_id: int):
    return config.UPLOADS_DIR / "icons" / f"{server_id}.png"


def backup_dir(server_id: int):
    return config.DATA_DIR / "backups" / str(server_id)


def build_spec(server: sqlite3.Row, model: sqlite3.Row, tunnel: sqlite3.Row,
               ops: list[str], whitelist: list[str]) -> dict:
    from .servers import effective_ram

    ram = effective_ram(server, model)
    env = {
        "EULA": "TRUE",
        "TYPE": server["type"],
        "VERSION": server["mc_version"] or "LATEST",
        "MEMORY": f"{int(ram * 1024)}M",
        "MAX_PLAYERS": str(model["max_players"]),
        "MOTD": server["motd"] or server["name"],
        "ONLINE_MODE": "TRUE",
        # optimierte Java-Einstellungen (schnellerer Start, weniger Ruckler)
        "USE_AIKAR_FLAGS": "TRUE",
        # Einstellungen aus dem Reiter „Einstellungen“ (Sichtweite begrenzt: playit-Tunnel + CPU)
        "VIEW_DISTANCE": str(server["view_distance"] or 8),
        "SIMULATION_DISTANCE": str(min(6, server["view_distance"] or 8)),
        "DIFFICULTY": server["difficulty"] or "easy",
        "MODE": server["gamemode"] or "survival",
        "PVP": "TRUE" if server["pvp"] else "FALSE",
        "ALLOW_FLIGHT": "TRUE" if server["allow_flight"] else "FALSE",
        "SPAWN_PROTECTION": str(server["spawn_protection"]),
        "TZ": config.TIMEZONE,
        # Konsole
        "ENABLE_RCON": "TRUE",
        "RCON_PASSWORD": server["rcon_password"],
        "RCON_PORT": str(config.RCON_PORT),
        # Einfrieren, wenn niemand online ist (leise!)
        "ENABLE_AUTOPAUSE": "TRUE",
        "AUTOPAUSE_TIMEOUT_EST": "300",
        "AUTOPAUSE_TIMEOUT_INIT": "300",
        "AUTOPAUSE_TIMEOUT_KN": "60",
        "MAX_TICK_TIME": "-1",
        # Whitelist: die Liste im Reiter "Spieler" ist maßgeblich
        "OVERRIDE_WHITELIST": "TRUE",
    }
    if server["type"] == "PAPER":
        env["JVM_DD_OPTS"] = "disable.watchdog:true"
    env["LEVEL"] = server["level_name"] or "world"
    if server["world_seed"]:
        env["SEED"] = server["world_seed"]
    if server["world_type"]:
        env["LEVEL_TYPE"] = server["world_type"]
    if server["resource_pack_url"]:
        env["RESOURCE_PACK"] = server["resource_pack_url"]
        env["RESOURCE_PACK_SHA1"] = server["resource_pack_sha1"] or ""
        env["RESOURCE_PACK_ENFORCE"] = "TRUE" if server["resource_pack_enforce"] else "FALSE"
    if ops:
        env["OPS"] = ",".join(ops)
    if server["whitelist_enabled"]:
        env["ENABLE_WHITELIST"] = "TRUE"
        env["ENFORCE_WHITELIST"] = "TRUE"
        if whitelist:
            env["WHITELIST"] = ",".join(whitelist)
    else:
        env["ENABLE_WHITELIST"] = "FALSE"
        env["ENFORCE_WHITELIST"] = "FALSE"
    return {
        "name": container_name(server["id"]),
        "image": config.MC_IMAGE,
        "env": env,
        "mem_limit": int((ram + config.CONTAINER_EXTRA_GB) * 1024 ** 3),
        "nano_cpus": int(model["cpu_limit"] * 1e9),
        "ip": tunnel["internal_ip"],
        "host_data_dir": str(config.HOST_DATA_DIR / "servers" / str(server["id"])),
        "labels": {"hostly.server": str(server["id"])},
    }


def reload_command(server_type: str) -> str:
    return "reload confirm" if server_type == "PAPER" else "reload"
