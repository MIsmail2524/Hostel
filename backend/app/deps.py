from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditLog, Listing, User
from .ratelimit import client_ip
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def _user_from_token(db: Session, creds: HTTPAuthorizationCredentials | None) -> User | None:
    if creds is None or creds.scheme.lower() != "bearer":
        return None
    data = decode_token(creds.credentials, "access")
    if not data:
        return None
    user = db.get(User, data["sub"])
    if user is None or user.token_version != data.get("ver") or user.is_suspended:
        return None
    return user


def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User | None:
    return _user_from_token(db, creds)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    user = _user_from_token(db, creds)
    if user is None:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


def verified_user(user: User = Depends(current_user)) -> User:
    if not user.contact_verified:
        raise HTTPException(403, "Verify your phone/email first")
    return user


def owner_user(user: User = Depends(verified_user)) -> User:
    if not user.is_owner:
        raise HTTPException(403, "Switch to an owner account to list spaces")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    return user


def owned_listing(db: Session, listing_id: str, user: User) -> Listing:
    """Object-level authorisation: 404 (not 403) for other people's listings to avoid leaking existence."""
    listing = db.get(Listing, listing_id)
    if listing is None or (listing.owner_id != user.id and not user.is_admin):
        raise HTTPException(404, "Listing not found")
    return listing


def audit(db: Session, request: Request | None, actor: User | None, action: str, target_type: str | None = None, target_id: str | None = None, **meta) -> None:
    db.add(AuditLog(actor_id=actor.id if actor else None, action=action, target_type=target_type, target_id=target_id, meta=meta, ip=client_ip(request) if request else None))
