"""ZIP erstellen (läuft als eigener Prozess mit niedrigster Priorität).

python -m hostly.worker.zipper QUELLE ZIEL world|all
"""
import sys
import zipfile
from pathlib import Path

SKIP = {".paused", ".skip-pause", ".rcon-cli.env", ".rcon-cli.yaml"}


def level_name(src: Path) -> str:
    props = src / "server.properties"
    if props.exists():
        for line in props.read_text(errors="replace").splitlines():
            if line.startswith("level-name="):
                return line.split("=", 1)[1].strip() or "world"
    return "world"


def main(src: str, dest: str, part: str) -> None:
    src_path, dest_path = Path(src), Path(dest)
    tmp = dest_path.with_suffix(".tmp")
    if part == "world":
        name = level_name(src_path)
        roots = [p for p in src_path.iterdir() if p.is_dir() and p.name in (name, f"{name}_nether", f"{name}_the_end")]
    else:
        roots = [src_path]
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for root in roots:
            files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
            for f in files:
                if f.name in SKIP or f.is_symlink():
                    continue
                zf.write(f, f.relative_to(src_path).as_posix())
    tmp.rename(dest_path)


if __name__ == "__main__":
    main(*sys.argv[1:4])
