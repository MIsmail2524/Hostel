"""Storage abstraction. Local disk for dev; swap for an S3/R2 implementation in production.

Keys are random (uuid-based) and namespaced:
  public/...   served at /media/... (listing photos, panoramas, previews)
  private/...  never served over HTTP (raw 3D capture inputs)
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .config import get_settings


def root() -> Path:
    return get_settings().storage_dir


def new_key(scope: str, prefix: str, ext: str) -> str:
    assert scope in ("public", "private")
    return f"{scope}/{prefix}/{uuid.uuid4().hex}{ext}"


def path_for(key: str) -> Path:
    p = (root() / key).resolve()
    if not str(p).startswith(str(root().resolve())):  # path traversal guard
        raise ValueError("invalid storage key")
    return p


def write_bytes(key: str, data: bytes) -> Path:
    p = path_for(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def write_file(key: str, src: Path) -> Path:
    p = path_for(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), p)
    return p


def delete(key: str | None) -> None:
    if key:
        try:
            path_for(key).unlink(missing_ok=True)
        except ValueError:
            pass


def public_url(key: str | None) -> str | None:
    if not key:
        return None
    assert key.startswith("public/")
    # Relative URL: clients prefix their API origin (works for LAN dev, CDN in prod).
    return f"/media/{key[len('public/'):]}"
