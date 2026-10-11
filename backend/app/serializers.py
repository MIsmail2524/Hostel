from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .models import Favorite, Listing, Review, Tour, TourRoom, User, VisitRequest
from .storage import public_url


def _round(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None  # ~1.1 km — protects exact location


def ratings_for(db: Session, ids: list[str]) -> dict[str, tuple[float, int]]:
    if not ids:
        return {}
    rows = db.execute(select(Review.listing_id, func.avg(Review.rating), func.count()).where(Review.listing_id.in_(ids)).group_by(Review.listing_id)).all()
    return {r[0]: (round(float(r[1]), 1), int(r[2])) for r in rows}


def tours_for(db: Session, ids: list[str]) -> dict[str, Tour]:
    if not ids:
        return {}
    return {t.listing_id: t for t in db.scalars(select(Tour).where(Tour.listing_id.in_(ids)))}


def tour_brief(t: Tour | None) -> schemas.TourBrief | None:
    if t is None:
        return None
    ready = [r for r in t.rooms if r.status == "ready"]
    return schemas.TourBrief(id=t.id, status=t.status, progress=t.progress, rooms=len(ready), preview_url=public_url(ready[0].preview_key) if ready else None)


def card(listing: Listing, rating: tuple[float, int] | None, tour: Tour | None) -> schemas.ListingCard:
    cover = listing.photos[0] if listing.photos else None
    return schemas.ListingCard(
        id=listing.id,
        title=listing.title,
        space_type=listing.space_type,
        gender_policy=listing.gender_policy,
        rent_monthly=listing.rent_monthly,
        bills_included=listing.bills_included,
        meals_included=listing.meals_included,
        available_beds=listing.available_beds,
        city=listing.city,
        area=listing.area,
        cover_url=public_url(cover.thumb_key) if cover else None,
        has_tour=bool(tour and tour.status == "ready"),
        owner_verified=listing.owner.is_verified_owner,
        rating=rating[0] if rating else None,
        review_count=rating[1] if rating else 0,
        status=listing.status,
        created_at=listing.created_at,
    )


def cards(db: Session, listings: list[Listing]) -> list[schemas.ListingCard]:
    ids = [x.id for x in listings]
    r, t = ratings_for(db, ids), tours_for(db, ids)
    return [card(x, r.get(x.id), t.get(x.id)) for x in listings]


def can_see_address(db: Session, listing: Listing, user: User | None) -> bool:
    if user is None:
        return False
    if user.id == listing.owner_id or user.is_admin:
        return True
    return db.scalar(
        select(func.count()).select_from(VisitRequest).where(
            VisitRequest.listing_id == listing.id, VisitRequest.seeker_id == user.id, VisitRequest.status == "accepted"
        )
    ) > 0


def detail(db: Session, listing: Listing, user: User | None) -> schemas.ListingOut:
    rating = ratings_for(db, [listing.id]).get(listing.id)
    tour = tours_for(db, [listing.id]).get(listing.id)
    base = card(listing, rating, tour).model_dump()
    is_owner_or_admin = bool(user and (user.id == listing.owner_id or user.is_admin))
    show_tour = tour if (tour and (tour.status == "ready" or is_owner_or_admin)) else None
    out = schemas.ListingOut(
        **base,
        description=listing.description,
        property_name=listing.property_name,
        deposit=listing.deposit,
        capacity=listing.capacity,
        amenities=listing.amenities or [],
        rules=listing.rules,
        approx_lat=_round(listing.lat),
        approx_lng=_round(listing.lng),
        available_from=listing.available_from,
        photos=[schemas.PhotoOut(id=p.id, url=public_url(p.key), thumb_url=public_url(p.thumb_key), width=p.width, height=p.height) for p in listing.photos],
        tour=tour_brief(show_tour),
        owner=schemas.PublicUserOut.model_validate(listing.owner),
        views=listing.views if is_owner_or_admin else 0,
        rejection_reason=listing.rejection_reason if is_owner_or_admin else None,
    )
    if user is not None:
        out.is_favorite = db.get(Favorite, (user.id, listing.id)) is not None
    if can_see_address(db, listing, user):
        out.address_line, out.lat, out.lng = listing.address_line, listing.lat, listing.lng
    return out


def room_out(r: TourRoom) -> schemas.RoomOut:
    return schemas.RoomOut(
        id=r.id, name=r.name, position=r.position, input_kind=r.input_kind, input_count=len(r.inputs),
        width_m=r.width_m, length_m=r.length_m, height_m=r.height_m, status=r.status, error_code=r.error_code,
        error_message=r.error_message, hints=r.hints or [], quality=r.quality or {}, preview_url=public_url(r.preview_key),
        yaw_offset_deg=r.yaw_offset_deg,
    )


def tour_out(t: Tour) -> schemas.TourOut:
    return schemas.TourOut(id=t.id, listing_id=t.listing_id, engine=t.engine, status=t.status, progress=t.progress, message=t.message, rooms=[room_out(r) for r in t.rooms], updated_at=t.updated_at)
