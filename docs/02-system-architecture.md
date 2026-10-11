# Kamra — System Architecture

## 1. Overview

```
 ┌────────────────────────┐        HTTPS/JSON         ┌───────────────────────────────┐
 │ Mobile app (Expo RN)   │ ────────────────────────▶ │ API (FastAPI, stateless)      │
 │ iOS · Android · Web    │ ◀──────────────────────── │ /api/v1/*   OpenAPI at /docs   │
 │  └─ Tour viewer        │   WebView / iframe        │ /viewer/*   three.js viewer    │
 └────────────────────────┘ ────────────────────────▶ │ /media/*    public media       │
                                                      └──────┬──────────────┬─────────┘
                                                             │ SQL          │ enqueue (jobs table)
                                                      ┌──────▼─────┐  ┌─────▼──────────────────────┐
                                                      │ PostgreSQL │  │ Recon worker(s)            │
                                                      └────────────┘  │  Room-360 engine (CPU)     │
                                                      ┌────────────┐  │  Gaussian-Splat engine     │
                                                      │ Redis      │  │  (GPU, remote, optional)   │
                                                      │ rate-limit │  └─────┬──────────────────────┘
                                                      └────────────┘        │ read inputs / write outputs
                                                                     ┌──────▼──────────────────────┐
                                                                     │ Object storage              │
                                                                     │ local disk (dev) / S3 / R2  │
                                                                     │  public/  (photos, panos)   │
                                                                     │  private/ (raw 3D inputs)   │
                                                                     └─────────────────────────────┘
```

## 2. Technology choices

| Layer | Choice | Why |
|---|---|---|
| Mobile | **React Native + Expo SDK, TypeScript, Expo Router** | One codebase → Android, iOS, Web; OTA updates; huge talent pool in PK |
| Secure storage | `expo-secure-store` (Keychain / Keystore) | MASVS-STORAGE: tokens never in plain AsyncStorage on device |
| 3D viewer | **three.js** (self-hosted, no CDN) in a WebView/iframe | GPU-accelerated WebGL on every phone; same viewer for web & share links |
| API | **Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2** | Async-ready, typed validation (mass-assignment safe), auto OpenAPI; same language as the CV pipeline |
| DB | **PostgreSQL 16** (SQLite for tests) | Relational integrity for marketplace data; JSONB for amenities/manifests |
| Queue | DB-backed job table with row locking (`FOR UPDATE SKIP LOCKED`) | No extra infra for MVP; swap to Redis/Celery or SQS when > 1 worker pool |
| Cache / rate-limit | **Redis** (in-memory fallback) | Distributed fixed-window counters |
| CV | **OpenCV 4 (SIFT, detail stitching API), NumPy** | Mature, CPU-only, permissive license (Apache-2) |
| Passwords | **Argon2id** (`argon2-cffi`) | OWASP-recommended |
| Tokens | JWT (HS256) access 15 min + opaque rotating refresh tokens (hashed in DB, reuse detection) | Short-lived, revocable sessions |
| Deploy | Docker images, `docker-compose` for dev; any container platform (Fly.io, ECS, k8s) for prod | 12-factor config via env vars |

## 3. Backend module layout

```
backend/app
├── main.py          app factory, middleware (security headers, body-size limit, CORS, request-id), routers, static mounts
├── config.py        typed settings from env (.env) — secrets never in code
├── db.py            engine/session, create_all for dev (Alembic for prod migrations)
├── models.py        SQLAlchemy ORM models
├── schemas.py       Pydantic request/response DTOs (extra="forbid" → no mass assignment)
├── security.py      Argon2id, JWT, refresh-token rotation, OTP hashing
├── deps.py          current-user, role guards, object-ownership helpers
├── ratelimit.py     Redis fixed-window limiter (+ in-memory fallback)
├── storage.py       storage abstraction (local; S3-compatible drop-in)
├── media.py         image/video validation, re-encoding, EXIF strip, thumbnails
├── audit.py         audit log helper
├── routers/         auth, me, listings, photos, tours, chat, visits, reviews, favorites, reports, admin
├── recon/           3D reconstruction: frames.py, stitch.py, engines.py, worker.py
└── viewer/          static three.js tour viewer (index.html, viewer.js, three.module.min.js)
```

## 4. Data model (ER summary)

```
users ─┬─< listings ─┬─< listing_photos
       │             ├─< tours ─< tour_rooms ─< tour_inputs
       │             ├─< conversations ─< messages
       │             ├─< visit_requests
       │             ├─< reviews
       │             └─< favorites >─ users
       ├─< refresh_tokens
       ├─< otp_codes
       ├─< reports
       └─< audit_logs
jobs (kind, ref_id, status, attempts, run_after, locked_at)
```

Key rules:
* `listings.address_line`, `lat`, `lng` are **private**; public API returns `area`, `city` and coordinates rounded to 2 decimals (~1.1 km).
* `conversations` unique on `(listing_id, seeker_id)`.
* `reviews` unique on `(listing_id, author_id)`; only allowed when an accepted visit exists.
* All primary keys are random UUIDv4 (non-enumerable — mitigates IDOR probing).

## 5. Listing lifecycle

```
draft ──submit──▶ pending_review ──approve──▶ active ──pause──▶ paused
   ▲                    │                       │  ▲               │
   └──── edit ◀─reject──┘                       │  └────resume─────┘
                                                └──mark rented──▶ rented
```
Editing material fields of an `active` listing sends it back to `pending_review` (prevents bait-and-switch after approval).

## 6. 3D tour lifecycle

```
draft (rooms + uploads) ──process──▶ queued ──worker──▶ processing (progress %) ──▶ ready
                                                              └──────────────────▶ failed (reason + hints) ──retry──▶ queued
```
The worker processes rooms independently; the tour is `ready` when ≥ 1 room succeeded (failed rooms are reported individually).

## 7. Request flow examples

**Seeker opens a tour**: app → `GET /api/v1/listings/{id}` (has `tour.status=ready`) → WebView loads `/viewer/?tour={id}` → viewer fetches `GET /api/v1/tours/{id}/manifest` → loads panoramas from `/media/...`.

**Owner preview of an unpublished tour**: app → `POST /api/v1/tours/{id}/preview-link` (auth) → returns `/viewer/?tour={id}&t=<10-min signed token>`; manifest endpoint accepts the token instead of requiring an active listing.

## 8. Scaling & operations

* API is stateless → scale horizontally behind a load balancer; sessions are JWT + DB refresh tokens.
* Workers scale independently; CPU engine ≈ 1 room/min/vCPU-pair; GPU engine on autoscaled GPU pool (RunPod/Modal/AWS g5).
* Media served via CDN (CloudFront/Cloudflare) in prod; `storage.py` returns public URLs.
* Observability: structured JSON logs with request-id, `/healthz` liveness, `/readyz` readiness (DB check); add Sentry + Prometheus in prod.
* Backups: daily Postgres PITR; object storage versioning on `public/`.
* Migrations: Alembic (dev uses `create_all`).

## 9. Environments & configuration

All settings come from environment variables (see `backend/.env.example`). The app **refuses to start in production** with the default/dev JWT secret, `DEBUG`, or wildcard CORS.
