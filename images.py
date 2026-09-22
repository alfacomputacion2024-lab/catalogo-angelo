"""Descarga y optimiza imágenes (JPG, máx. MAX_IMAGE_SIDE px)."""
import hashlib
import io
import re
import time

import requests
from PIL import Image

import config


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def download_images(brand_key: str, reference: str, urls, referer=None):
    """Devuelve rutas relativas a data/imagenes, p. ej. ['casio/GA-2100-1A_1.jpg']."""
    folder = config.IMAGES_DIR / brand_key
    folder.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", reference)
    headers = {"User-Agent": config.USER_AGENT}
    if referer:
        headers["Referer"] = referer

    saved, seen = [], set()
    for url in urls:
        if len(saved) >= config.MAX_IMAGES:
            break
        try:
            r = requests.get(url, headers=headers, timeout=config.TIMEOUT)
            if r.status_code != 200:
                continue
            digest = hashlib.md5(r.content).hexdigest()
            if digest in seen:
                continue
            img = Image.open(io.BytesIO(r.content))
            img.load()
        except Exception:
            continue
        if min(img.size) < config.MIN_IMAGE_SIDE:
            continue
        img = _to_rgb(img)
        img.thumbnail((config.MAX_IMAGE_SIDE, config.MAX_IMAGE_SIDE))
        name = f"{slug}_{len(saved) + 1}.jpg"
        img.save(folder / name, "JPEG", quality=config.JPEG_QUALITY, optimize=True)
        seen.add(digest)
        saved.append(f"{brand_key}/{name}")
        time.sleep(0.3)
    return saved


def save_image(file_storage, brand_key: str, reference: str, index: int) -> str | None:
    """Guarda una imagen subida desde un formulario HTML. Devuelve ruta relativa o None."""
    import re as _re
    folder = config.IMAGES_DIR / brand_key
    folder.mkdir(parents=True, exist_ok=True)
    slug = _re.sub(r"[^A-Za-z0-9._-]+", "_", reference)
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except Exception:
        return None
    if min(img.size) < config.MIN_IMAGE_SIDE:
        return None
    img = _to_rgb(img)
    img.thumbnail((config.MAX_IMAGE_SIDE, config.MAX_IMAGE_SIDE))
    name = f"{slug}_{index + 1}.jpg"
    img.save(folder / name, "JPEG", quality=config.JPEG_QUALITY, optimize=True)
    return f"{brand_key}/{name}"
