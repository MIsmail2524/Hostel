"""Input preparation: image loading, video keyframe extraction and capture-quality checks."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .stitch import StitchError

MAX_VIDEO_SECONDS = 180
MAX_FRAMES = 36


def sharpness(img: np.ndarray) -> float:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    s = 640 / max(g.shape)
    if s < 1:
        g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def load_images(paths: list[Path]) -> list[np.ndarray]:
    imgs = []
    for p in paths:
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is not None:
            imgs.append(img)
    return imgs


def _shift(a: np.ndarray, b: np.ndarray) -> float:
    (dx, dy), _ = cv2.phaseCorrelate(a, b)
    return float(np.hypot(dx, dy))


def extract_keyframes(video: Path, max_frames: int = MAX_FRAMES) -> list[np.ndarray]:
    """Pick sharp frames spaced by ~25 % of the frame width of camera motion."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise StitchError("bad_video", "The video could not be read.", ["Upload an MP4/MOV/WebM recorded with the phone camera"])
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if n > 0 and n / fps > MAX_VIDEO_SECONDS:
        cap.release()
        raise StitchError("video_too_long", f"Video is longer than {MAX_VIDEO_SECONDS} s.", ["Record one slow turn of 20–60 seconds"])
    step = max(1, round(fps / 6))  # ~6 candidate frames per second
    cands: list[tuple[np.ndarray, float, np.ndarray]] = []
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if ok and frame is not None:
                small = cv2.cvtColor(cv2.resize(frame, (320, round(320 * frame.shape[0] / frame.shape[1]))), cv2.COLOR_BGR2GRAY)
                cands.append((frame, sharpness(frame), np.float32(small)))
        idx += 1
        if len(cands) > 6 * MAX_VIDEO_SECONDS:
            break
    cap.release()
    if len(cands) < 2:
        raise StitchError("bad_video", "The video has too few frames.", ["Record one slow full turn of the room"])

    width = cands[0][2].shape[1]
    window: list[tuple[np.ndarray, float]] = [(cands[0][0], cands[0][1])]
    keyframes = [cands[0][0]]
    acc = 0.0
    for prev, cur in zip(cands, cands[1:]):
        acc += _shift(prev[2], cur[2])
        window.append((cur[0], cur[1]))
        if acc >= 0.22 * width:
            keyframes.append(max(window, key=lambda t: t[1])[0])
            window, acc = [], 0.0
    if window and acc > 0.08 * width:
        keyframes.append(max(window, key=lambda t: t[1])[0])
    if len(keyframes) < 4:  # very small motion: fall back to uniform sampling
        pick = np.linspace(0, len(cands) - 1, num=min(len(cands), 12)).round().astype(int)
        keyframes = [cands[i][0] for i in sorted(set(pick))]
    if len(keyframes) > max_frames:
        pick = np.linspace(0, len(keyframes) - 1, num=max_frames).round().astype(int)
        keyframes = [keyframes[i] for i in pick]
    return keyframes


@dataclass
class QualityReport:
    count: int
    blurry: int = 0
    dark: int = 0
    hints: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"count": self.count, "blurry": self.blurry, "dark": self.dark, "hints": self.hints}


def assess(images: list[np.ndarray]) -> QualityReport:
    rep = QualityReport(count=len(images))
    for img in images:
        if sharpness(img) < 30:
            rep.blurry += 1
        if float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean()) < 45:
            rep.dark += 1
    if rep.count < 8:
        rep.hints.append("Take at least 12 photos while turning on the spot for a full 360°.")
    if rep.blurry > rep.count * 0.3:
        rep.hints.append("Several photos are blurry — hold the phone steady or turn more slowly.")
    if rep.dark > rep.count * 0.3:
        rep.hints.append("The room is dark — switch on the lights and open curtains.")
    return rep
