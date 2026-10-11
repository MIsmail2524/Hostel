"""End-to-end: owner uploads phone photos / a video through the API → worker reconstructs →
public manifest + panoramas → viewer can load them. Uses synthetic rooms with known geometry."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from app import storage
from app.recon.synthetic import Room, RoomRenderer, capture_photos, capture_video
from app.recon.worker import run_once
from tests.conftest import create_active_listing, make_user


def _drain():
    while run_once():
        pass


def _ncc_band(gt: np.ndarray, pano: np.ndarray) -> float:
    pano = cv2.resize(pano, (gt.shape[1], gt.shape[0]))
    H = gt.shape[0]
    band = slice(int(H * 0.35), int(H * 0.65))
    A = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY)[band].astype(np.float32)
    B = cv2.cvtColor(pano, cv2.COLOR_BGR2GRAY)[band].astype(np.float32)
    a = A - A.mean()
    best, best_s = -1.0, 0
    for s in range(0, A.shape[1], 4):  # heading search over the full 360°
        Bs = np.roll(B, s, axis=1)
        b = Bs - Bs.mean()
        v = float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
        if v > best:
            best, best_s = v, s
    return best


@pytest.fixture(scope="module")
def setup(client, tmp_path_factory):
    owner, admin, stranger = make_user(client, owner=True), make_user(client, admin=True), make_user(client)
    lid = create_active_listing(client, owner, admin)
    return owner, admin, stranger, lid, tmp_path_factory.mktemp("cap")


def test_photos_and_video_to_walkthrough(client, setup):
    owner, admin, stranger, lid, tmp = setup
    tour = client.post(f"/api/v1/listings/{lid}/tour", json={}, headers=owner["h"]).json()
    tid = tour["id"]
    assert client.get(f"/api/v1/tours/{tid}", headers=stranger["h"]).status_code == 403  # seekers can't open the builder
    # Room 1: photos
    room_a = Room(seed=5)
    r1 = client.post(f"/api/v1/tours/{tid}/rooms", json={"name": "Bedroom", "width_m": room_a.width, "length_m": room_a.length}, headers=owner["h"]).json()
    photos = capture_photos(room_a, Path(tmp) / "a")
    for i in range(0, len(photos), 6):
        files = [("files", (p.name, p.read_bytes(), "image/jpeg")) for p in photos[i : i + 6]]
        assert client.post(f"/api/v1/tours/{tid}/rooms/{r1['id']}/inputs", files=files, headers=owner["h"]).status_code == 201
    # Room 2: video
    room_b = Room(seed=9, width=4.5, length=4.0, wall_color=(210, 235, 220))
    r2 = client.post(f"/api/v1/tours/{tid}/rooms", json={"name": "Common area", "width_m": 4.5, "length_m": 4.0}, headers=owner["h"]).json()
    vid = capture_video(room_b, Path(tmp) / "b.mp4")
    r = client.post(f"/api/v1/tours/{tid}/rooms/{r2['id']}/inputs", files=[("files", ("b.mp4", vid.read_bytes(), "video/mp4"))], headers=owner["h"])
    assert r.status_code == 201 and r.json()["input_kind"] == "video"
    # Mixing photos into a video room is rejected
    r = client.post(f"/api/v1/tours/{tid}/rooms/{r2['id']}/inputs", files=[("files", (photos[0].name, photos[0].read_bytes(), "image/jpeg"))], headers=owner["h"])
    assert r.status_code == 422

    # Not public before processing
    assert client.get(f"/api/v1/tours/{tid}/manifest").status_code == 404
    t = client.post(f"/api/v1/tours/{tid}/process", headers=owner["h"]).json()
    assert t["status"] == "queued"
    assert client.post(f"/api/v1/tours/{tid}/rooms", json={"name": "X"}, headers=owner["h"]).status_code == 409  # locked while queued
    _drain()
    t = client.get(f"/api/v1/tours/{tid}", headers=owner["h"]).json()
    assert t["status"] == "ready", t
    rooms = {r["name"]: r for r in t["rooms"]}
    assert rooms["Bedroom"]["status"] == "ready" and rooms["Common area"]["status"] == "ready", t
    assert rooms["Bedroom"]["quality"]["horizontal_coverage"] >= 0.95
    assert rooms["Common area"]["quality"]["horizontal_coverage"] >= 0.9

    # Public manifest & media
    m = client.get(f"/api/v1/tours/{tid}/manifest").json()
    assert [r["name"] for r in m["rooms"]] == ["Bedroom", "Common area"] and len(m["links"]) == 1
    for room, gt_room, min_ncc in ((m["rooms"][0], room_a, 0.9), (m["rooms"][1], room_b, 0.75)):
        res = client.get(room["pano"])
        assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
        pano = cv2.imdecode(np.frombuffer(res.content, np.uint8), cv2.IMREAD_COLOR)
        assert pano.shape[1] == 2 * pano.shape[0]
        assert _ncc_band(RoomRenderer(gt_room).equirect(1024), pano) >= min_ncc
        assert client.get(room["pano_small"]).status_code == 200
    # Raw capture inputs are never web-accessible
    assert not any(p.startswith("/media/private") for r in m["rooms"] for p in (r["pano"], r["pano_small"]))
    assert client.get("/media/../private/x").status_code == 404
    # Listing card advertises the tour
    assert client.get(f"/api/v1/listings/{lid}").json()["has_tour"] is True
    # Viewer page is served
    v = client.get(f"/viewer/?tour={tid}")
    assert v.status_code == 200 and "viewer.js" in v.text


def test_preview_token_for_unpublished_tour(client, setup):
    owner, admin, stranger, _, tmp = setup
    r = client.post("/api/v1/listings", json={"title": "Draft room with a tour", "space_type": "private_room", "gender_policy": "any", "rent_monthly": 20000, "city": "Lahore", "area": "DHA", "address_line": "Street 1, Phase 5"}, headers=owner["h"])
    lid = r.json()["id"]
    tid = client.post(f"/api/v1/listings/{lid}/tour", json={}, headers=owner["h"]).json()["id"]
    room = client.post(f"/api/v1/tours/{tid}/rooms", json={"name": "Room"}, headers=owner["h"]).json()
    photos = capture_photos(Room(seed=12), Path(tmp) / "c", rows=((0, 12),))
    client.post(f"/api/v1/tours/{tid}/rooms/{room['id']}/inputs", files=[("files", (p.name, p.read_bytes(), "image/jpeg")) for p in photos], headers=owner["h"])
    client.post(f"/api/v1/tours/{tid}/process", headers=owner["h"])
    _drain()
    assert client.get(f"/api/v1/tours/{tid}/manifest").status_code == 404  # listing is a draft
    link = client.post(f"/api/v1/tours/{tid}/preview-link", headers=owner["h"]).json()["path"]
    token = link.split("t=")[1]
    assert client.get(f"/api/v1/tours/{tid}/manifest", params={"t": token}).status_code == 200
    assert client.get(f"/api/v1/tours/{tid}/manifest", params={"t": token[:-3] + "abc"}).status_code == 404
    assert client.post(f"/api/v1/tours/{tid}/preview-link", headers=stranger["h"]).status_code == 403


def test_bad_capture_fails_gracefully_with_hints(client, setup):
    owner, _, _, _, _ = setup
    lid = client.post("/api/v1/listings", json={"title": "Room with bad capture", "space_type": "private_room", "gender_policy": "any", "rent_monthly": 20000, "city": "Lahore", "area": "DHA", "address_line": "Street 1, Phase 5"}, headers=owner["h"]).json()["id"]
    tid = client.post(f"/api/v1/listings/{lid}/tour", json={}, headers=owner["h"]).json()["id"]
    room = client.post(f"/api/v1/tours/{tid}/rooms", json={"name": "Dark room"}, headers=owner["h"]).json()
    rng = np.random.default_rng(0)
    files = []
    for i in range(5):  # unrelated, featureless, dark frames
        img = np.full((600, 800, 3), int(rng.integers(5, 25)), np.uint8)
        files.append(("files", (f"{i}.jpg", cv2.imencode(".jpg", img)[1].tobytes(), "image/jpeg")))
    client.post(f"/api/v1/tours/{tid}/rooms/{room['id']}/inputs", files=files, headers=owner["h"])
    client.post(f"/api/v1/tours/{tid}/process", headers=owner["h"])
    _drain()
    t = client.get(f"/api/v1/tours/{tid}", headers=owner["h"]).json()
    assert t["status"] == "failed"
    r = t["rooms"][0]
    assert r["status"] == "failed" and r["error_message"] and r["hints"]


def test_gpu_engine_rejected_when_unavailable(client, setup):
    owner, _, _, _, _ = setup
    lid = client.post("/api/v1/listings", json={"title": "Room for GPU engine", "space_type": "private_room", "gender_policy": "any", "rent_monthly": 20000, "city": "Lahore", "area": "DHA", "address_line": "Street 1, Phase 5"}, headers=owner["h"]).json()["id"]
    r = client.post(f"/api/v1/listings/{lid}/tour", json={"engine": "gsplat"}, headers=owner["h"])
    assert r.status_code == 422


def test_storage_never_serves_private(client):
    key = storage.new_key("private", "tours/x", ".jpg")
    storage.write_bytes(key, b"secret")
    assert client.get("/media/" + key).status_code == 404
    assert client.get("/media/" + key.removeprefix("private/")).status_code == 404
