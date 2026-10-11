"""Password hashing, JWT access tokens, rotating refresh tokens and OTP codes."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .models import RefreshToken, User

_ph = PasswordHasher()  # Argon2id, library defaults follow RFC 9106 / OWASP guidance
_DUMMY_HASH = _ph.hash("timing-equaliser-" + secrets.token_hex(8))

COMMON_PASSWORDS = {
    "password", "password1", "12345678", "123456789", "1234567890", "qwerty123", "11111111",
    "iloveyou", "pakistan", "pakistan1", "pakistan123", "admin123", "welcome1", "abc12345",
    "qwertyuiop", "letmein1", "00000000", "asdfghjk", "password123", "lahore123", "karachi123",
}


def aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; normalise everything to aware UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def now() -> datetime:
    return datetime.now(timezone.utc)


def password_problems(pw: str, *, context: list[str] | None = None) -> list[str]:
    problems = []
    if len(pw) < 8:
        problems.append("Use at least 8 characters")
    if len(pw) > 128:
        problems.append("Use at most 128 characters")
    if pw.lower() in COMMON_PASSWORDS:
        problems.append("This password is too common")
    classes = sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if classes < 2:
        problems.append("Mix letters with numbers or symbols")
    for c in context or []:
        if c and len(c) >= 4 and c.lower() in pw.lower():
            problems.append("Password must not contain your name, email or phone")
            break
    return problems


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY_HASH, pw) and hashed is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ---------------------------------------------------------------- access tokens
def create_access_token(user: User) -> str:
    s = get_settings()
    t = now()
    payload = {
        "sub": user.id,
        "ver": user.token_version,
        "typ": "access",
        "iss": s.jwt_issuer,
        "iat": int(t.timestamp()),
        "exp": int((t + timedelta(minutes=s.access_token_minutes)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str, typ: str) -> dict | None:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=["HS256"], issuer=s.jwt_issuer, options={"require": ["exp", "sub", "typ"]})
    except jwt.PyJWTError:
        return None
    return data if data.get("typ") == typ else None


def create_scoped_token(sub: str, typ: str, minutes: int) -> str:
    """Short-lived capability token, e.g. owner preview of an unpublished tour."""
    s = get_settings()
    t = now()
    payload = {"sub": sub, "typ": typ, "iss": s.jwt_issuer, "iat": int(t.timestamp()), "exp": int((t + timedelta(minutes=minutes)).timestamp())}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


# ---------------------------------------------------------------- refresh tokens
def issue_refresh_token(db: Session, user: User, user_agent: str | None, family_id: str | None = None) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=_sha256(raw),
        family_id=family_id or str(uuid.uuid4()),
        expires_at=now() + timedelta(days=get_settings().refresh_token_days),
        user_agent=(user_agent or "")[:200],
    )
    db.add(rt)
    db.flush()
    return raw, rt


def rotate_refresh_token(db: Session, raw: str, user_agent: str | None) -> tuple[User, str] | None:
    """Rotate a refresh token. Reuse of an already-rotated token revokes the whole family (theft detection)."""
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _sha256(raw)))
    if rt is None:
        return None
    if rt.revoked_at is not None:
        db.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now()))
        db.commit()
        return None
    if aware(rt.expires_at) < now():
        return None
    user = db.get(User, rt.user_id)
    if user is None or user.is_suspended:
        return None
    new_raw, new_rt = issue_refresh_token(db, user, user_agent, family_id=rt.family_id)
    rt.revoked_at = now()
    rt.replaced_by = new_rt.id
    db.commit()
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _sha256(raw)))
    if rt and rt.revoked_at is None:
        db.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now()))
        db.commit()


def revoke_all_sessions(db: Session, user: User) -> None:
    user.token_version += 1  # invalidates outstanding access tokens
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now()))


# ---------------------------------------------------------------- OTP
def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str, user_id: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def otp_matches(code: str, user_id: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code, user_id), code_hash)
