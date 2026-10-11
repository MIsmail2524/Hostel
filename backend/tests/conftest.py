import io
import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="kamra-test-"))
os.environ.update(
    KAMRA_ENV="test",
    KAMRA_DATABASE_URL=f"sqlite:///{_TMP / 'test.db'}",
    KAMRA_STORAGE_DIR=str(_TMP / "storage"),
    KAMRA_REDIS_URL="",
    KAMRA_JWT_SECRET="test-secret-" + "x" * 40,
    KAMRA_RUN_WORKER_IN_PROCESS="false",
    KAMRA_RECON_OUTPUT_WIDTH="2048",
)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

PW = "Str0ng!Pass"


@pytest.fixture(scope="session", autouse=True)
def _setup():
    (_TMP / "storage" / "public").mkdir(parents=True, exist_ok=True)
    init_db()
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


_n = [0]


def make_user(client, *, owner=False, admin=False, verified=True) -> dict:
    """Register via the API (exercises the real flow), then optionally verify / elevate in DB."""
    _n[0] += 1
    i = _n[0]
    r = client.post("/api/v1/auth/register", json={"full_name": f"User {i}", "email": f"u{i}@example.com", "password": PW, "is_owner": owner})
    assert r.status_code == 201, r.text
    data = r.json()
    with SessionLocal() as db:
        u = db.get(User, data["user"]["id"])
        u.contact_verified = verified
        u.is_admin = admin
        db.commit()
    return {"id": data["user"]["id"], "email": f"u{i}@example.com", "token": data["access_token"], "refresh": data["refresh_token"], "h": {"Authorization": f"Bearer {data['access_token']}"}}


def jpeg_bytes(w=800, h=600, color=(200, 120, 50), exif_gps=False) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x010F] = "SpyCam"  # Make
        exif[0x8825] = {1: "N", 2: (31.0, 28.0, 0.0), 3: "E", 4: (74.0, 16.0, 0.0)}  # GPS IFD
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


LISTING = {
    "title": "Bed in shared room near UET",
    "description": "Clean and quiet.",
    "space_type": "bed_space",
    "gender_policy": "male",
    "rent_monthly": 15000,
    "deposit": 5000,
    "capacity": 3,
    "available_beds": 1,
    "amenities": ["wifi", "ups"],
    "city": "Lahore",
    "area": "Johar Town",
    "address_line": "House 1, Street 2, Block R1",
    "lat": 31.469712,
    "lng": 74.272845,
}


def create_active_listing(client, owner, admin, **overrides) -> str:
    r = client.post("/api/v1/listings", json={**LISTING, **overrides}, headers=owner["h"])
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    r = client.post(f"/api/v1/listings/{lid}/photos", files=[("files", ("a.jpg", jpeg_bytes(), "image/jpeg"))], headers=owner["h"])
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/listings/{lid}/status", json={"action": "submit"}, headers=owner["h"])
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/admin/listings/{lid}/moderate", json={"action": "approve"}, headers=admin["h"])
    assert r.status_code == 200, r.text
    return lid
