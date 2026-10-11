from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas, serializers
from ..db import get_db
from ..deps import admin_user, audit
from ..models import AuditLog, Listing, Report, User
from ..security import revoke_all_sessions

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(Listing.status, func.count()).group_by(Listing.status)).all())
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "listings": by_status,
        "open_reports": db.scalar(select(func.count()).select_from(Report).where(Report.status == "open")),
    }


@router.get("/listings/pending", response_model=list[schemas.ListingCard])
def pending(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Listing).where(Listing.status == "pending_review").order_by(Listing.updated_at)))
    return serializers.cards(db, rows)


@router.post("/listings/{listing_id}/moderate", response_model=schemas.ListingCard)
def moderate(listing_id: str, body: schemas.ModerateIn, request: Request, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(404, "Listing not found")
    if listing.status != "pending_review":
        raise HTTPException(409, "Listing is not pending review")
    if body.action == "reject" and not body.reason:
        raise HTTPException(422, "Give the owner a reason so they can fix it")
    listing.status = "active" if body.action == "approve" else "rejected"
    listing.rejection_reason = body.reason if body.action == "reject" else None
    audit(db, request, admin, f"listing.{body.action}", "listing", listing.id, reason=body.reason)
    db.commit()
    return serializers.cards(db, [listing])[0]


@router.get("/reports")
def reports(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).where(Report.status == "open").order_by(Report.created_at).limit(200))
    return [{"id": r.id, "target_type": r.target_type, "target_id": r.target_id, "reason": r.reason, "details": r.details, "created_at": r.created_at} for r in rows]


@router.post("/reports/{report_id}")
def resolve_report(report_id: str, body: schemas.ReportResolveIn, request: Request, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(404, "Report not found")
    r.status, r.resolution_note = body.status, body.note
    audit(db, request, admin, f"report.{body.status}", "report", r.id)
    db.commit()
    return {"id": r.id, "status": r.status}


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: str, body: schemas.AdminUserUpdateIn, request: Request, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    if u.id == admin.id and body.is_suspended:
        raise HTTPException(422, "You cannot suspend yourself")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        if v is not None:
            setattr(u, k, v)
    if changes.get("is_suspended"):
        revoke_all_sessions(db, u)
    audit(db, request, admin, "user.admin_update", "user", u.id, **{k: v for k, v in changes.items()})
    db.commit()
    return u


@router.get("/audit")
def audit_log(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    return [{"action": a.action, "actor_id": a.actor_id, "target_type": a.target_type, "target_id": a.target_id, "meta": a.meta, "ip": a.ip, "at": a.created_at} for a in rows]
