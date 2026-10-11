from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import schemas, serializers, storage
from ..config import get_settings
from ..db import get_db
from ..deps import audit, current_user, optional_user, owned_listing, owner_user
from ..media import save_listing_photo
from ..models import Favorite, Listing, ListingPhoto, Review, Tour, User
from ..ratelimit import limit

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=schemas.Page)
def search(
    request: Request,
    q: str | None = Query(None, max_length=80),
    city: str | None = Query(None, max_length=60),
    area: str | None = Query(None, max_length=80),
    space_type: list[schemas.SpaceType] | None = Query(None),
    gender: schemas.GenderPolicy | None = None,
    min_rent: int | None = Query(None, ge=0),
    max_rent: int | None = Query(None, ge=0),
    amenities: list[str] | None = Query(None, max_length=10),
    has_tour: bool = False,
    verified: bool = False,
    meals: bool = False,
    bills: bool = False,
    sort: Literal["newest", "price_asc", "price_desc"] = "newest",
    page: int = Query(1, ge=1, le=500),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    limit(request, "search", 120, 60)
    conds = [Listing.status == "active"]
    if q:
        like = f"%{q.lower().replace('%', '').replace('_', '')}%"
        conds.append(or_(func.lower(Listing.title).like(like), func.lower(Listing.area).like(like), func.lower(Listing.description).like(like), func.lower(func.coalesce(Listing.property_name, "")).like(like)))
    if city:
        conds.append(func.lower(Listing.city) == city.lower())
    if area:
        conds.append(func.lower(Listing.area).like(f"%{area.lower().replace('%', '')}%"))
    if space_type:
        conds.append(Listing.space_type.in_(space_type))
    if gender:
        # A seeker filtering "female" should also see "any" policies.
        conds.append(Listing.gender_policy.in_([gender, "any"]) if gender in ("male", "female") else Listing.gender_policy == gender)
    if min_rent is not None:
        conds.append(Listing.rent_monthly >= min_rent)
    if max_rent is not None:
        conds.append(Listing.rent_monthly <= max_rent)
    if meals:
        conds.append(Listing.meals_included.is_(True))
    if bills:
        conds.append(Listing.bills_included.is_(True))
    if has_tour:
        conds.append(Listing.id.in_(select(Tour.listing_id).where(Tour.status == "ready")))
    if verified:
        conds.append(Listing.owner_id.in_(select(User.id).where(User.is_verified_owner.is_(True))))
    stmt = select(Listing).where(and_(*conds))
    order = {"newest": Listing.created_at.desc(), "price_asc": Listing.rent_monthly.asc(), "price_desc": Listing.rent_monthly.desc()}[sort]
    stmt = stmt.order_by(order, Listing.id)
    if amenities:  # JSON containment differs across DBs; filter in Python (use a GIN index + @> on Postgres at scale)
        want = set(amenities)
        rows = [r for r in db.scalars(stmt) if want.issubset(set(r.amenities or []))]
        total = len(rows)
        rows = rows[(page - 1) * page_size : page * page_size]
    else:
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return schemas.Page(items=serializers.cards(db, rows), total=total, page=page, page_size=page_size)


@router.get("/cities")
def cities(db: Session = Depends(get_db)):
    rows = db.execute(select(Listing.city, func.count()).where(Listing.status == "active").group_by(Listing.city).order_by(func.count().desc())).all()
    return [{"city": c, "count": n} for c, n in rows]


@router.get("/mine", response_model=list[schemas.ListingCard])
def mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Listing).where(Listing.owner_id == user.id).order_by(Listing.created_at.desc())))
    return serializers.cards(db, rows)


