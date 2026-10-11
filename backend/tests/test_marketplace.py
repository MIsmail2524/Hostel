from datetime import datetime, timedelta, timezone

from PIL import Image

from app import storage
from tests.conftest import LISTING, create_active_listing, jpeg_bytes, make_user


def test_owner_permissions(client):
    seeker = make_user(client)
    unverified_owner = make_user(client, owner=True, verified=False)
    assert client.post("/api/v1/listings", json=LISTING, headers=seeker["h"]).status_code == 403
    assert client.post("/api/v1/listings", json=LISTING, headers=unverified_owner["h"]).status_code == 403
    assert client.post("/api/v1/listings", json=LISTING).status_code == 401


def test_listing_validation_and_mass_assignment(client):
    owner = make_user(client, owner=True)
    assert client.post("/api/v1/listings", json={**LISTING, "status": "active"}, headers=owner["h"]).status_code == 422
    assert client.post("/api/v1/listings", json={**LISTING, "available_beds": 9}, headers=owner["h"]).status_code == 422
    assert client.post("/api/v1/listings", json={**LISTING, "amenities": ["hot_tub"]}, headers=owner["h"]).status_code == 422
    assert client.post("/api/v1/listings", json={**LISTING, "rent_monthly": -5}, headers=owner["h"]).status_code == 422


def test_html_is_stripped(client):
    owner = make_user(client, owner=True)
    r = client.post("/api/v1/listings", json={**LISTING, "title": "<script>alert(1)</script>Nice bed space", "description": "<img src=x onerror=alert(1)>Hello"}, headers=owner["h"])
    assert r.status_code == 201
    assert "<" not in r.json()["title"] and "<" not in r.json()["description"]


def test_lifecycle_moderation_and_privacy(client):
    owner, admin, stranger = make_user(client, owner=True), make_user(client, admin=True), make_user(client)
    r = client.post("/api/v1/listings", json=LISTING, headers=owner["h"])
    lid = r.json()["id"]
    assert r.json()["status"] == "draft"
    # Draft is invisible to others & search
    assert client.get(f"/api/v1/listings/{lid}", headers=stranger["h"]).status_code == 404
    # Submit requires photo
    assert client.post(f"/api/v1/listings/{lid}/status", json={"action": "submit"}, headers=owner["h"]).status_code == 422
    client.post(f"/api/v1/listings/{lid}/photos", files=[("files", ("a.jpg", jpeg_bytes(), "image/jpeg"))], headers=owner["h"])
    assert client.post(f"/api/v1/listings/{lid}/status", json={"action": "submit"}, headers=owner["h"]).json()["status"] == "pending_review"
    # Non-admin cannot moderate; reject requires reason
    assert client.post(f"/api/v1/admin/listings/{lid}/moderate", json={"action": "approve"}, headers=owner["h"]).status_code == 403
    assert client.post(f"/api/v1/admin/listings/{lid}/moderate", json={"action": "reject"}, headers=admin["h"]).status_code == 422
    assert client.post(f"/api/v1/admin/listings/{lid}/moderate", json={"action": "approve"}, headers=admin["h"]).status_code == 200
    pub = client.get(f"/api/v1/listings/{lid}").json()
    # exact address/coords never public; approx coords rounded
    assert pub["address_line"] is None and pub["lat"] is None
    assert pub["approx_lat"] == 31.47 and pub["approx_lng"] == 74.27
    own = client.get(f"/api/v1/listings/{lid}", headers=owner["h"]).json()
    assert own["address_line"] == LISTING["address_line"]
    # Editing a live listing sends it back to review (anti bait-and-switch)
    r = client.put(f"/api/v1/listings/{lid}", json={**LISTING, "rent_monthly": 9000}, headers=owner["h"])
    assert r.json()["status"] == "pending_review"


def test_idor_other_owner_cannot_touch(client):
    a, b, admin = make_user(client, owner=True), make_user(client, owner=True), make_user(client, admin=True)
    lid = create_active_listing(client, a, admin)
    assert client.put(f"/api/v1/listings/{lid}", json=LISTING, headers=b["h"]).status_code == 404
    assert client.delete(f"/api/v1/listings/{lid}", headers=b["h"]).status_code == 404
    assert client.post(f"/api/v1/listings/{lid}/photos", files=[("files", ("a.jpg", jpeg_bytes(), "image/jpeg"))], headers=b["h"]).status_code == 404
    assert client.post(f"/api/v1/listings/{lid}/tour", json={}, headers=b["h"]).status_code == 404


def test_upload_sanitisation(client):
    owner = make_user(client, owner=True)
    lid = client.post("/api/v1/listings", json=LISTING, headers=owner["h"]).json()["id"]
    # EXIF/GPS stripped by re-encoding
    r = client.post(f"/api/v1/listings/{lid}/photos", files=[("files", ("gps.jpg", jpeg_bytes(exif_gps=True), "image/jpeg"))], headers=owner["h"])
    assert r.status_code == 201
    key = "public/" + r.json()[0]["url"].removeprefix("/media/")
    assert not Image.open(storage.path_for(key)).getexif()
    # Fake image (script disguised as jpg) rejected by magic-byte sniffing
    r = client.post(f"/api/v1/listings/{lid}/photos", files=[("files", ("x.jpg", b"<?php system($_GET['c']); ?>", "image/jpeg"))], headers=owner["h"])
    assert r.status_code == 415
    # Truncated/corrupt JPEG rejected
    r = client.post(f"/api/v1/listings/{lid}/photos", files=[("files", ("c.jpg", jpeg_bytes()[:200], "image/jpeg"))], headers=owner["h"])
    assert r.status_code == 422
    # Path traversal in storage keys blocked
    import pytest

    with pytest.raises(ValueError):
        storage.path_for("../../etc/passwd")


