"""Modrinth-API (nur Modrinth, kein CurseForge). Ergebnisse werden 10 Minuten zwischengespeichert."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.modrinth.com/v2/"
USER_AGENT = "hostly/1.0 (selbst gehostete Minecraft-Plattform)"
CACHE_SECONDS = 600

# Server-Typ → (Art, Loader auf Modrinth)
KINDS = {
    "PAPER": ("plugin", ["paper", "spigot", "bukkit"]),
    "FABRIC": ("mod", ["fabric"]),
}
DATAPACK_LOADERS = ["datapack"]

_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


class ModrinthError(Exception):
    pass


def _get(path: str, **params):
    query = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
                                    for k, v in params.items() if v is not None})
    url = API + path + ("?" + query if query else "")
    with _lock:
        hit = _cache.get(url)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code == 429:
            raise ModrinthError("Modrinth ist gerade ausgelastet – bitte später erneut versuchen.")
        raise ModrinthError(f"Modrinth antwortet nicht ({exc.code}).")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ModrinthError("Modrinth ist gerade nicht erreichbar – bitte später erneut versuchen.")
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[url] = (time.time(), data)
    return data


def loaders_for(kind: str, server_type: str) -> list[str]:
    if kind == "datapack":
        return DATAPACK_LOADERS
    return KINDS[server_type][1]


def kinds_for(server_type: str) -> list[str]:
    """Was passt zu welchem Server-Typ (KONZEPT.md 15.2)."""
    if server_type in KINDS:
        return [KINDS[server_type][0], "datapack"]
    return ["datapack"]


def search(query: str, kind: str, server_type: str, mc_version: str, limit: int = 20) -> list[dict]:
    if kind == "datapack":
        facets = [["project_type:datapack"], [f"versions:{mc_version}"]]
    elif kind == "resourcepack":
        facets = [["project_type:resourcepack"], [f"versions:{mc_version}"]]
    else:
        facets = [[f"project_type:{kind}"], [f"categories:{l}" for l in loaders_for(kind, server_type)],
                  [f"versions:{mc_version}"]]
    data = _get("search", query=query.strip()[:100], facets=facets, limit=limit,
                index="relevance" if query.strip() else "downloads")
    return (data or {}).get("hits", [])


def project(id_or_slug: str) -> dict | None:
    return _get(f"project/{urllib.parse.quote(id_or_slug)}")


def versions(id_or_slug: str, loaders: list[str], mc_version: str) -> list[dict]:
    return _get(f"project/{urllib.parse.quote(id_or_slug)}/version", loaders=loaders,
                game_versions=[mc_version]) or []


def version(version_id: str) -> dict | None:
    return _get(f"version/{urllib.parse.quote(version_id)}")


def best_version(id_or_slug: str, loaders: list[str], mc_version: str) -> dict | None:
    """Neueste passende Version – stabile Versionen bevorzugt."""
    vs = versions(id_or_slug, loaders, mc_version)
    for v in vs:
        if v.get("version_type") == "release":
            return v
    return vs[0] if vs else None


def primary_file(v: dict) -> dict:
    files = v.get("files") or []
    for f in files:
        if f.get("primary"):
            return f
    if not files:
        raise ModrinthError("Diese Version hat keine Datei.")
    return files[0]


def mojang_releases(limit: int = 30) -> list[str]:
    """Liste der Minecraft-Versionen (neueste zuerst)."""
    url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    with _lock:
        hit = _cache.get(url)
        if hit and time.time() - hit[0] < 3600:
            return hit[1]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ModrinthError("Die Minecraft-Versionsliste ist gerade nicht erreichbar.")
    result = [v["id"] for v in data["versions"] if v["type"] == "release"][:limit]
    with _lock:
        _cache[url] = (time.time(), result)
    return result


def fabric_loader_version() -> str:
    url = "https://meta.fabricmc.net/v2/versions/loader"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            for v in json.load(resp):
                if v.get("stable"):
                    return v["version"]
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    return "0.16.10"
