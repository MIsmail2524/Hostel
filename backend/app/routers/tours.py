from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas, serializers, storage
from ..config import get_settings
from ..db import get_db
from ..deps import audit, owned_listing, owner_user
from ..media import save_tour_image, save_tour_video, sniff
from ..models import Listing, Tour, TourInput, TourRoom, User
from ..ratelimit import limit
from ..recon.engines import get_engine
from ..recon.worker import enqueue
from ..security import create_scoped_token, decode_token

router = APIRouter(tags=["tours"])
MAX_ROOMS = 12


def _owned_tour(db: Session, tour_id: str, user: User) -> Tour:
    tour = db.get(Tour, tour_id)
    if tour is None or (tour.owner_id != user.id and not user.is_admin):
        raise HTTPException(404, "Tour not found")
    return tour


def _room(tour: Tour, room_id: str) -> TourRoom:
    room = next((r for r in tour.rooms if r.id == room_id), None)
    if room is None:
        raise HTTPException(404, "Room not found")
    return room


def _editable(tour: Tour) -> None:
    if tour.status in ("queued", "processing"):
        raise HTTPException(409, "The tour is being processed. Please wait until it finishes.")


@router.post("/listings/{listing_id}/tour", response_model=schemas.TourOut, status_code=201)
def create_tour(listing_id: str, body: schemas.TourCreateIn, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    if not get_engine(body.engine).available() or get_engine(body.engine).name != body.engine:
        raise HTTPException(422, "The photoreal (GPU) engine is not available yet. Use the standard 3D engine.")
    existing = db.scalar(select(Tour).where(Tour.listing_id == listing.id))
    if existing:
        return serializers.tour_out(existing)
    tour = Tour(listing_id=listing.id, owner_id=listing.owner_id, engine=body.engine)
    db.add(tour)
    db.commit()
    db.refresh(tour)
    return serializers.tour_out(tour)


@router.get("/tours/{tour_id}", response_model=schemas.TourOut)
def get_tour(tour_id: str, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    return serializers.tour_out(_owned_tour(db, tour_id, user))


@router.post("/tours/{tour_id}/rooms", response_model=schemas.RoomOut, status_code=201)
def add_room(tour_id: str, body: schemas.RoomIn, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    tour = _owned_tour(db, tour_id, user)
    _editable(tour)
    if len(tour.rooms) >= MAX_ROOMS:
        raise HTTPException(422, f"A tour can have at most {MAX_ROOMS} rooms")
    room = TourRoom(tour_id=tour.id, position=len(tour.rooms), **body.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return serializers.room_out(room)


@router.patch("/tours/{tour_id}/rooms/{room_id}", response_model=schemas.RoomOut)
def update_room(tour_id: str, room_id: str, body: schemas.RoomUpdateIn, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    tour = _owned_tour(db, tour_id, user)
    room = _room(tour, room_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(room, k, v)
    db.commit()
    return serializers.room_out(room)


@router.delete("/tours/{tour_id}/rooms/{room_id}", status_code=204)
def delete_room(tour_id: str, room_id: str, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    tour = _owned_tour(db, tour_id, user)
    _editable(tour)
    room = _room(tour, room_id)
    for k in [x.key for x in room.inputs] + [room.pano_key, room.pano_small_key, room.preview_key]:
        storage.delete(k)
    db.delete(room)
    db.flush()
    for i, r in enumerate(sorted([r for r in tour.rooms if r.id != room_id], key=lambda r: r.position)):
        r.position = i
    if not any(r.status == "ready" for r in tour.rooms if r.id != room_id):
        tour.status = "draft"
    db.commit()


@router.post("/tours/{tour_id}/rooms/{room_id}/inputs", response_model=schemas.RoomOut, status_code=201)
async def upload_inputs(tour_id: str, room_id: str, request: Request, files: list[UploadFile] = File(...), user: User = Depends(owner_user), db: Session = Depends(get_db)):
    limit(request, "tour-upload", 300, 3600, key=user.id)
    tour = _owned_tour(db, tour_id, user)
    _editable(tour)
    room = _room(tour, room_id)
    s = get_settings()
    for f in files:
        head = await f.read(16)
        await f.seek(0)
        kind = sniff(head)
        is_video = kind in ("mp4", "webm")
        if is_video:
            if room.inputs:
                raise HTTPException(422, "A room takes either photos or one video. Clear the room's media first.")
            key = await save_tour_video(f, tour.id)
            db.add(TourInput(room_id=room.id, kind="video", key=key, seq=0))
            room.input_kind = "video"
            db.flush()
            db.refresh(room)
        else:
            if room.input_kind == "video":
                raise HTTPException(422, "This room already has a video. Clear it to upload photos instead.")
            if len(room.inputs) >= s.max_inputs_per_room:
                raise HTTPException(422, f"At most {s.max_inputs_per_room} photos per room")
            key = await save_tour_image(f, tour.id)
            db.add(TourInput(room_id=room.id, kind="image", key=key, seq=len(room.inputs)))
            room.input_kind = "photos"
            db.flush()
            db.refresh(room)
    room.status = "draft"
    db.commit()
    db.refresh(room)
    return serializers.room_out(room)


@router.delete("/tours/{tour_id}/rooms/{room_id}/inputs", response_model=schemas.RoomOut)
def clear_inputs(tour_id: str, room_id: str, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    tour = _owned_tour(db, tour_id, user)
    _editable(tour)
    room = _room(tour, room_id)
    for x in list(room.inputs):
        storage.delete(x.key)
        db.delete(x)
    room.input_kind = None
    db.commit()
    db.refresh(room)
    return serializers.room_out(room)


@router.post("/tours/{tour_id}/process", response_model=schemas.TourOut)
def process(tour_id: str, request: Request, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    limit(request, "tour-process", 20, 3600, key=user.id)
    tour = _owned_tour(db, tour_id, user)
    _editable(tour)
    if not tour.rooms:
        raise HTTPException(422, "Add at least one room")
    empty = [r.name for r in tour.rooms if not r.inputs]
    if empty:
        raise HTTPException(422, f"Add photos or a video for: {', '.join(empty)}")
    for r in tour.rooms:
        if r.input_kind == "photos" and len(r.inputs) < 4:
            raise HTTPException(422, f"'{r.name}' needs at least 4 photos (12+ recommended)")
    tour.status, tour.progress, tour.message = "queued", 0.0, "Waiting in queue"
    enqueue(db, "tour.process", tour.id)
    audit(db, request, user, "tour.process", "tour", tour.id)
    db.commit()
    return serializers.tour_out(tour)


@router.post("/tours/{tour_id}/preview-link")
def preview_link(tour_id: str, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    tour = _owned_tour(db, tour_id, user)
    token = create_scoped_token(tour.id, "tour_preview", minutes=30)
    return {"path": f"/viewer/?tour={tour.id}&t={token}", "expires_in": 1800}


@router.get("/tours/{tour_id}/manifest")
def manifest(tour_id: str, t: str | None = Query(None, max_length=600), db: Session = Depends(get_db)):
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise HTTPException(404, "Tour not found")
    listing = db.get(Listing, tour.listing_id)
    public_ok = tour.status == "ready" and listing is not None and listing.status in ("active", "rented")
    token_ok = False
    if t:
        data = decode_token(t, "tour_preview")
        token_ok = bool(data and data.get("sub") == tour.id)
    if not (public_ok or token_ok):
        raise HTTPException(404, "Tour not found")
    rooms = [r for r in tour.rooms if r.status == "ready"]
    x = 0.0
    out_rooms = []
    for r in rooms:
        out_rooms.append(
            {
                "id": r.id,
                "name": r.name,
                "pano": storage.public_url(r.pano_key),
                "pano_small": storage.public_url(r.pano_small_key),
                "preview": storage.public_url(r.preview_key),
                "width": r.width_m,
                "length": r.length_m,
                "height": r.height_m,
                "camera_height": 1.5,
                "yaw_offset": r.yaw_offset_deg,
                "origin": [round(x + r.width_m / 2, 3), 0.0],
            }
        )
        x += r.width_m + 0.4
    links = [{"from": a["id"], "to": b["id"]} for a, b in zip(out_rooms, out_rooms[1:])]
    return {
        "id": tour.id,
        "version": 1,
        "engine": tour.engine,
        "title": listing.title if listing else "",
        "listing_id": tour.listing_id,
        "rooms": out_rooms,
        "links": links,
    }
