from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


UUID = String(36)
TS = DateTime(timezone=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(80))
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    bio: Mapped[str | None] = mapped_column(String(500))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(TS)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[str] = mapped_column(UUID, index=True)
    expires_at: Mapped[datetime] = mapped_column(TS)
    revoked_at: Mapped[datetime | None] = mapped_column(TS)
    replaced_by: Mapped[str | None] = mapped_column(UUID)
    user_agent: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # verify_contact | reset_password
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(TS)
    consumed_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    space_type: Mapped[str] = mapped_column(String(20), index=True)
    gender_policy: Mapped[str] = mapped_column(String(10), index=True)
    property_name: Mapped[str | None] = mapped_column(String(100))
    rent_monthly: Mapped[int] = mapped_column(Integer, index=True)
    deposit: Mapped[int] = mapped_column(Integer, default=0)
    bills_included: Mapped[bool] = mapped_column(Boolean, default=False)
    meals_included: Mapped[bool] = mapped_column(Boolean, default=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    available_beds: Mapped[int] = mapped_column(Integer, default=1)
    amenities: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(60), index=True)
    area: Mapped[str] = mapped_column(String(80), index=True)
    address_line: Mapped[str] = mapped_column(String(200))  # private
    lat: Mapped[float | None] = mapped_column(Float)  # private (exact)
    lng: Mapped[float | None] = mapped_column(Float)
    available_from: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(300))
    views: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(lazy="joined")
    photos: Mapped[list[ListingPhoto]] = relationship(
        order_by="ListingPhoto.position", cascade="all, delete-orphan", lazy="selectin"
    )


class ListingPhoto(Base):
    __tablename__ = "listing_photos"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(200))
    thumb_key: Mapped[str] = mapped_column(String(200))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Tour(Base):
    __tablename__ = "tours"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), unique=True, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    engine: Mapped[str] = mapped_column(String(20), default="room360")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|queued|processing|ready|failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    rooms: Mapped[list[TourRoom]] = relationship(
        order_by="TourRoom.position", cascade="all, delete-orphan", lazy="selectin"
    )


class TourRoom(Base):
    __tablename__ = "tour_rooms"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    tour_id: Mapped[str] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0)
    input_kind: Mapped[str | None] = mapped_column(String(10))  # photos | video
    width_m: Mapped[float] = mapped_column(Float, default=3.7)
    length_m: Mapped[float] = mapped_column(Float, default=4.3)
    height_m: Mapped[float] = mapped_column(Float, default=3.0)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|processing|ready|failed
    error_code: Mapped[str | None] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(String(300))
    hints: Mapped[list] = mapped_column(JSON, default=list)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    pano_key: Mapped[str | None] = mapped_column(String(200))
    pano_small_key: Mapped[str | None] = mapped_column(String(200))
    preview_key: Mapped[str | None] = mapped_column(String(200))
    yaw_offset_deg: Mapped[float] = mapped_column(Float, default=0.0)

    inputs: Mapped[list[TourInput]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="TourInput.seq")


class TourInput(Base):
    __tablename__ = "tour_inputs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(ForeignKey("tour_rooms.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # image | video
    seq: Mapped[int] = mapped_column(Integer, default=0)  # capture order: first photo = initial view
    key: Mapped[str] = mapped_column(String(200))  # private storage key
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(30))
    ref_id: Mapped[str] = mapped_column(UUID, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[datetime | None] = mapped_column(TS)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("listing_id", "seeker_id"),)
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    seeker_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_message_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    listing: Mapped[Listing] = relationship(lazy="joined")
    seeker: Mapped[User] = relationship(foreign_keys=[seeker_id], lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys=[owner_id], lazy="joined")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class VisitRequest(Base):
    __tablename__ = "visit_requests"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    seeker_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    proposed_at: Mapped[datetime] = mapped_column(TS)
    note: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|accepted|declined|cancelled
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    listing: Mapped[Listing] = relationship(lazy="joined")
    seeker: Mapped[User] = relationship(foreign_keys=[seeker_id], lazy="joined")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("listing_id", "author_id"),)
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(String(1000), default="")
    owner_reply: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)

    author: Mapped[User] = relationship(lazy="joined")


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # listing | user | message
    target_id: Mapped[str] = mapped_column(UUID, index=True)
    reason: Mapped[str] = mapped_column(String(30))
    details: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | resolved | dismissed
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, default=_uuid)
    actor_id: Mapped[str | None] = mapped_column(UUID, index=True)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(20))
    target_id: Mapped[str | None] = mapped_column(UUID)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
