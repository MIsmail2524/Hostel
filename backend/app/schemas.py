"""Request/response DTOs. Inputs use extra="forbid" so clients can never set server-owned fields."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

SpaceType = Literal["bed_space", "shared_room", "private_room", "portion", "hostel_seat"]
GenderPolicy = Literal["male", "female", "family", "any"]
AMENITIES = {
    "wifi", "ac", "ups", "generator", "solar", "geyser", "attached_bath", "kitchen", "laundry",
    "meals", "parking", "cctv", "security_guard", "furnished", "study_table", "cupboard",
    "fridge", "lift", "prayer_area", "gym", "water_filter", "gas", "balcony",
}
_TAGS = re.compile(r"<[^>]*>")


def _clean(s: str) -> str:
    """Strip HTML tags & control chars (defence in depth — clients also escape on render)."""
    s = _TAGS.sub("", s)
    return "".join(ch for ch in s if ch in "\n\t" or ord(ch) >= 32).strip()


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------- auth
def normalise_phone(v: str) -> str:
    digits = re.sub(r"[^\d+]", "", v)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("03") and len(digits) == 11:  # PK local mobile format
        digits = "+92" + digits[1:]
    if not re.fullmatch(r"\+[1-9]\d{7,14}", digits):
        raise ValueError("Enter a valid phone number, e.g. 03001234567 or +923001234567")
    return digits


class RegisterIn(In):
    full_name: str = Field(min_length=2, max_length=80)
    email: EmailStr | None = None
    phone: str | None = None
    password: str = Field(min_length=8, max_length=128)
    is_owner: bool = False

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 2:
            raise ValueError("Enter your name")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return v.lower() if v else None

    @model_validator(mode="after")
    def _one_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Provide a phone number or an email")
        return self


class LoginIn(In):
    identifier: str = Field(min_length=3, max_length=254, description="email or phone")
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(In):
    refresh_token: str = Field(min_length=20, max_length=200)


class OtpVerifyIn(In):
    code: str = Field(pattern=r"^\d{6}$")


class PasswordResetRequestIn(In):
    identifier: str = Field(min_length=3, max_length=254)


class PasswordResetIn(In):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(In):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountIn(In):
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    email: str | None
    phone: str | None
    is_owner: bool
    is_admin: bool
    contact_verified: bool
    is_verified_owner: bool
    gender: str | None
    bio: str | None
    created_at: datetime


class PublicUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    is_verified_owner: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdateIn(In):
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    gender: Literal["male", "female", "other"] | None = None
    bio: str | None = Field(default=None, max_length=500)
    is_owner: bool | None = None

    @field_validator("full_name", "bio")
    @classmethod
    def _c(cls, v):
        return _clean(v) if v else v


# ---------------------------------------------------------------- listings
class ListingIn(In):
    title: str = Field(min_length=8, max_length=100)
    description: str = Field(default="", max_length=4000)
    space_type: SpaceType
    gender_policy: GenderPolicy
    property_name: str | None = Field(default=None, max_length=100)
    rent_monthly: int = Field(ge=1000, le=1_000_000)
    deposit: int = Field(default=0, ge=0, le=5_000_000)
    bills_included: bool = False
    meals_included: bool = False
    capacity: int = Field(default=1, ge=1, le=500)
    available_beds: int = Field(default=1, ge=0, le=500)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    rules: str = Field(default="", max_length=2000)
    city: str = Field(min_length=2, max_length=60)
    area: str = Field(min_length=2, max_length=80)
    address_line: str = Field(min_length=5, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    available_from: date | None = None

    @field_validator("title", "description", "property_name", "rules", "city", "area", "address_line")
    @classmethod
    def _c(cls, v):
        return _clean(v) if isinstance(v, str) else v

    @field_validator("amenities")
    @classmethod
    def _amen(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if a not in AMENITIES]
        if bad:
            raise ValueError(f"Unknown amenities: {', '.join(bad[:5])}")
        return sorted(set(v))

    @model_validator(mode="after")
    def _beds(self):
        if self.available_beds > self.capacity:
            raise ValueError("Available beds cannot exceed capacity")
        return self


class ListingUpdateIn(ListingIn):
    pass


class PhotoOut(BaseModel):
    id: str
    url: str
    thumb_url: str
    width: int
    height: int


class TourBrief(BaseModel):
    id: str
    status: str
    progress: float
    rooms: int
    preview_url: str | None


class ListingCard(BaseModel):
    id: str
    title: str
    space_type: str
    gender_policy: str
    rent_monthly: int
    bills_included: bool
    meals_included: bool
    available_beds: int
    city: str
    area: str
    cover_url: str | None
    has_tour: bool
    owner_verified: bool
    rating: float | None
    review_count: int
    status: str
    created_at: datetime


class ListingOut(ListingCard):
    description: str
    property_name: str | None
    deposit: int
    capacity: int
    amenities: list[str]
    rules: str
    approx_lat: float | None
    approx_lng: float | None
    available_from: date | None
    photos: list[PhotoOut]
    tour: TourBrief | None
    owner: PublicUserOut
    is_favorite: bool = False
    views: int = 0
    rejection_reason: str | None = None
    # Only populated for the owner, admins, or a seeker with an accepted visit
    address_line: str | None = None
    lat: float | None = None
    lng: float | None = None


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------- tours
class TourCreateIn(In):
    engine: Literal["room360", "gsplat"] = "room360"


class RoomIn(In):
    name: str = Field(min_length=1, max_length=40)
    width_m: float = Field(default=3.7, ge=1.5, le=20)
    length_m: float = Field(default=4.3, ge=1.5, le=20)
    height_m: float = Field(default=3.0, ge=2.2, le=6)

    @field_validator("name")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class RoomUpdateIn(In):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    width_m: float | None = Field(default=None, ge=1.5, le=20)
    length_m: float | None = Field(default=None, ge=1.5, le=20)
    height_m: float | None = Field(default=None, ge=2.2, le=6)
    yaw_offset_deg: float | None = Field(default=None, ge=-180, le=180)


class RoomOut(BaseModel):
    id: str
    name: str
    position: int
    input_kind: str | None
    input_count: int
    width_m: float
    length_m: float
    height_m: float
    status: str
    error_code: str | None
    error_message: str | None
    hints: list[str]
    quality: dict
    preview_url: str | None
    yaw_offset_deg: float


class TourOut(BaseModel):
    id: str
    listing_id: str
    engine: str
    status: str
    progress: float
    message: str | None
    rooms: list[RoomOut]
    updated_at: datetime


# ---------------------------------------------------------------- chat / visits / reviews / reports
class ConversationStartIn(In):
    listing_id: str = Field(min_length=36, max_length=36)
    message: str = Field(min_length=1, max_length=2000)


class MessageIn(In):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def _c(cls, v):
        v = _clean(v)
        if not v:
            raise ValueError("Message is empty")
        return v


class MessageOut(BaseModel):
    id: str
    sender_id: str
    body: str
    created_at: datetime
    read_at: datetime | None


class ConversationOut(BaseModel):
    id: str
    listing_id: str
    listing_title: str
    listing_cover_url: str | None
    other_party: PublicUserOut
    role: Literal["seeker", "owner"]
    last_message: str | None
    last_message_at: datetime
    unread: int


class VisitIn(In):
    listing_id: str = Field(min_length=36, max_length=36)
    proposed_at: datetime
    note: str = Field(default="", max_length=500)

    @field_validator("note")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class VisitUpdateIn(In):
    status: Literal["accepted", "declined", "cancelled"]


class VisitOut(BaseModel):
    id: str
    listing_id: str
    listing_title: str
    seeker: PublicUserOut
    proposed_at: datetime
    note: str
    status: str
    role: Literal["seeker", "owner"]
    address_line: str | None = None
    created_at: datetime


class ReviewIn(In):
    rating: int = Field(ge=1, le=5)
    body: str = Field(default="", max_length=1000)

    @field_validator("body")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class ReviewReplyIn(In):
    reply: str = Field(min_length=1, max_length=1000)

    @field_validator("reply")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class ReviewOut(BaseModel):
    id: str
    rating: int
    body: str
    owner_reply: str | None
    author_name: str
    created_at: datetime


class ReportIn(In):
    target_type: Literal["listing", "user", "message"]
    target_id: str = Field(min_length=36, max_length=36)
    reason: Literal["scam", "fake_photos", "wrong_info", "harassment", "inappropriate", "already_rented", "other"]
    details: str = Field(default="", max_length=1000)

    @field_validator("details")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class ModerateIn(In):
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=300)


class ReportResolveIn(In):
    status: Literal["resolved", "dismissed"]
    note: str = Field(default="", max_length=500)


class AdminUserUpdateIn(In):
    is_verified_owner: bool | None = None
    is_suspended: bool | None = None
