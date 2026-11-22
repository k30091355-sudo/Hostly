"""Kleiner RCON-Client (Minecraft-Konsole über das Netzwerk). Nur der worker benutzt ihn."""
import socket
import struct
import time


class RconError(Exception):
    pass


def _packet(req_id: int, kind: int, body: str) -> bytes:
    data = struct.pack("<ii", req_id, kind) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(data)) + data


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise RconError("Verbindung getrennt")
        buf += chunk
    return buf


def _read(sock: socket.socket) -> tuple[int, int, str]:
    (length,) = struct.unpack("<i", _recv_exact(sock, 4))
    data = _recv_exact(sock, length)
    req_id, kind = struct.unpack("<ii", data[:8])
    return req_id, kind, data[8:-2].decode("utf-8", errors="replace")


def command(host: str, port: int, password: str, cmd: str, timeout: float = 10) -> str:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(_packet(1, 3, password))
        req_id, _, _ = _read(sock)
        if req_id == -1:
            raise RconError("RCON-Passwort falsch")
        sock.sendall(_packet(2, 2, cmd))
        _, _, body = _read(sock)
        return body


def command_retry(host: str, port: int, password: str, cmd: str, attempts: int = 8, wait: float = 2.0) -> str:
    """Mit Wiederholungen – ein eingefrorener Server wacht beim ersten Verbindungsversuch auf."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return command(host, port, password, cmd)
        except (OSError, RconError) as exc:
            last = exc
            time.sleep(wait)
    raise RconError(f"Server antwortet nicht ({last})")
