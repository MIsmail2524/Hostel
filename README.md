# Kamra — rooms, beds & spaces, in 3D

A marketplace that connects **hostel owners, flat owners and people renting out a single room or bed** with **students and working professionals**, replacing WhatsApp/Facebook-group hunting with structured search, private chat, visit scheduling and trust & safety — plus a **photo/video → interactive 3D walkthrough** generated automatically from what owners capture on an ordinary phone.

```
Hostel/
├── docs/                    Product & engineering documents (start here)
│   ├── 01-product-requirements.md
│   ├── 02-system-architecture.md
│   ├── 03-3d-reconstruction-pipeline.md
│   ├── 04-security.md
│   ├── 05-ux-hci-guidelines.md
│   ├── 06-api.md
│   └── 07-testing-and-results.md
├── backend/                 FastAPI API + 3D reconstruction engine + three.js viewer
│   ├── app/
│   │   ├── routers/         auth, me, listings, tours, social (chat/visits/reports), admin
│   │   ├── recon/           stitch.py, frames.py, engines.py, worker.py, synthetic.py
│   │   └── viewer/          self-hosted 3D walkthrough viewer (served at /viewer/)
│   ├── tests/               pytest: security, marketplace, photos/video → 3D end-to-end
│   ├── seed.py              demo data incl. real reconstructed tours
│   └── Dockerfile
├── mobile/                  React Native (Expo SDK 57, Expo Router) app — iOS, Android, Web
│   └── src/app/             screens (file-based routes)
└── docker-compose.yml       Postgres + Redis + API + worker
```

## Quick start (local development)

Prerequisites: Python 3.11+ (3.13 used), Node 20+ (22 used), Docker (for Postgres) — or skip Docker and use the SQLite default.

```bash
# 1. Database (optional — omit KAMRA_DATABASE_URL to use SQLite)
docker run -d --name kamra-db -e POSTGRES_USER=kamra -e POSTGRES_PASSWORD=kamra_dev_pw -e POSTGRES_DB=kamra -p 127.0.0.1:5434:5432 postgres:16-alpine
```

```bash
# 2. Backend (run from the backend folder so .env is picked up)
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp -n .env.example .env
# edit .env and set a real KAMRA_JWT_SECRET (required for production; local dev can use the default)

# If you want to use the bundled Postgres service from step 1, keep the default .env values.
# If you want SQLite instead, remove/override KAMRA_DATABASE_URL before starting the app.
python seed.py --reset          # demo users, listings and REAL 3D tours (~2 min)
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

API docs: http://localhost:8090/docs · Viewer: http://localhost:8090/viewer/?tour=<tour-id>

```bash
# 3. Mobile app
cd mobile
npm install
npx expo start            # press a (Android), i (iOS) or w (web); or scan the QR with Expo Go / a dev build
```

On a physical phone set the API address to your computer's LAN IP:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.20:8090 npx expo start
```

…and add that origin to `KAMRA_CORS_ORIGINS` / `KAMRA_VIEWER_FRAME_ANCESTORS` for the web build. Android emulator uses `http://10.0.2.2:8090` automatically.

Static web build (what was used for testing here): `npx expo export --platform web` then `python3 scripts/serve_web.py 8082`.

### Demo accounts (local seed only)

Password for all: `Demo@12345` (override with `KAMRA_DEMO_PASSWORD` before seeding).

| Email | Role |
|---|---|
| admin@kamra.test | Admin (moderation queue in Profile) |
| rauf@kamra.test | Verified hostel owner (2 listings with/without 3D) |
| sana@kamra.test | Flat owner (female flat with a 3D tour from **video**) |
| ayesha@kamra.test, bilal@kamra.test | Seekers |

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q          # ~5 min, includes real 3D reconstruction from photos & video
cd mobile && npx tsc --noEmit
```

## Production

`docker compose up --build` runs Postgres, Redis, the API and a separate reconstruction worker. See `docs/04-security.md §7` for the production checklist (secrets, TLS proxy, S3 storage, SMS gateway, migrations, monitoring) and `docs/03` for adding the GPU Gaussian-Splatting engine.
