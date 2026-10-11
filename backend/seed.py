"""Seed demo data: users, listings with photos, and REAL reconstructed 3D tours (from synthetic captures).

    python seed.py            # idempotent: skips if demo users already exist
    python seed.py --reset    # wipes the database & storage first (dev only)

Demo passwords are read from env KAMRA_DEMO_PASSWORD (default for local dev only).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent))
from app import storage  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import Listing, ListingPhoto, Tour, TourInput, TourRoom, User  # noqa: E402
from app.recon.synthetic import Room, RoomRenderer, capture_photos, capture_video  # noqa: E402
from app.recon.worker import process_tour  # noqa: E402
from app.security import hash_password  # noqa: E402

PW = os.environ.get("KAMRA_DEMO_PASSWORD", "Demo@12345")


def user(db, name, email, phone, owner=False, admin=False, verified_owner=False):
    u = User(full_name=name, email=email, phone=phone, password_hash=hash_password(PW), is_owner=owner, is_admin=admin, contact_verified=True, is_verified_owner=verified_owner)
    db.add(u)
    db.flush()
    return u


def add_photos(db, listing: Listing, room: Room, yaws=(0, 90, 200)):
    rr = RoomRenderer(room)
    for i, yaw in enumerate(yaws):
        img = rr.perspective(yaw, -8, 75, 1280, 960)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        key = storage.new_key("public", f"listings/{listing.id}", ".jpg")
        storage.write_bytes(key, buf.tobytes())
        small = cv2.resize(img, (480, 360), interpolation=cv2.INTER_AREA)
        tkey = key.replace(".jpg", "_t.jpg")
        storage.write_bytes(tkey, cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 78])[1].tobytes())
        db.add(ListingPhoto(listing_id=listing.id, key=key, thumb_key=tkey, width=1280, height=960, position=i))


def add_tour(db, listing: Listing, rooms: list[tuple[str, Room, str]]):
    tour = Tour(listing_id=listing.id, owner_id=listing.owner_id, status="queued")
    db.add(tour)
    db.flush()
    tmp = Path(tempfile.mkdtemp())
    for pos, (name, room, mode) in enumerate(rooms):
        tr = TourRoom(tour_id=tour.id, name=name, position=pos, width_m=room.width, length_m=room.length, height_m=room.height, input_kind=mode)
        db.add(tr)
        db.flush()
        if mode == "video":
            vp = capture_video(room, tmp / f"{tr.id}.mp4")
            key = storage.new_key("private", f"tours/{tour.id}", ".mp4")
            storage.write_file(key, vp)
            db.add(TourInput(room_id=tr.id, kind="video", key=key))
        else:
            for seq, p in enumerate(capture_photos(room, tmp / tr.id)):
                key = storage.new_key("private", f"tours/{tour.id}", ".jpg")
                storage.write_file(key, p)
                db.add(TourInput(room_id=tr.id, kind="image", key=key, seq=seq))
    db.commit()
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"  reconstructing {len(rooms)} room(s) for '{listing.title}' …", flush=True)
    process_tour(db, tour.id)
    db.refresh(tour)
    print(f"  → tour {tour.status}: {tour.message}")


def main(reset: bool):
    s = get_settings()
    if reset:
        if s.is_production:
            raise SystemExit("refusing to reset in production")
        Base.metadata.drop_all(engine)
        shutil.rmtree(s.storage_dir, ignore_errors=True)
    (s.storage_dir / "public").mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    if db.query(User).filter(User.email == "admin@kamra.test").first():
        print("Demo data already present (use --reset to recreate).")
        return
    admin = user(db, "Kamra Admin", "admin@kamra.test", "+923000000001", admin=True)
    rauf = user(db, "Abdul Rauf", "rauf@kamra.test", "+923001111111", owner=True, verified_owner=True)
    sana = user(db, "Sana Malik", "sana@kamra.test", "+923002222222", owner=True)
    user(db, "Ayesha Khan", "ayesha@kamra.test", "+923003333333")
    user(db, "Bilal Ahmed", "bilal@kamra.test", "+923004444444")
    db.commit()

    today = date.today()
    specs = [
        dict(owner=rauf, title="Bed in 3-seater room · Al-Noor Boys Hostel", space_type="bed_space", gender_policy="male", property_name="Al-Noor Boys Hostel",
             rent_monthly=14000, deposit=10000, bills_included=True, meals_included=True, capacity=3, available_beds=1,
             amenities=["wifi", "ups", "meals", "laundry", "cctv", "study_table", "water_filter"], city="Lahore", area="Johar Town",
             address_line="House 12, Block R1, Johar Town", lat=31.4697, lng=74.2728,
             description="Clean, quiet hostel 5 minutes from UCP and UMT. Three meals a day, weekly laundry, 24/7 security and backup power.",
             rules="No smoking. Gate closes at 11 pm. Guests in the lobby only.", room=Room(seed=3), tour=[("Room", Room(seed=3), "photos"), ("Common area", Room(seed=7, width=5.0, length=4.0, wall_color=(200, 235, 245)), "photos")]),
        dict(owner=sana, title="Private room in shared female flat · DHA Phase 6", space_type="private_room", gender_policy="female", property_name=None,
             rent_monthly=38000, deposit=38000, bills_included=False, meals_included=False, capacity=1, available_beds=1,
             amenities=["wifi", "ac", "attached_bath", "kitchen", "furnished", "geyser", "security_guard"], city="Karachi", area="DHA Phase 6",
             address_line="Flat 4B, Bukhari Commercial, DHA Phase 6", lat=24.7955, lng=67.0606,
             description="Bright furnished room with attached bath in a 3-bed flat shared with two working women. Walking distance to Bukhari Commercial.",
             rules="Females only. Share kitchen cleaning. No overnight guests.", room=Room(seed=11, wall_color=(225, 215, 240)), tour=[("Bedroom", Room(seed=11, wall_color=(225, 215, 240)), "video")]),
        dict(owner=rauf, title="Shared room for 2 near NUST · G-11", space_type="shared_room", gender_policy="male", property_name="Capital Residency",
             rent_monthly=18000, deposit=15000, bills_included=True, meals_included=False, capacity=2, available_beds=2,
             amenities=["wifi", "ups", "kitchen", "parking", "cupboard"], city="Islamabad", area="G-11 Markaz",
             address_line="Street 4, G-11/2", lat=33.6684, lng=72.9986,
             description="Spacious room for two with separate cupboards and study tables. Shared kitchen, 10 minutes to NUST H-12.",
             rules="Students and working men only.", room=Room(seed=21, width=4.5, length=4.8), tour=None),
        dict(owner=sana, title="Girls hostel seat with meals · Gulberg III", space_type="hostel_seat", gender_policy="female", property_name="Hira Girls Hostel",
             rent_monthly=22000, deposit=10000, bills_included=True, meals_included=True, capacity=4, available_beds=2,
             amenities=["wifi", "meals", "ups", "cctv", "security_guard", "laundry", "prayer_area"], city="Lahore", area="Gulberg III",
             address_line="45-C, Main Boulevard, Gulberg III", lat=31.5120, lng=74.3440,
             description="Safe girls' hostel with female warden, biometric entry and CCTV. Close to Kinnaird and LCWU.",
             rules="Females only. Curfew 9 pm. Parents' contact required.", room=Room(seed=31, wall_color=(215, 230, 215)), tour=None),
        dict(owner=rauf, title="Upper portion room · Bahria Town Phase 4", space_type="portion", gender_policy="family", property_name=None,
             rent_monthly=30000, deposit=60000, bills_included=False, meals_included=False, capacity=3, available_beds=3,
             amenities=["parking", "gas", "geyser", "balcony", "kitchen"], city="Rawalpindi", area="Bahria Town Phase 4",
             address_line="House 220, Street 9, Phase 4", lat=33.5300, lng=73.1270,
             description="Independent upper-portion room with balcony and small kitchen. Separate entrance, ideal for a small family.",
             rules="Family only.", room=Room(seed=41, width=4.2, length=5.0), tour=None),
    ]
    for i, spec in enumerate(specs):
        room = spec.pop("room")
        tour = spec.pop("tour")
        owner = spec.pop("owner")
        listing = Listing(owner_id=owner.id, status="active", available_from=today + timedelta(days=3 * i), **spec)
        db.add(listing)
        db.flush()
        add_photos(db, listing, room)
        db.commit()
        print(f"listing: {listing.title}")
        if tour:
            add_tour(db, listing, tour)
    pending = Listing(owner_id=sana.id, status="pending_review", title="Bed space in Model Town hostel", space_type="bed_space", gender_policy="female",
                      rent_monthly=12000, city="Lahore", area="Model Town", address_line="Block G, Model Town", amenities=["wifi"])
    db.add(pending)
    db.flush()
    add_photos(db, pending, Room(seed=51), yaws=(30,))
    db.commit()
    print(f"\nDemo accounts (password from KAMRA_DEMO_PASSWORD, default for dev): admin@kamra.test, rauf@kamra.test (owner), sana@kamra.test (owner), ayesha@kamra.test, bilal@kamra.test")
    db.close()


if __name__ == "__main__":
    main("--reset" in sys.argv)
