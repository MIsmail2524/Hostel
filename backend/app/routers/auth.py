from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas
from ..config import get_settings
from ..db import get_db
from ..deps import audit, current_user
from ..models import OtpCode, User
from ..ratelimit import limit
from ..security import (
    aware,
    create_access_token,
    hash_otp,
    hash_password,
    issue_refresh_token,
    new_otp,
    now,
    otp_matches,
    password_problems,
    revoke_all_sessions,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("kamra.auth")


def _tokens(db: Session, user: User, request: Request) -> schemas.TokenOut:
    raw, _ = issue_refresh_token(db, user, request.headers.get("user-agent"))
    db.commit()
    return schemas.TokenOut(
        access_token=create_access_token(user),
        refresh_token=raw,
        expires_in=get_settings().access_token_minutes * 60,
        user=schemas.UserOut.model_validate(user),
    )


def _find(db: Session, identifier: str) -> User | None:
    ident = identifier.strip().lower()
    phone = None
    try:
        phone = schemas.normalise_phone(ident)
    except ValueError:
        pass
    conds = [User.email == ident]
    if phone:
        conds.append(User.phone == phone)
    return db.scalar(select(User).where(or_(*conds)))


def _send_otp(db: Session, user: User, purpose: str) -> dict:
    """Create an OTP and deliver it via the configured provider (console in dev)."""
    recent = db.scalar(
        select(OtpCode).where(OtpCode.user_id == user.id, OtpCode.purpose == purpose).order_by(OtpCode.created_at.desc())
    )
    if recent and aware(recent.created_at) > now() - timedelta(seconds=45):
        raise HTTPException(429, "Please wait a moment before requesting another code", headers={"Retry-After": "45"})
    db.execute(update(OtpCode).where(OtpCode.user_id == user.id, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None)).values(consumed_at=now()))
    code = new_otp()
    db.add(OtpCode(user_id=user.id, purpose=purpose, code_hash=hash_otp(code, user.id), expires_at=now() + timedelta(minutes=get_settings().otp_ttl_minutes)))
    db.commit()
    # Production: plug in an SMS gateway (e.g. Twilio / local aggregator) or email provider here.
    log.info("OTP for %s (%s): %s", user.phone or user.email, purpose, code if get_settings().expose_dev_codes else "******")
    out = {"sent_to": _mask(user.phone or user.email or "")}
    if get_settings().expose_dev_codes:
        out["dev_code"] = code
    return out


def _mask(contact: str) -> str:
    if "@" in contact:
        name, dom = contact.split("@", 1)
        return name[:2] + "***@" + dom
    return contact[:4] + "*****" + contact[-3:]


def _check_otp(db: Session, user: User, purpose: str, code: str) -> None:
    otp = db.scalar(
        select(OtpCode).where(OtpCode.user_id == user.id, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None)).order_by(OtpCode.created_at.desc())
    )
    if otp is None or aware(otp.expires_at) < now() or otp.attempts >= 5:
        raise HTTPException(400, "The code has expired. Request a new one.")
    otp.attempts += 1
    if not otp_matches(code, user.id, otp.code_hash):
        db.commit()
        raise HTTPException(400, "Incorrect code")
    otp.consumed_at = now()


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
def register(body: schemas.RegisterIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "register", 10, 3600)
    probs = password_problems(body.password, context=[body.full_name.split()[0] if body.full_name else "", body.email or "", body.phone or ""])
    if probs:
        raise HTTPException(422, probs[0])
    conds = ([User.email == body.email] if body.email else []) + ([User.phone == body.phone] if body.phone else [])
    exists = db.scalar(select(User).where(or_(*conds)))
    if exists:
        raise HTTPException(409, "An account with this phone or email already exists. Try logging in.")
    user = User(full_name=body.full_name, email=body.email, phone=body.phone, password_hash=hash_password(body.password), is_owner=body.is_owner)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # concurrent registration with the same contact
        db.rollback()
        raise HTTPException(409, "An account with this phone or email already exists. Try logging in.")
    audit(db, request, user, "user.register", "user", user.id)
    return _tokens(db, user, request)


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "login-ip", 20, 300)
    limit(request, "login-id", 10, 300, key=body.identifier.lower())
    s = get_settings()
    user = _find(db, body.identifier)
    generic = HTTPException(401, "Incorrect phone/email or password")
    if user and user.locked_until and aware(user.locked_until) > now():
        raise HTTPException(423, "Too many failed attempts. Try again in a few minutes or reset your password.")
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= s.max_login_failures:
                user.locked_until = now() + timedelta(minutes=s.lockout_minutes)
                user.failed_logins = 0
                audit(db, request, user, "user.locked", "user", user.id)
            db.commit()
        raise generic
    if user.is_suspended:
        raise HTTPException(403, "This account is suspended. Contact support.")
    user.failed_logins = 0
    user.locked_until = None
    audit(db, request, user, "user.login", "user", user.id)
    return _tokens(db, user, request)


