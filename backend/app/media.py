"""Upload validation & sanitisation.

* Size limits enforced while streaming (never trust Content-Length alone).
* Type detected from magic bytes, not the filename or client MIME type.
* Images are decoded (decompression-bomb guarded), EXIF-orientation applied, then
  RE-ENCODED to JPEG — this strips EXIF/GPS metadata and any embedded payloads.
* Videos are checked by container signature and decodability/duration with OpenCV.
"""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import cv2
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from . import storage
from .config import get_settings

Image.MAX_IMAGE_PIXELS = 60_000_000  # ~60 MP: above any phone camera, blocks decompression bombs
CHUNK = 1024 * 1024


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    buf = io.BytesIO()
    while True:
        chunk = await upload.read(CHUNK)
        if not chunk:
            break
        buf.write(chunk)
        if buf.tell() > max_bytes:
            raise HTTPException(413, f"File too large (max {max_bytes // (1024 * 1024)} MB)")
    return buf.getvalue()


def sniff(head: bytes) -> str | None:
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"msf1", b"heim", b"heis"):
            return "heic"
        return "mp4"  # mp4 / mov / 3gp family
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    return None


def _decode_image(data: bytes) -> Image.Image:
    kind = sniff(data[:16])
    if kind == "heic":
        raise HTTPException(415, "HEIC photos are not supported yet — set your camera to 'Most compatible' (JPEG)")
    if kind not in ("jpeg", "png", "webp"):
        raise HTTPException(415, "Only JPEG, PNG or WebP images are allowed")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise HTTPException(422, "The image is corrupted or too large")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if min(img.size) < 320:
        raise HTTPException(422, "Image is too small (min 320 px)")
    return img.convert("RGB")


def _encode(img: Image.Image, max_side: int, quality: int = 85) -> tuple[bytes, int, int]:
    im = img.copy()
    im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)  # no exif → metadata stripped
    return out.getvalue(), im.width, im.height


async def save_listing_photo(upload: UploadFile, listing_id: str) -> tuple[str, str, int, int]:
    s = get_settings()
    data = await read_limited(upload, s.max_image_mb * 1024 * 1024)
    img = _decode_image(data)
    full, w, h = _encode(img, 1920)
    thumb, _, _ = _encode(img, 480, quality=78)
    key = storage.new_key("public", f"listings/{listing_id}", ".jpg")
    tkey = key.replace(".jpg", "_t.jpg")
    storage.write_bytes(key, full)
    storage.write_bytes(tkey, thumb)
    return key, tkey, w, h


async def save_tour_image(upload: UploadFile, tour_id: str) -> str:
    s = get_settings()
    data = await read_limited(upload, s.max_image_mb * 1024 * 1024)
    img = _decode_image(data)
    full, _, _ = _encode(img, 3000, quality=92)
    key = storage.new_key("private", f"tours/{tour_id}", ".jpg")
    storage.write_bytes(key, full)
    return key


async def save_tour_video(upload: UploadFile, tour_id: str) -> str:
    s = get_settings()
    max_bytes = s.max_upload_mb * 1024 * 1024
    fd, name = tempfile.mkstemp(suffix=".vid", dir=storage.root() if storage.root().exists() else None)
    os.close(fd)
    tmp = Path(name)
    try:
        size = 0
        head = b""
        with tmp.open("wb") as f:
            while True:
                chunk = await upload.read(CHUNK)
                if not chunk:
                    break
                if not head:
                    head = chunk[:16]
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"Video too large (max {s.max_upload_mb} MB)")
                f.write(chunk)
        kind = sniff(head)
        if kind not in ("mp4", "webm"):
            raise HTTPException(415, "Only MP4, MOV or WebM videos are allowed")
        cap = cv2.VideoCapture(str(tmp))
        ok = cap.isOpened() and cap.read()[0]
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        if not ok:
            raise HTTPException(422, "The video could not be decoded")
        if fps > 0 and frames / fps > s.max_video_seconds:
            raise HTTPException(422, f"Video is longer than {s.max_video_seconds} seconds")
        key = storage.new_key("private", f"tours/{tour_id}", ".mp4" if kind == "mp4" else ".webm")
        storage.write_file(key, tmp)
        return key
    finally:
        tmp.unlink(missing_ok=True)
