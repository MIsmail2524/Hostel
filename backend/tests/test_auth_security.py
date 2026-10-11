from app import ratelimit
from tests.conftest import PW, make_user


def test_register_validation(client):
    r = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": "weak@example.com", "password": "password"})
    assert r.status_code == 422  # common password
    r = client.post("/api/v1/auth/register", json={"full_name": "A B", "password": PW})
    assert r.status_code == 422 and "phone number or an email" in r.json()["detail"]
    r = client.post("/api/v1/auth/register", json={"full_name": "A B", "phone": "12", "password": PW})
    assert r.status_code == 422


def test_register_normalises_pk_phone_and_rejects_duplicates(client):
    r = client.post("/api/v1/auth/register", json={"full_name": "Ali Raza", "phone": "0300-1234567", "password": PW})
    assert r.status_code == 201 and r.json()["user"]["phone"] == "+923001234567"
    r = client.post("/api/v1/auth/register", json={"full_name": "Ali Raza", "phone": "+923001234567", "password": PW})
    assert r.status_code == 409


def test_mass_assignment_rejected(client):
    r = client.post("/api/v1/auth/register", json={"full_name": "Eve", "email": "eve@example.com", "password": PW, "is_admin": True})
    assert r.status_code == 422  # extra fields forbidden


def test_login_generic_error_and_lockout(client):
    u = make_user(client)
    r = client.post("/api/v1/auth/login", json={"identifier": "nobody@example.com", "password": "x"})
    assert r.status_code == 401
    r2 = client.post("/api/v1/auth/login", json={"identifier": u["email"], "password": "wrong"})
    assert r2.status_code == 401 and r.json()["detail"] == r2.json()["detail"]  # no user enumeration
    for _ in range(4):
        client.post("/api/v1/auth/login", json={"identifier": u["email"], "password": "wrong"})
    r = client.post("/api/v1/auth/login", json={"identifier": u["email"], "password": PW})
    assert r.status_code == 423  # locked even with the right password


def test_otp_verification_flow(client):
    u = make_user(client, verified=False)
    r = client.post("/api/v1/auth/otp/request", headers=u["h"])
    assert r.status_code == 200
    code = r.json()["dev_code"]
    assert client.post("/api/v1/auth/otp/verify", json={"code": "000000" if code != "000000" else "111111"}, headers=u["h"]).status_code == 400
    r = client.post("/api/v1/auth/otp/verify", json={"code": code}, headers=u["h"])
    assert r.status_code == 200 and r.json()["contact_verified"] is True
    # resend throttle
    u2 = make_user(client, verified=False)
    assert client.post("/api/v1/auth/otp/request", headers=u2["h"]).status_code == 200
    assert client.post("/api/v1/auth/otp/request", headers=u2["h"]).status_code == 429


def test_refresh_rotation_and_reuse_detection(client):
    u = make_user(client)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": u["refresh"]})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    # replaying the old token = theft signal → whole family revoked
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": u["refresh"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh}).status_code == 401


def test_tampered_and_wrong_type_tokens_rejected(client):
    u = make_user(client)
    bad = u["token"][:-4] + ("AAAA" if not u["token"].endswith("AAAA") else "BBBB")
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer " + u["refresh"]}).status_code == 401
    import jwt

    forged = jwt.encode({"sub": u["id"], "typ": "access", "ver": 0, "iss": "kamra-api", "exp": 9999999999}, "guessed-secret", algorithm="HS256")
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    none_alg = jwt.encode({"sub": u["id"], "typ": "access", "ver": 0, "iss": "kamra-api", "exp": 9999999999}, None, algorithm="none")
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {none_alg}"}).status_code == 401


def test_password_change_revokes_sessions(client):
    u = make_user(client)
    r = client.post("/api/v1/auth/password/change", json={"current_password": PW, "new_password": "N3w!Passw0rd"}, headers=u["h"])
    assert r.status_code == 204
    assert client.get("/api/v1/me", headers=u["h"]).status_code == 401  # old access token invalid
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": u["refresh"]}).status_code == 401


def test_password_reset_no_enumeration(client):
    r1 = client.post("/api/v1/auth/password/forgot", json={"identifier": "ghost@example.com"})
    u = make_user(client)
    r2 = client.post("/api/v1/auth/password/forgot", json={"identifier": u["email"]})
    assert r1.status_code == r2.status_code == 200 and r1.json()["message"] == r2.json()["message"]
    code = r2.json()["dev_code"]
    r = client.post("/api/v1/auth/password/reset", json={"identifier": u["email"], "code": code, "new_password": "Br4nd!NewPass"})
    assert r.status_code == 204
    assert client.post("/api/v1/auth/login", json={"identifier": u["email"], "password": "Br4nd!NewPass"}).status_code == 200


def test_rate_limit_login(client):
    ratelimit.reset()
    h = {"x-test-ratelimit": "on"}
    codes = [client.post("/api/v1/auth/login", json={"identifier": "rl@example.com", "password": "x"}, headers=h).status_code for _ in range(12)]
    assert 429 in codes
    ratelimit.reset()


def test_security_headers(client):
    r = client.get("/api/v1/listings")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"
    v = client.get("/viewer/index.html")
    assert "script-src 'self'" in v.headers["content-security-policy"] and "frame-ancestors" in v.headers["content-security-policy"]


def test_body_size_limit(client):
    r = client.post("/api/v1/auth/login", content=b"x", headers={"content-length": str(10 * 1024 * 1024 * 1024), "content-type": "application/json"})
    assert r.status_code == 413


def test_production_config_guard():
    import pytest

    from app.config import Settings

    s = Settings(env="production", jwt_secret="dev-insecure-abc", database_url="sqlite:///x.db", public_base_url="http://x")
    with pytest.raises(RuntimeError):
        s.validate_for_production()


def test_account_deletion_requires_password_and_cascades(client):
    from tests.conftest import LISTING

    u = make_user(client, owner=True)
    lid = client.post("/api/v1/listings", json=LISTING, headers=u["h"]).json()["id"]
    assert client.post("/api/v1/me/delete", json={"password": "wrong"}, headers=u["h"]).status_code == 400
    assert client.post("/api/v1/me/delete", json={"password": PW}, headers=u["h"]).status_code == 204
    assert client.get("/api/v1/me", headers=u["h"]).status_code == 401
    assert client.post("/api/v1/auth/login", json={"identifier": u["email"], "password": PW}).status_code == 401
    admin = make_user(client, admin=True)
    assert client.get(f"/api/v1/listings/{lid}", headers=admin["h"]).status_code == 404