@router.post("/refresh", response_model=schemas.TokenOut)
def refresh(body: schemas.RefreshIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "refresh", 60, 300)
    res = rotate_refresh_token(db, body.refresh_token, request.headers.get("user-agent"))
    if res is None:
        raise HTTPException(401, "Session expired. Please log in again.")
    user, raw = res
    return schemas.TokenOut(access_token=create_access_token(user), refresh_token=raw, expires_in=get_settings().access_token_minutes * 60, user=schemas.UserOut.model_validate(user))


@router.post("/logout", status_code=204)
def logout(body: schemas.RefreshIn, db: Session = Depends(get_db)):
    revoke_refresh_token(db, body.refresh_token)


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    revoke_all_sessions(db, user)
    audit(db, request, user, "user.logout_all", "user", user.id)
    db.commit()


@router.post("/otp/request")
def otp_request(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(request, "otp", 5, 3600, key=user.id)
    if user.contact_verified:
        return {"already_verified": True}
    return _send_otp(db, user, "verify_contact")


@router.post("/otp/verify", response_model=schemas.UserOut)
def otp_verify(body: schemas.OtpVerifyIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(request, "otp-verify", 10, 900, key=user.id)
    _check_otp(db, user, "verify_contact", body.code)
    user.contact_verified = True
    audit(db, request, user, "user.verified", "user", user.id)
    db.commit()
    return user


@router.post("/password/forgot")
def forgot(body: schemas.PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "forgot", 5, 3600)
    user = _find(db, body.identifier)
    resp: dict = {"message": "If an account exists, a code has been sent."}  # no account enumeration
    if user and not user.is_suspended:
        try:
            out = _send_otp(db, user, "reset_password")
            if "dev_code" in out:
                resp["dev_code"] = out["dev_code"]
        except HTTPException:
            pass
    return resp


@router.post("/password/reset", status_code=204)
def reset(body: schemas.PasswordResetIn, request: Request, db: Session = Depends(get_db)):
    limit(request, "reset", 10, 3600)
    user = _find(db, body.identifier)
    if user is None:
        raise HTTPException(400, "The code has expired. Request a new one.")
    _check_otp(db, user, "reset_password", body.code)
    probs = password_problems(body.new_password, context=[user.email or "", user.phone or ""])
    if probs:
        raise HTTPException(422, probs[0])
    user.password_hash = hash_password(body.new_password)
    user.locked_until = None
    user.contact_verified = True  # proved control of the contact
    revoke_all_sessions(db, user)
    audit(db, request, user, "user.password_reset", "user", user.id)
    db.commit()


@router.post("/password/change", status_code=204)
def change_password(body: schemas.ChangePasswordIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit(request, "pw-change", 10, 3600, key=user.id)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    probs = password_problems(body.new_password, context=[user.email or "", user.phone or ""])
    if probs:
        raise HTTPException(422, probs[0])
    user.password_hash = hash_password(body.new_password)
    revoke_all_sessions(db, user)
    audit(db, request, user, "user.password_change", "user", user.id)
    db.commit()
