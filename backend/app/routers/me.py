from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas, serializers, storage
from ..db import get_db
from ..deps import audit, current_user
from ..models import Favorite, Listing, User
from ..security import verify_password

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=schemas.UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("", response_model=schemas.UserOut)
def update_me(body: schemas.ProfileUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(user, k, v)
    db.commit()
    return user


@router.post("/delete", status_code=204)
def delete_account(body: schemas.DeleteAccountIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Right to erasure: re-authenticate, then cascade-delete the account and its content."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Password is incorrect")
    for listing in db.scalars(select(Listing).where(Listing.owner_id == user.id)):
        for p in listing.photos:
            storage.delete(p.key)
            storage.delete(p.thumb_key)
    audit(db, request, None, "user.deleted", "user", user.id)
    db.delete(user)
    db.commit()


@router.get("/favorites", response_model=list[schemas.ListingCard])
def favorites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Listing).join(Favorite, Favorite.listing_id == Listing.id).where(Favorite.user_id == user.id, Listing.status.in_(["active", "rented"])).order_by(Favorite.created_at.desc())))
    return serializers.cards(db, rows)
