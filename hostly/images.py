"""Hochgeladene Bilder prüfen und NEU speichern (entfernt versteckte Inhalte)."""
import io

from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000


class ImageError(Exception):
    pass


def square_png(data: bytes, size: int) -> bytes:
    """Bild auf ein Quadrat (Mitte) zuschneiden, auf size×size verkleinern, als PNG zurückgeben."""
    if not data:
        raise ImageError("Kein Bild ausgewählt.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageError("Das Bild ist zu groß (höchstens 5 MB).")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageError("Das ist kein gültiges Bild.")
    img = img.convert("RGBA")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
    img = img.resize((size, size), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
