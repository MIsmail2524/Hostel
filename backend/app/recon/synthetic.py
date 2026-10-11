"""Synthetic textured rooms with known ground truth.

Used by the automated tests (photos/video → panorama accuracy) and by the demo seed so a
fresh install has working 3D tours. Rendering is an exact ray-cast of a box room, so the
"phone photos" it produces are geometrically identical to a real rotation-only capture.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

PX_PER_M = 220


@dataclass
class Room:
    width: float = 3.7  # x
    length: float = 4.3  # z
    height: float = 3.0
    cam_height: float = 1.5
    offset_x: float = 0.15  # camera offset from room centre
    offset_z: float = -0.2
    seed: int = 1
    wall_color: tuple[int, int, int] = (205, 222, 232)  # BGR
    floor_color: tuple[int, int, int] = (150, 170, 190)

    @property
    def bounds(self):
        x0 = -self.width / 2 - self.offset_x
        z0 = -self.length / 2 - self.offset_z
        y0 = -(self.height - self.cam_height)  # ceiling (y down)
        return x0, x0 + self.width, y0, self.cam_height, z0, z0 + self.length


def _noise(h, w, rng, scale=12, amp=10):
    n = rng.normal(0, 1, (max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC) * amp


def _poster(img, rng, x, y, w, h):
    cv2.rectangle(img, (x - 6, y - 6), (x + w + 6, y + h + 6), (40, 50, 60), -1)
    bg = tuple(int(c) for c in rng.integers(60, 230, 3))
    cv2.rectangle(img, (x, y), (x + w, y + h), bg, -1)
    for _ in range(14):
        c = tuple(int(v) for v in rng.integers(0, 255, 3))
        kind = rng.integers(0, 3)
        px, py = int(x + rng.integers(0, w)), int(y + rng.integers(0, h))
        if kind == 0:
            cv2.circle(img, (px, py), int(rng.integers(6, max(8, w // 5))), c, -1)
        elif kind == 1:
            cv2.line(img, (px, py), (int(x + rng.integers(0, w)), int(y + rng.integers(0, h))), c, int(rng.integers(2, 6)))
        else:
            cv2.rectangle(img, (px, py), (min(x + w, px + int(rng.integers(8, 40))), min(y + h, py + int(rng.integers(8, 40)))), c, -1)
    words = ["KAMRA", "HOSTEL", "ROOM 7", "STUDY", "WELCOME", "LAHORE", "QUIET", "WIFI"]
    cv2.putText(img, words[int(rng.integers(0, len(words)))], (x + 8, y + h - 12), cv2.FONT_HERSHEY_SIMPLEX, max(0.5, w / 220), (255, 255, 255), 2, cv2.LINE_AA)


def _wall(room: Room, w_m: float, kind: str, rng) -> np.ndarray:
    W, H = int(w_m * PX_PER_M), int(room.height * PX_PER_M)
    img = np.empty((H, W, 3), np.float32)
    img[:] = room.wall_color
    img += _noise(H, W, rng)[..., None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    floor_y = H - 1  # v=1 is the floor
    cv2.rectangle(img, (0, floor_y - 22), (W, floor_y), (70, 90, 110), -1)  # skirting
    m = PX_PER_M
    if kind == "door":
        x = int(W * 0.15)
        cv2.rectangle(img, (x, floor_y - int(2.1 * m)), (x + int(0.9 * m), floor_y), (45, 75, 120), -1)
        cv2.rectangle(img, (x + 12, floor_y - int(2.0 * m)), (x + int(0.9 * m) - 12, floor_y - int(1.1 * m)), (35, 60, 100), 3)
        cv2.circle(img, (x + int(0.78 * m), floor_y - int(1.0 * m)), 9, (40, 190, 220), -1)
        _poster(img, rng, int(W * 0.55), int(H * 0.25), int(0.9 * m), int(0.6 * m))
    elif kind == "window":
        x0, y0, x1, y1 = int(W * 0.25), int(H * 0.22), int(W * 0.75), int(H * 0.6)
        sky = np.linspace(255, 190, y1 - y0)[:, None, None] * np.array([1.0, 0.85, 0.55])[None, None, :]
        img[y0:y1, x0:x1] = np.clip(sky, 0, 255).astype(np.uint8)
        cv2.circle(img, (int(x0 + (x1 - x0) * 0.7), int(y0 + (y1 - y0) * 0.35)), 30, (60, 140, 60), -1)
        for t in np.linspace(x0, x1, 4).astype(int):
            cv2.line(img, (int(t), y0), (int(t), y1), (240, 240, 240), 8)
        for t in np.linspace(y0, y1, 3).astype(int):
            cv2.line(img, (x0, int(t)), (x1, int(t)), (240, 240, 240), 8)
        cv2.rectangle(img, (x0 - 30, y0 - 20), (x0 + 20, y1 + 60), (90, 60, 160), -1)  # curtains
        cv2.rectangle(img, (x1 - 20, y0 - 20), (x1 + 30, y1 + 60), (90, 60, 160), -1)
        cv2.rectangle(img, (int(W * 0.3), floor_y - int(0.75 * m)), (int(W * 0.7), floor_y - int(0.7 * m)), (60, 80, 100), -1)  # desk
    elif kind == "bed":
        bx0, bx1 = int(W * 0.1), int(W * 0.1 + 2.0 * m)
        cv2.rectangle(img, (bx0, floor_y - int(0.55 * m)), (bx1, floor_y - 25), (110, 80, 60), -1)
        cv2.rectangle(img, (bx0, floor_y - int(0.65 * m)), (bx1, floor_y - int(0.45 * m)), (200, 160, 120), -1)
        cv2.ellipse(img, (bx0 + 70, floor_y - int(0.6 * m)), (55, 22), 0, 0, 360, (245, 245, 245), -1)
        _poster(img, rng, int(W * 0.15), int(H * 0.2), int(0.7 * m), int(0.5 * m))
        _poster(img, rng, int(W * 0.62), int(H * 0.28), int(0.5 * m), int(0.7 * m))
    else:  # cupboard
        cx = int(W * 0.55)
        cv2.rectangle(img, (cx, floor_y - int(2.0 * m)), (cx + int(1.2 * m), floor_y), (60, 100, 150), -1)
        cv2.line(img, (cx + int(0.6 * m), floor_y - int(2.0 * m)), (cx + int(0.6 * m), floor_y), (30, 50, 80), 4)
        for k in (0.5, 0.7):
            cv2.circle(img, (cx + int(k * m), floor_y - int(1.0 * m)), 7, (200, 200, 200), -1)
        _poster(img, rng, int(W * 0.1), int(H * 0.25), int(0.8 * m), int(0.55 * m))
        cv2.circle(img, (int(W * 0.25), int(H * 0.12)), 28, (230, 230, 230), -1)  # clock
        cv2.circle(img, (int(W * 0.25), int(H * 0.12)), 28, (40, 40, 40), 3)
    return img


def _floor(room: Room, rng) -> np.ndarray:
    W, H = int(room.width * PX_PER_M), int(room.length * PX_PER_M)
    img = np.empty((H, W, 3), np.float32)
    tile = int(0.6 * PX_PER_M)
    for ty in range(0, H, tile):
        for tx in range(0, W, tile):
            img[ty : ty + tile, tx : tx + tile] = np.array(room.floor_color) + rng.normal(0, 12, 3)
    img += _noise(H, W, rng, scale=6, amp=8)[..., None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    for t in range(0, W, tile):
        cv2.line(img, (t, 0), (t, H), (90, 100, 110), 3)
    for t in range(0, H, tile):
        cv2.line(img, (0, t), (W, t), (90, 100, 110), 3)
    cv2.rectangle(img, (int(W * 0.3), int(H * 0.35)), (int(W * 0.75), int(H * 0.7)), (60, 40, 140), -1)  # rug
    cv2.rectangle(img, (int(W * 0.32), int(H * 0.37)), (int(W * 0.73), int(H * 0.68)), (80, 160, 200), 6)
    return img


def _ceiling(room: Room, rng) -> np.ndarray:
    W, H = int(room.width * PX_PER_M), int(room.length * PX_PER_M)
    img = np.full((H, W, 3), 238, np.float32) + _noise(H, W, rng, amp=4)[..., None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    c = (W // 2, H // 2)
    cv2.circle(img, c, 40, (120, 120, 120), -1)
    for a in range(0, 360, 120):
        r = np.deg2rad(a)
        cv2.line(img, c, (int(c[0] + 260 * np.cos(r)), int(c[1] + 260 * np.sin(r))), (110, 110, 110), 26)
    cv2.rectangle(img, (int(W * 0.1), int(H * 0.1)), (int(W * 0.1) + 160, int(H * 0.1) + 30), (255, 255, 255), -1)
    return img


def _sample(tex: np.ndarray, mx: np.ndarray, my: np.ndarray) -> np.ndarray:
    """Bilinear lookup of 1-D coordinate lists (cv2.remap needs < 32k rows, so fold into 2-D)."""
    n, cols = len(mx), 4096
    rows = -(-n // cols)
    pad = rows * cols - n
    mx2 = np.pad(mx, (0, pad)).reshape(rows, cols)
    my2 = np.pad(my, (0, pad)).reshape(rows, cols)
    return cv2.remap(tex, mx2, my2, cv2.INTER_LINEAR).reshape(-1, 3)[:n]


class RoomRenderer:
    def __init__(self, room: Room):
        self.room = room
        rng = np.random.default_rng(room.seed)
        kinds = ["door", "window", "bed", "cupboard"]
        rng.shuffle(kinds)
        # faces: +z, +x, -z, -x walls, floor (+y), ceiling (-y)
        self.tex = {
            "+z": _wall(room, room.width, kinds[0], rng),
            "+x": _wall(room, room.length, kinds[1], rng),
            "-z": _wall(room, room.width, kinds[2], rng),
            "-x": _wall(room, room.length, kinds[3], rng),
            "+y": _floor(room, rng),
            "-y": _ceiling(room, rng),
        }

    def shade(self, d: np.ndarray, origin: np.ndarray | None = None) -> np.ndarray:
        """Colour for unit ray directions d (..., 3) cast from `origin` (default: capture point)."""
        x0, x1, y0, y1, z0, z1 = self.room.bounds
        o = np.zeros(3) if origin is None else np.asarray(origin, np.float64)
        shp = d.shape[:-1]
        d = d.reshape(-1, 3).astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            tx = (np.where(d[:, 0] > 0, x1, x0) - o[0]) / d[:, 0]
            ty = (np.where(d[:, 1] > 0, y1, y0) - o[1]) / d[:, 1]
            tz = (np.where(d[:, 2] > 0, z1, z0) - o[2]) / d[:, 2]
        ts = np.stack([tx, ty, tz], 1)
        ts[~np.isfinite(ts) | (ts <= 0)] = np.inf
        axis = ts.argmin(1)
        t = ts[np.arange(len(d)), axis]
        p = o[None, :] + d * t[:, None]
        out = np.zeros((len(d), 3), np.uint8)
        W, L, H = x1 - x0, z1 - z0, y1 - y0
        faces = {
            "+z": ((axis == 2) & (d[:, 2] > 0), (p[:, 0] - x0) / W, (p[:, 1] - y0) / H),
            "-z": ((axis == 2) & (d[:, 2] <= 0), (x1 - p[:, 0]) / W, (p[:, 1] - y0) / H),
            "+x": ((axis == 0) & (d[:, 0] > 0), (z1 - p[:, 2]) / L, (p[:, 1] - y0) / H),
            "-x": ((axis == 0) & (d[:, 0] <= 0), (p[:, 2] - z0) / L, (p[:, 1] - y0) / H),
            "+y": ((axis == 1) & (d[:, 1] > 0), (p[:, 0] - x0) / W, (z1 - p[:, 2]) / L),
            "-y": ((axis == 1) & (d[:, 1] <= 0), (p[:, 0] - x0) / W, (p[:, 2] - z0) / L),
        }
        for name, (mask, u, v) in faces.items():
            if not mask.any():
                continue
            tex = self.tex[name]
            th, tw = tex.shape[:2]
            mx = np.clip(u[mask], 0, 1).astype(np.float32) * (tw - 1)
            my = np.clip(v[mask], 0, 1).astype(np.float32) * (th - 1)
            out[mask] = _sample(tex, mx, my)
        return out.reshape(*shp, 3)

    def perspective(self, yaw_deg: float, pitch_deg: float = 0.0, hfov_deg: float = 65.0, w: int = 1280, h: int = 960, arm: float = 0.0) -> np.ndarray:
        """`arm` > 0 simulates a person turning their body: the phone sits `arm` metres in front of the
        rotation axis, so the camera centre moves on a circle (real-world parallax)."""
        f = (w / 2) / np.tan(np.deg2rad(hfov_deg) / 2)
        xs, ys = np.meshgrid(np.arange(w) + 0.5 - w / 2, np.arange(h) + 0.5 - h / 2)
        r = np.stack([xs / f, ys / f, np.ones_like(xs)], -1)
        a, y = np.deg2rad(pitch_deg), np.deg2rad(yaw_deg)
        Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
        Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
        d = r @ (Ry @ Rx).T
        d /= np.linalg.norm(d, axis=-1, keepdims=True)
        origin = arm * np.array([np.sin(y), 0.0, np.cos(y)])
        return self.shade(d, origin)

    def equirect(self, w: int = 2048) -> np.ndarray:
        from .stitch import _ray_grid

        return self.shade(_ray_grid(w, w // 2, 0, w // 2))


def _camera_effects(img: np.ndarray, rng) -> np.ndarray:
    g = rng.uniform(0.88, 1.12)
    out = img.astype(np.float32) * g + rng.normal(0, 2.5, img.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def capture_photos(room: Room, out_dir: Path, rows=((0, 12), (40, 6), (-40, 6)), hfov=65.0, arm: float = 0.0) -> list[Path]:
    """Simulate a rotation-only phone capture; returns JPEG paths."""
    rr = RoomRenderer(room)
    rng = np.random.default_rng(room.seed + 100)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for pitch, n in rows:
        for k in range(n):
            yaw = k * 360.0 / n + rng.uniform(-3, 3) + (15 if pitch else 0)
            img = _camera_effects(rr.perspective(yaw, pitch + rng.uniform(-2, 2), hfov, arm=arm), rng)
            p = out_dir / f"img_{len(paths):02d}.jpg"
            cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            paths.append(p)
    return paths


def capture_video(room: Room, path: Path, seconds: float = 10.0, fps: int = 12, w: int = 960, h: int = 540, hfov: float = 70.0) -> Path:
    """Simulate a slow 360° turn recorded as video (with a slight hand wobble)."""
    rr = RoomRenderer(room)
    rng = np.random.default_rng(room.seed + 200)
    path.parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = int(seconds * fps)
    for i in range(n):
        yaw = 375.0 * i / (n - 1)
        pitch = 6 * np.sin(i / n * 4 * np.pi) + rng.normal(0, 0.3)
        vw.write(_camera_effects(rr.perspective(yaw, pitch, hfov, w, h), rng))
    vw.release()
    return path
