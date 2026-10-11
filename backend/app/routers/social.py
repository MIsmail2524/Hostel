"""Conversations, messages, visit requests and reports."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from .. import schemas, storage
from ..db import get_db
from ..deps import audit, current_user, verified_user
from ..models import Conversation, Listing, Message, Report, User, VisitRequest
from ..ratelimit import limit
from ..security import aware, now

router = APIRouter(tags=["social"])


def _conv_for(db: Session, conv_id: str, user: User) -> Conversation:
    c = db.get(Conversation, conv_id)
    if c is None or user.id not in (c.seeker_id, c.owner_id):
        raise HTTPException(404, "Conversation not found")
    return c


def _conv_out(db: Session, c: Conversation, user: User) -> schemas.ConversationOut:
    last = db.scalar(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at.desc()).limit(1))
    unread = db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == c.id, Message.sender_id != user.id, Message.read_at.is_(None)))
    other = c.owner if user.id == c.seeker_id else c.seeker
    cover = c.listing.photos[0].thumb_key if c.listing.photos else None
    return schemas.ConversationOut(
        id=c.id, listing_id=c.listing_id, listing_title=c.listing.title, listing_cover_url=storage.public_url(cover),
        other_party=schemas.PublicUserOut.model_validate(other), role="seeker" if user.id == c.seeker_id else "owner",
        last_message=last.body[:120] if last else None, last_message_at=c.last_message_at, unread=unread or 0,
    )


def _msg_out(m: Message) -> schemas.MessageOut:
    return schemas.MessageOut(id=m.id, sender_id=m.sender_id, body=m.body, created_at=m.created_at, read_at=m.read_at)


@router.get("/conversations", response_model=list[schemas.ConversationOut])
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).where(or_(Conversation.seeker_id == user.id, Conversation.owner_id == user.id)).order_by(Conversation.last_message_at.desc()).limit(200))
    return [_conv_out(db, c, user) for c in rows]


@router.get("/conversations/unread-count")
def unread_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(
        select(func.count()).select_from(Message).join(Conversation, Conversation.id == Message.conversation_id).where(
            or_(Conversation.seeker_id == user.id, Conversation.owner_id == user.id), Message.sender_id != user.id, Message.read_at.is_(None)
        )
    )
    return {"unread": n or 0}


@router.post("/conversations", response_model=schemas.ConversationOut, status_code=201)
def start_conversation(body: schemas.ConversationStartIn, request: Request, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    limit(request, "conv-start", 30, 3600, key=user.id)
    listing = db.get(Listing, body.listing_id)
    if listing is None or listing.status != "active":
        raise HTTPException(404, "Listing not found")
    if listing.owner_id == user.id:
        raise HTTPException(422, "This is your own listing")
    c = db.scalar(select(Conversation).where(Conversation.listing_id == listing.id, Conversation.seeker_id == user.id))
    if c is None:
        c = Conversation(listing_id=listing.id, seeker_id=user.id, owner_id=listing.owner_id)
        db.add(c)
        db.flush()
    msg = schemas.MessageIn(body=body.message)
    db.add(Message(conversation_id=c.id, sender_id=user.id, body=msg.body))
    c.last_message_at = now()
    db.commit()
    db.refresh(c)
    return _conv_out(db, c, user)


@router.get("/conversations/{conv_id}", response_model=schemas.ConversationOut)
def get_conversation(conv_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _conv_out(db, _conv_for(db, conv_id, user), user)


@router.get("/conversations/{conv_id}/messages", response_model=list[schemas.MessageOut])
def messages(conv_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _conv_for(db, conv_id, user)
    stmt = select(Message).where(Message.conversation_id == c.id)
    rows = list(db.scalars(stmt.order_by(Message.created_at.desc()).limit(200)))
    db.execute(update(Message).where(Message.conversation_id == c.id, Message.sender_id != user.id, Message.read_at.is_(None)).values(read_at=now()))
    db.commit()
    return [_msg_out(m) for m in reversed(rows)]


@router.post("/conversations/{conv_id}/messages", response_model=schemas.MessageOut, status_code=201)
def send_message(conv_id: str, body: schemas.MessageIn, request: Request, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    limit(request, "msg", 60, 60, key=user.id)
    c = _conv_for(db, conv_id, user)
    m = Message(conversation_id=c.id, sender_id=user.id, body=body.body)
    db.add(m)
    c.last_message_at = now()
    db.commit()
    return _msg_out(m)


# ---------------------------------------------------------------- visits
def _visit_out(db: Session, v: VisitRequest, user: User) -> schemas.VisitOut:
    role = "owner" if user.id == v.owner_id else "seeker"
    show_addr = v.status == "accepted"
    return schemas.VisitOut(
        id=v.id, listing_id=v.listing_id, listing_title=v.listing.title, seeker=schemas.PublicUserOut.model_validate(v.seeker),
        proposed_at=v.proposed_at, note=v.note, status=v.status, role=role, address_line=v.listing.address_line if show_addr else None, created_at=v.created_at,
    )


@router.get("/visits", response_model=list[schemas.VisitOut])
def visits(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(VisitRequest).where(or_(VisitRequest.seeker_id == user.id, VisitRequest.owner_id == user.id)).order_by(VisitRequest.created_at.desc()).limit(200))
    return [_visit_out(db, v, user) for v in rows]


@router.post("/visits", response_model=schemas.VisitOut, status_code=201)
def request_visit(body: schemas.VisitIn, request: Request, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    limit(request, "visit", 20, 3600, key=user.id)
    listing = db.get(Listing, body.listing_id)
    if listing is None or listing.status != "active":
        raise HTTPException(404, "Listing not found")
    if listing.owner_id == user.id:
        raise HTTPException(422, "This is your own listing")
    when = aware(body.proposed_at)
    if when < now() + timedelta(minutes=30) or when > now() + timedelta(days=60):
        raise HTTPException(422, "Pick a time between 30 minutes and 60 days from now")
    pending = db.scalar(select(func.count()).select_from(VisitRequest).where(VisitRequest.listing_id == listing.id, VisitRequest.seeker_id == user.id, VisitRequest.status == "pending"))
    if pending:
        raise HTTPException(409, "You already have a pending visit request for this listing")
    v = VisitRequest(listing_id=listing.id, seeker_id=user.id, owner_id=listing.owner_id, proposed_at=when, note=body.note)
    db.add(v)
    db.commit()
    db.refresh(v)
    return _visit_out(db, v, user)


@router.patch("/visits/{visit_id}", response_model=schemas.VisitOut)
def update_visit(visit_id: str, body: schemas.VisitUpdateIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = db.get(VisitRequest, visit_id)
    if v is None or user.id not in (v.seeker_id, v.owner_id):
        raise HTTPException(404, "Visit not found")
    if body.status in ("accepted", "declined") and user.id != v.owner_id:
        raise HTTPException(403, "Only the owner can accept or decline")
    if body.status == "cancelled" and user.id != v.seeker_id:
        raise HTTPException(403, "Only the requester can cancel")
    if v.status != "pending" and not (body.status == "cancelled" and v.status == "accepted"):
        raise HTTPException(409, f"This visit is already {v.status}")
    v.status = body.status
    audit(db, request, user, f"visit.{body.status}", "visit", v.id)
    db.commit()
    return _visit_out(db, v, user)


# ---------------------------------------------------------------- reports
AUTO_HIDE_THRESHOLD = 3


@router.post("/reports", status_code=201)
def report(body: schemas.ReportIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(request, "report", 20, 3600, key=user.id)
    dup = db.scalar(select(Report).where(Report.reporter_id == user.id, Report.target_id == body.target_id, Report.status == "open"))
    if dup:
        return {"id": dup.id, "status": "open"}
    r = Report(reporter_id=user.id, **body.model_dump())
    db.add(r)
    db.flush()
    if body.target_type == "listing":
        n = db.scalar(select(func.count(func.distinct(Report.reporter_id))).where(and_(Report.target_id == body.target_id, Report.status == "open")))
        listing = db.get(Listing, body.target_id)
        if listing and n >= AUTO_HIDE_THRESHOLD and listing.status == "active":
            listing.status = "pending_review"  # auto-hide pending moderation
            audit(db, request, None, "listing.auto_hidden", "listing", listing.id, reports=n)
    db.commit()
    return {"id": r.id, "status": r.status}