def test_search_filters(client):
    owner, admin = make_user(client, owner=True), make_user(client, admin=True)
    a = create_active_listing(client, owner, admin, title="Girls hostel seat Gulberg", gender_policy="female", rent_monthly=20000, city="Lahore", area="Gulberg", amenities=["wifi", "ac"], meals_included=True)
    b = create_active_listing(client, owner, admin, title="Private room Clifton Karachi", space_type="private_room", gender_policy="any", rent_monthly=40000, city="Karachi", area="Clifton")
    ids = lambda r: {x["id"] for x in r.json()["items"]}  # noqa: E731
    assert a in ids(client.get("/api/v1/listings", params={"city": "lahore"}))
    assert b not in ids(client.get("/api/v1/listings", params={"city": "Lahore"}))
    r = client.get("/api/v1/listings", params={"gender": "female"})
    assert a in ids(r) and b in ids(r)  # "any" included for female seekers
    assert b not in ids(client.get("/api/v1/listings", params={"max_rent": 30000}))
    assert a in ids(client.get("/api/v1/listings", params=[("amenities", "wifi"), ("amenities", "ac")]))
    assert a not in ids(client.get("/api/v1/listings", params={"space_type": "private_room"}))
    assert a in ids(client.get("/api/v1/listings", params={"q": "gulberg"}))
    assert a in ids(client.get("/api/v1/listings", params={"meals": True}))
    prices = [x["rent_monthly"] for x in client.get("/api/v1/listings", params={"sort": "price_asc", "page_size": 50}).json()["items"]]
    assert prices == sorted(prices)


def test_chat_visits_reviews_reports(client):
    owner, admin, seeker, other = make_user(client, owner=True), make_user(client, admin=True), make_user(client), make_user(client)
    lid = create_active_listing(client, owner, admin)
    # chat
    r = client.post("/api/v1/conversations", json={"listing_id": lid, "message": "Is it available?"}, headers=seeker["h"])
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.get(f"/api/v1/conversations/{cid}/messages", headers=other["h"]).status_code == 404  # not a participant
    assert client.post(f"/api/v1/conversations/{cid}/messages", json={"body": "Yes!"}, headers=owner["h"]).status_code == 201
    assert client.get("/api/v1/conversations/unread-count", headers=seeker["h"]).json()["unread"] == 1
    msgs = client.get(f"/api/v1/conversations/{cid}/messages", headers=seeker["h"]).json()
    assert [m["body"] for m in msgs] == ["Is it available?", "Yes!"]
    assert client.get("/api/v1/conversations/unread-count", headers=seeker["h"]).json()["unread"] == 0
    # review before visit not allowed
    assert client.post(f"/api/v1/listings/{lid}/reviews", json={"rating": 5}, headers=seeker["h"]).status_code == 403
    # visit
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert client.post("/api/v1/visits", json={"listing_id": lid, "proposed_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}, headers=seeker["h"]).status_code == 422
    v = client.post("/api/v1/visits", json={"listing_id": lid, "proposed_at": when, "note": "after class"}, headers=seeker["h"]).json()
    assert v["address_line"] is None
    assert client.patch(f"/api/v1/visits/{v['id']}", json={"status": "accepted"}, headers=seeker["h"]).status_code == 403
    v = client.patch(f"/api/v1/visits/{v['id']}", json={"status": "accepted"}, headers=owner["h"]).json()
    assert v["status"] == "accepted" and v["address_line"] == LISTING["address_line"]
    assert client.get(f"/api/v1/listings/{lid}", headers=seeker["h"]).json()["address_line"] == LISTING["address_line"]
    assert client.get(f"/api/v1/listings/{lid}", headers=other["h"]).json()["address_line"] is None
    # review after accepted visit; one per user; owner reply
    r = client.post(f"/api/v1/listings/{lid}/reviews", json={"rating": 4, "body": "Clean & quiet"}, headers=seeker["h"])
    assert r.status_code == 201
    assert client.post(f"/api/v1/listings/{lid}/reviews", json={"rating": 1}, headers=seeker["h"]).status_code == 409
    assert client.post(f"/api/v1/listings/{lid}/reviews/{r.json()['id']}/reply", json={"reply": "Thanks!"}, headers=owner["h"]).status_code == 200
    card = client.get(f"/api/v1/listings/{lid}").json()
    assert card["rating"] == 4.0 and card["review_count"] == 1
    # favourites
    assert client.post(f"/api/v1/listings/{lid}/favorite", headers=seeker["h"]).status_code == 204
    assert [x["id"] for x in client.get("/api/v1/me/favorites", headers=seeker["h"]).json()] == [lid]
    # reports: 3 distinct reporters auto-hide
    for u in (seeker, other, make_user(client)):
        assert client.post("/api/v1/reports", json={"target_type": "listing", "target_id": lid, "reason": "scam"}, headers=u["h"]).status_code == 201
    assert client.get(f"/api/v1/listings/{lid}").status_code == 404
    assert len(client.get("/api/v1/admin/reports", headers=admin["h"]).json()) >= 3
    assert any(a["action"] == "listing.auto_hidden" for a in client.get("/api/v1/admin/audit", headers=admin["h"]).json())


def test_suspension_revokes_access(client):
    admin, user = make_user(client, admin=True), make_user(client)
    assert client.patch(f"/api/v1/admin/users/{user['id']}", json={"is_suspended": True}, headers=admin["h"]).status_code == 200
    assert client.get("/api/v1/me", headers=user["h"]).status_code == 401
    assert client.post("/api/v1/auth/login", json={"identifier": user["email"], "password": "Str0ng!Pass"}).status_code == 403