@router.post("", response_model=schemas.ListingOut, status_code=201)
def create(body: schemas.ListingIn, request: Request, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    limit(request, "listing-create", 20, 3600, key=user.id)
    count = db.scalar(select(func.count()).select_from(Listing).where(Listing.owner_id == user.id))
    if count >= 100:
        raise HTTPException(403, "Listing limit reached")
    listing = Listing(owner_id=user.id, status="draft", **body.model_dump())
    db.add(listing)
    db.flush()
    audit(db, request, user, "listing.create", "listing", listing.id)
    db.commit()
    db.refresh(listing)
    return serializers.detail(db, listing, user)


@router.get("/{listing_id}", response_model=schemas.ListingOut)
def get_listing(listing_id: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(404, "Listing not found")
    is_privileged = user is not None and (user.id == listing.owner_id or user.is_admin)
    if listing.status not in ("active", "rented") and not is_privileged:
        raise HTTPException(404, "Listing not found")
    if not is_privileged:
        listing.views += 1
        db.commit()
    return serializers.detail(db, listing, user)


@router.put("/{listing_id}", response_model=schemas.ListingOut)
def update(listing_id: str, body: schemas.ListingUpdateIn, request: Request, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    for k, v in body.model_dump().items():
        setattr(listing, k, v)
    if listing.status in ("active", "paused", "rejected"):
        # Material edits are re-reviewed — prevents bait-and-switch after approval.
        listing.status = "pending_review"
        listing.rejection_reason = None
    audit(db, request, user, "listing.update", "listing", listing.id)
    db.commit()
    return serializers.detail(db, listing, user)


class AvailabilityIn(schemas.In):
    available_beds: int = Field(ge=0, le=500)


@router.patch("/{listing_id}/availability", response_model=schemas.ListingOut)
def availability(listing_id: str, body: AvailabilityIn, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    if body.available_beds > listing.capacity:
        raise HTTPException(422, "Available beds cannot exceed capacity")
    listing.available_beds = body.available_beds
    db.commit()
    return serializers.detail(db, listing, user)


class StatusIn(schemas.In):
    action: Literal["submit", "pause", "resume", "rented"]


_TRANSITIONS = {
    "submit": ({"draft", "rejected"}, "pending_review"),
    "pause": ({"active"}, "paused"),
    "resume": ({"paused"}, "active"),
    "rented": ({"active", "paused"}, "rented"),
}


@router.post("/{listing_id}/status", response_model=schemas.ListingOut)
def change_status(listing_id: str, body: StatusIn, request: Request, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    allowed, target = _TRANSITIONS[body.action]
    if listing.status not in allowed:
        raise HTTPException(409, f"Cannot {body.action} a listing that is {listing.status.replace('_', ' ')}")
    if body.action == "submit" and not listing.photos:
        raise HTTPException(422, "Add at least one photo before submitting")
    listing.status = target
    audit(db, request, user, f"listing.{body.action}", "listing", listing.id)
    db.commit()
    return serializers.detail(db, listing, user)


@router.delete("/{listing_id}", status_code=204)
def delete(listing_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    for p in listing.photos:
        storage.delete(p.key)
        storage.delete(p.thumb_key)
    audit(db, request, user, "listing.delete", "listing", listing.id)
    db.delete(listing)
    db.commit()


# ---------------------------------------------------------------- photos
@router.post("/{listing_id}/photos", response_model=list[schemas.PhotoOut], status_code=201)
async def upload_photos(listing_id: str, request: Request, files: list[UploadFile] = File(...), user: User = Depends(owner_user), db: Session = Depends(get_db)):
    limit(request, "photo-upload", 120, 3600, key=user.id)
    listing = owned_listing(db, listing_id, user)
    s = get_settings()
    if len(listing.photos) + len(files) > s.max_photos_per_listing:
        raise HTTPException(422, f"A listing can have at most {s.max_photos_per_listing} photos")
    created = []
    start = len(listing.photos)
    for i, f in enumerate(files):
        key, tkey, w, h = await save_listing_photo(f, listing.id)
        p = ListingPhoto(listing_id=listing.id, key=key, thumb_key=tkey, width=w, height=h, position=start + i)
        db.add(p)
        created.append(p)
    db.commit()
    return [schemas.PhotoOut(id=p.id, url=storage.public_url(p.key), thumb_url=storage.public_url(p.thumb_key), width=p.width, height=p.height) for p in created]


@router.delete("/{listing_id}/photos/{photo_id}", status_code=204)
def delete_photo(listing_id: str, photo_id: str, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    photo = next((p for p in listing.photos if p.id == photo_id), None)
    if photo is None:
        raise HTTPException(404, "Photo not found")
    storage.delete(photo.key)
    storage.delete(photo.thumb_key)
    db.delete(photo)
    db.commit()


class OrderIn(BaseModel):
    photo_ids: list[str] = Field(max_length=50)


@router.put("/{listing_id}/photos/order", status_code=204)
def reorder(listing_id: str, body: OrderIn, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    listing = owned_listing(db, listing_id, user)
    by_id = {p.id: p for p in listing.photos}
    if set(body.photo_ids) != set(by_id):
        raise HTTPException(422, "Order must contain every photo exactly once")
    for i, pid in enumerate(body.photo_ids):
        by_id[pid].position = i
    db.commit()


# ---------------------------------------------------------------- favourites & reviews
@router.post("/{listing_id}/favorite", status_code=204)
def favorite(listing_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None or listing.status not in ("active", "rented"):
        raise HTTPException(404, "Listing not found")
    if db.get(Favorite, (user.id, listing_id)) is None:
        db.add(Favorite(user_id=user.id, listing_id=listing_id))
        db.commit()


@router.delete("/{listing_id}/favorite", status_code=204)
def unfavorite(listing_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    fav = db.get(Favorite, (user.id, listing_id))
    if fav:
        db.delete(fav)
        db.commit()


@router.get("/{listing_id}/reviews", response_model=list[schemas.ReviewOut])
def reviews(listing_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(select(Review).where(Review.listing_id == listing_id).order_by(Review.created_at.desc()).limit(100))
    return [schemas.ReviewOut(id=r.id, rating=r.rating, body=r.body, owner_reply=r.owner_reply, author_name=r.author.full_name.split()[0], created_at=r.created_at) for r in rows]


@router.post("/{listing_id}/reviews", response_model=schemas.ReviewOut, status_code=201)
def add_review(listing_id: str, body: schemas.ReviewIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None or listing.status not in ("active", "rented"):
        raise HTTPException(404, "Listing not found")
    if listing.owner_id == user.id:
        raise HTTPException(403, "You cannot review your own listing")
    if not serializers.can_see_address(db, listing, user):
        raise HTTPException(403, "You can review after the owner accepts your visit")
    if db.scalar(select(Review).where(Review.listing_id == listing_id, Review.author_id == user.id)):
        raise HTTPException(409, "You already reviewed this listing")
    r = Review(listing_id=listing_id, author_id=user.id, rating=body.rating, body=body.body)
    db.add(r)
    audit(db, request, user, "review.create", "listing", listing_id)
    db.commit()
    return schemas.ReviewOut(id=r.id, rating=r.rating, body=r.body, owner_reply=None, author_name=user.full_name.split()[0], created_at=r.created_at)


@router.post("/{listing_id}/reviews/{review_id}/reply", response_model=schemas.ReviewOut)
def reply_review(listing_id: str, review_id: str, body: schemas.ReviewReplyIn, user: User = Depends(owner_user), db: Session = Depends(get_db)):
    owned_listing(db, listing_id, user)
    r = db.get(Review, review_id)
    if r is None or r.listing_id != listing_id:
        raise HTTPException(404, "Review not found")
    r.owner_reply = body.reply
    db.commit()
    return schemas.ReviewOut(id=r.id, rating=r.rating, body=r.body, owner_reply=r.owner_reply, author_name=r.author.full_name.split()[0], created_at=r.created_at)

