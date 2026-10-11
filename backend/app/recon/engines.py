"""Reconstruction engines behind one interface.

* Room360Engine     — CPU. Photos/video (rotation capture) → 360° equirect panorama → textured room shell.
* GaussianSplatEngine — GPU (remote worker). Video walk-around → 3D Gaussian splat. Enabled by KAMRA_GPU_WORKER_URL.
"""
from __future__ import annotations

import multiprocessing as mp
import queue as _queue
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from .. import storage
from ..config import get_settings
from .frames import assess, extract_keyframes, load_images
from .stitch import StitchError, stitch_equirect

Progress = Callable[[float, str], None]


@dataclass
class RoomInputs:
    kind: str  # photos | video
    paths: list[Path]


@dataclass
class RoomResult:
    pano_key: str
    pano_small_key: str
    preview_key: str
    quality: dict = field(default_factory=dict)
    hints: list[str] = field(default_factory=list)


class ReconstructionEngine:
    name = "base"

    def available(self) -> bool:
        return True

    def process_room(self, tour_id: str, room_id: str, inputs: RoomInputs, progress: Progress) -> RoomResult:
        raise NotImplementedError


class Room360Engine(ReconstructionEngine):
    name = "room360"

    def process_room(self, tour_id: str, room_id: str, inputs: RoomInputs, progress: Progress) -> RoomResult:
        progress(0.05, "Reading your capture")
        if inputs.kind == "video":
            images = extract_keyframes(inputs.paths[0])
        else:
            images = load_images(inputs.paths)
        if len(images) < 2:
            raise StitchError("too_few_images", "At least 2 overlapping photos are needed.", ["Take 12 or more photos while turning on the spot"])
        report = assess(images)
        progress(0.2, f"Aligning {len(images)} views")
        result = stitch_equirect(images, out_w=get_settings().recon_output_width)
        progress(0.85, "Building 3D room")
        hints = list(report.hints)
        if result.horizontal_coverage < 0.9:
            hints.append(f"Only {round(result.horizontal_coverage * 360)}° of the room was captured — turn a full circle next time.")
        if result.sphere_coverage < 0.6:
            hints.append("Add one turn tilted up (ceiling) and one tilted down (floor) for a more complete room.")
        if result.dropped:
            hints.append(f"{len(result.dropped)} photo(s) could not be matched and were skipped.")
        prefix = f"tours/{tour_id}/{room_id}"
        pano_key = storage.new_key("public", prefix, ".jpg")
        small_key = pano_key.replace(".jpg", "_2k.jpg")
        preview_key = pano_key.replace(".jpg", "_preview.jpg")
        storage.path_for(pano_key).parent.mkdir(parents=True, exist_ok=True)
        pano = result.pano
        cv2.imwrite(str(storage.path_for(pano_key)), pano, [cv2.IMWRITE_JPEG_QUALITY, 88, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
        cv2.imwrite(str(storage.path_for(small_key)), cv2.resize(pano, (2048, 1024), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
        h, w = pano.shape[:2]
        crop = pano[int(h * 0.3) : int(h * 0.7), int(w * 0.3) : int(w * 0.7)]  # forward-facing preview
        cv2.imwrite(str(storage.path_for(preview_key)), cv2.resize(crop, (800, 400), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 80])
        quality = {
            **report.as_dict(),
            "used": len(result.used),
            "dropped": len(result.dropped),
            "horizontal_coverage": round(result.horizontal_coverage, 3),
            "sphere_coverage": round(result.sphere_coverage, 3),
            "width": w,
        }
        progress(1.0, "Done")
        return RoomResult(pano_key, small_key, preview_key, quality, hints)


class GaussianSplatEngine(ReconstructionEngine):
    """Premium photoreal engine. The API only accepts it when a GPU worker is configured.

    Contract with the remote worker (see docs/03): POST {GPU_WORKER_URL}/jobs with signed input URLs →
    worker runs COLMAP + gsplat → uploads .spz/.splat → calls back /internal/tours/{id}/rooms/{id}.
    """

    name = "gsplat"

    def available(self) -> bool:
        return bool(get_settings().gpu_worker_url)

    def process_room(self, tour_id: str, room_id: str, inputs: RoomInputs, progress: Progress) -> RoomResult:
        raise StitchError("engine_unavailable", "The photoreal (GPU) engine is not enabled on this server.", ["Use the standard 3D engine"])


ENGINES: dict[str, ReconstructionEngine] = {e.name: e for e in (Room360Engine(), GaussianSplatEngine())}


def get_engine(name: str) -> ReconstructionEngine:
    return ENGINES.get(name, ENGINES["room360"])


# ---------------------------------------------------------------- process isolation
# Native CV code runs on untrusted media: a crash (or a pathological input) must never take
# down the API/worker. Each room is processed in a fresh child process with a hard timeout.
_CTX = mp.get_context("spawn")


def _child(engine_name: str, tour_id: str, room_id: str, inputs: RoomInputs, q) -> None:
    cv2.setNumThreads(2)

    def progress(frac: float, msg: str) -> None:
        q.put(("progress", frac, msg))

    try:
        res = get_engine(engine_name).process_room(tour_id, room_id, inputs, progress)
        q.put(("ok", res))
    except StitchError as e:
        q.put(("stitch_error", e.code, e.message, e.hints))
    except Exception as e:  # noqa: BLE001
        q.put(("error", f"{type(e).__name__}: {e}"))


def run_isolated(engine_name: str, tour_id: str, room_id: str, inputs: RoomInputs, progress: Progress, timeout_s: int = 900, retries: int = 1) -> RoomResult:
    last = "unknown"
    for _attempt in range(retries + 1):
        q = _CTX.Queue()
        proc = _CTX.Process(target=_child, args=(engine_name, tour_id, room_id, inputs, q), daemon=True)
        proc.start()
        deadline = time.monotonic() + timeout_s
        result = None
        while result is None:
            try:
                msg = q.get(timeout=0.5)
            except _queue.Empty:
                if not proc.is_alive():
                    break
                if time.monotonic() > deadline:
                    proc.kill()
                    raise StitchError("timeout", "Processing took too long.", ["Use fewer photos or a shorter video"])
                continue
            if msg[0] == "progress":
                progress(msg[1], msg[2])
            else:
                result = msg
        proc.join(timeout=5)
        if result is None:
            last = f"worker exited with code {proc.exitcode}"
            continue  # native crash → retry in a fresh process
        if result[0] == "ok":
            return result[1]
        if result[0] == "stitch_error":
            raise StitchError(result[1], result[2], result[3])
        raise RuntimeError(result[1])
    raise RuntimeError(last)
