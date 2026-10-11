"""DB-backed job worker. Run in-process for dev (`KAMRA_RUN_WORKER_IN_PROCESS=true`) or standalone:

    python -m app.recon.worker
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from datetime import timedelta

from sqlalchemy import select, update

from .. import storage
from ..db import SessionLocal, init_db
from ..models import Job, Tour, TourRoom
from ..security import aware, now
from .engines import RoomInputs, get_engine, run_isolated
from .stitch import StitchError

log = logging.getLogger("kamra.worker")
MAX_ATTEMPTS = 3


def enqueue(db, kind: str, ref_id: str) -> Job:
    job = Job(kind=kind, ref_id=ref_id)
    db.add(job)
    return job


def claim(db) -> Job | None:
    cand = db.scalar(select(Job.id).where(Job.status == "queued").order_by(Job.created_at).limit(1))
    if cand is None:
        return None
    res = db.execute(update(Job).where(Job.id == cand, Job.status == "queued").values(status="running", locked_at=now(), attempts=Job.attempts + 1))
    db.commit()
    if res.rowcount != 1:  # another worker won the race
        return None
    return db.get(Job, cand)


def recover_stale(db, older_than_min: int = 30) -> None:
    cutoff = now() - timedelta(minutes=older_than_min)
    for job in db.scalars(select(Job).where(Job.status == "running")):
        if job.locked_at and aware(job.locked_at) < cutoff:
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
    db.commit()


def process_tour(db, tour_id: str) -> None:
    tour = db.get(Tour, tour_id)
    if tour is None:
        return
    engine = get_engine(tour.engine)
    rooms = [r for r in tour.rooms if r.inputs]
    tour.status, tour.progress, tour.message = "processing", 0.0, "Starting"
    db.commit()
    for i, room in enumerate(rooms):
        room.status, room.error_code, room.error_message, room.hints = "processing", None, None, []
        db.commit()

        def progress(frac: float, msg: str, _i=i, _room=room):
            tour.progress = round((_i + frac) / len(rooms), 3)
            tour.message = f"{_room.name}: {msg}"
            db.commit()

        kind = "video" if any(x.kind == "video" for x in room.inputs) else "photos"
        paths = [storage.path_for(x.key) for x in room.inputs if (x.kind == "video") == (kind == "video")]
        try:
            res = run_isolated(engine.name, tour.id, room.id, RoomInputs(kind, paths), progress)
            for old in (room.pano_key, room.pano_small_key, room.preview_key):
                storage.delete(old)
            room.pano_key, room.pano_small_key, room.preview_key = res.pano_key, res.pano_small_key, res.preview_key
            room.quality, room.hints, room.status = res.quality, res.hints, "ready"
        except StitchError as e:
            room.status, room.error_code, room.error_message, room.hints = "failed", e.code, e.message, e.hints
        except Exception as e:  # unexpected — keep the worker alive, surface a generic error
            log.error("room %s failed: %s\n%s", room.id, e, traceback.format_exc())
            room.status, room.error_code, room.error_message = "failed", "internal", "Something went wrong while processing this room."
            room.hints = ["Try again; if it keeps failing, re-capture the room"]
        db.commit()
    ready = [r for r in tour.rooms if r.status == "ready"]
    failed = [r for r in rooms if r.status == "failed"]
    tour.progress = 1.0
    if ready:
        tour.status = "ready"
        tour.message = f"{len(ready)} room(s) ready" + (f", {len(failed)} failed" if failed else "")
    else:
        tour.status = "failed"
        tour.message = "No room could be reconstructed. See tips for each room."
    db.commit()


def run_once() -> bool:
    with SessionLocal() as db:
        job = claim(db)
        if job is None:
            return False
        try:
            if job.kind == "tour.process":
                process_tour(db, job.ref_id)
            job.status = "done"
        except Exception as e:
            db.rollback()
            job = db.get(Job, job.id)
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.error = f"{e}\n{traceback.format_exc()}"[:4000]
            log.error("job %s failed: %s", job.id, e)
        db.commit()
        return True


def loop(stop: threading.Event, idle_sleep: float = 1.0) -> None:
    with SessionLocal() as db:
        recover_stale(db)
    while not stop.is_set():
        try:
            if not run_once():
                stop.wait(idle_sleep)
        except Exception as e:  # pragma: no cover
            log.error("worker loop error: %s", e)
            stop.wait(5)


_stop = threading.Event()
_thread: threading.Thread | None = None


def start_background() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=loop, args=(_stop,), name="recon-worker", daemon=True)
    _thread.start()


def stop_background() -> None:
    _stop.set()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    log.info("recon worker started")
    try:
        loop(threading.Event())
    except KeyboardInterrupt:
        time.sleep(0)
