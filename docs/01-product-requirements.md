# Kamra — Product Requirements Document (PRD)

> Working title: **Kamra** (Urdu/Hindi for "room"). Rename freely; the brand string lives in one place per app (`mobile/src/theme.ts`, `backend/app/config.py`).

| Item | Value |
|---|---|
| Version | 1.0 (MVP) |
| Date | 2026-10-08 |
| Primary market | Pakistan (Lahore, Karachi, Islamabad/Rawalpindi first), extendable to South Asia |
| Platforms | Android + iOS (React Native / Expo), Web (same codebase via react-native-web) |
| Currency | PKR (configurable) |

---

## 1. Problem

Students and young professionals who move to a new city need a **bed, a room, or a portion** — not a whole house. Today this market runs on **WhatsApp groups, Facebook groups and word of mouth**:

* Listings are unstructured text + a few blurry photos; no filters (price, gender policy, area, amenities).
* No trust layer: fake listings, bait-and-switch photos, advance-payment scams, harassment risk for female seekers when phone numbers are posted publicly.
* Owners of hostels and flats re-post the same ad daily; vacancies for a *single bed* or *single room* are invisible.
* Seekers waste days on physical visits to places that look nothing like the photos.

Existing property portals (Zameen, Graana, OLX) are built around **whole units** (house/flat/plot) and do not model *bed space*, *shared room*, *gender policy*, *meals*, *bills included*, etc.

## 2. Vision

> "Find your exact bed, room or space — and walk through it in 3D before you visit."

Kamra is a two-sided marketplace for **space-level** rentals (bed in a shared room, private room in a flat, hostel seat, portion) with:

1. Structured, searchable listings at **room/bed granularity**.
2. **Photo/video → interactive 3D walkthrough** generated automatically from what the owner captures on their phone.
3. **Private in-app chat & visit requests** (no public phone numbers).
4. Trust & safety: verified owners, reviews from real tenants, reporting & moderation.

## 3. Personas

| Persona | Description | Top goals | Pain today |
|---|---|---|---|
| **Ayesha – student seeker** | 19, moving from Multan to Lahore for university | Safe girls' hostel near campus under PKR 25k, with meals | Has to share her number in FB groups, gets spam calls; photos are fake |
| **Bilal – working professional** | 26, new job in Karachi | Private room in a shared flat, close to office, Wi-Fi + backup power | Brokers charge a month's rent; can't judge room size from photos |
| **Mr. Rauf – hostel owner** | Runs a 40-bed boys' hostel | Keep beds full; stop re-posting daily; filter serious tenants | Vacancy of 3 beds is invisible; endless "price?" messages |
| **Sana – flat owner/tenant** | Rents out 1 spare room in her flat | Find a compatible female flatmate safely | Doesn't want her address and number public |
| **Admin / Trust & Safety** | Kamra staff | Remove scams, verify owners, resolve reports | — |

## 4. Scope

### 4.1 MVP (this repository)

**Seeker**
* Register / log in (phone or email + password), OTP verification (pluggable SMS provider).
* Explore: search by text, city, area; filter by space type, price range, gender policy, amenities, "has 3D tour", "verified owner"; sort by newest / price.
* Listing detail: photo gallery, price breakdown (rent, deposit, bills), amenities, house rules, approximate location (exact address hidden until the owner accepts a visit), owner card with verification badge & rating.
* **3D Tour**: interactive walkthrough (drag/swipe to look, joystick/WASD to walk, tap hotspots to move between rooms, "dollhouse" overview).
* Save (favourite) listings.
* Message owner (in-app chat), request a visit with preferred date/time.
* Review a listing after a visit was accepted.
* Report a listing or user.

**Owner**
* Create / edit / pause listings with a step-by-step wizard and inline validation.
* Upload photos (gallery) and **capture media for 3D** (photos taken by rotating in place, or a slow 360° video) per room.
* See 3D processing status (queued → processing → ready / failed with actionable reason) and preview the tour.
* Inbox: conversations and visit requests (accept / decline / propose time).

**Admin**
* Moderate listings (pending → approved / rejected with reason), resolve reports, verify owners, suspend users.
* Audit log of privileged actions.

### 4.2 Post-MVP roadmap

| Phase | Feature |
|---|---|
| v1.1 | Push notifications (FCM/APNs via Expo Notifications), Urdu localisation + RTL, map view |
| v1.2 | **GPU reconstruction engine** (Gaussian Splatting) for photoreal free-walk 3D from video (see doc 03) |
| v1.3 | Online booking with token payment (JazzCash / Easypaisa / Raast / cards) held in escrow until move-in |
| v1.4 | Roommate matching (habits, schedule, budget), digital rental agreement, rent reminders |
| v2 | Owner SaaS: bed-level occupancy management, rent collection, expense ledger, multi-hostel dashboard |

### 4.3 Out of scope (MVP)

Payments, whole-house sale/rent, brokers' bulk import, in-app voice/video calls.

## 5. Functional requirements (MVP)

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Users register with phone (E.164, PK default) or email + strong password; roles: `seeker`, `owner` (a user can be both), `admin` | Must |
| FR-02 | OTP verification of phone/email; unverified users can browse but not message/list | Must |
| FR-03 | Owners create listings with: title, description, space type (`bed_space`, `shared_room`, `private_room`, `portion`, `hostel_seat`), gender policy (`male`, `female`, `family`, `any`), rent, deposit, bills included flag, meals flag, capacity, available beds, amenities, rules, city, area, address, lat/lng, available-from | Must |
| FR-04 | New/edited listings go to `pending_review`; admin approves → `active` | Must |
| FR-05 | Search with filters + pagination; only `active` listings visible publicly | Must |
| FR-06 | Exact address + coordinates are **never** returned publicly; public location is area + coordinates rounded to ~1 km | Must |
| FR-07 | Owners upload up to 20 photos per listing; images are validated, re-encoded, EXIF/GPS stripped, resized | Must |
| FR-08 | Owners create a 3D tour with 1..N rooms; each room accepts 4–40 photos or one video (≤ 120 s, ≤ 200 MB) | Must |
| FR-09 | Server reconstructs each room into a 360° textured room model and composes a navigable multi-room tour; status & progress visible | Must |
| FR-10 | Interactive viewer: look around, walk, room hotspots, dollhouse view, fullscreen, works in app (WebView) and browser | Must |
| FR-11 | In-app conversation per (listing, seeker); text messages; owner phone never exposed by default | Must |
| FR-12 | Visit requests with status `pending/accepted/declined/cancelled`; accepting reveals exact address to that seeker | Must |
| FR-13 | Reviews (1–5 + text) only by seekers with an accepted visit; one per listing; owner can reply | Should |
| FR-14 | Favourites | Should |
| FR-15 | Reports with reason; admin queue; auto-hide listing at ≥ 3 distinct open reports | Should |
| FR-16 | Admin: approve/reject listings, verify owners, suspend users; all actions audit-logged | Must |

## 6. Non-functional requirements

| Category | Target |
|---|---|
| Performance | p95 API latency < 300 ms for reads (excluding media); search page < 1 s on 4G |
| 3D processing | ≤ 3 min per room on 4 vCPU (CPU engine); asynchronous with progress |
| Availability | 99.5 % (MVP), stateless API → horizontally scalable |
| Security | OWASP ASVS L2, OWASP MASVS-L1, OWASP API Top-10 mitigations (see doc 04) |
| Privacy | PDPB-style data minimisation; exact address & phone shared only with consent; EXIF stripped |
| Accessibility | WCAG 2.2 AA contrast, ≥ 44×44 pt touch targets, screen-reader labels, dynamic type |
| Usability | First listing published in < 10 min; first search result < 30 s from install |
| Low-end devices | Works on Android 8+, 2 GB RAM; viewer degrades gracefully (lower texture resolution) |
| Data usage | Thumbnails ≤ 60 KB; panoramas served at 4K and 2K variants |

## 7. Business model (sellability)

1. **Freemium for owners**: 1 active listing free; paid plans for hostels (unlimited listings, featured placement, analytics, 3D tours).
2. **3D tour credits**: first tour free, then per-tour fee (CPU engine cheap; GPU "photoreal" engine premium).
3. **Featured / boosted listings** in search.
4. **Verified badge** (owner KYC) — trust is the moat versus WhatsApp groups.
5. v1.3+: **booking commission** (token-money escrow) and **owner SaaS** subscription.

Unit-economics note: the CPU engine costs ≈ cents per room (a few CPU-minutes); GPU splatting ≈ 10–20 GPU-minutes per room — price accordingly.

## 8. Success metrics (KPIs)

* Seeker: search → contact conversion, time-to-first-contact, % listings viewed with 3D tour.
* Owner: time-to-first-listing, vacancy fill time, response rate & time.
* Trust: reports per 1k listings, % verified owners, scam incidents.
* Engagement: D7 / D30 retention, messages per conversation.

## 9. Assumptions (made autonomously — please confirm)

1. Market = Pakistan, currency PKR, phone numbers default to +92.
2. Cross-platform with **React Native (Expo)** rather than two native apps — one codebase, faster to market, web build for free.
3. **Python/FastAPI** backend because the 3D pipeline is Python (OpenCV/NumPy) — one language server-side.
4. The development machine has **no GPU**, so the shipped reconstruction engine is the CPU **"Room-360"** engine (photos/video → stitched 360° panorama → textured 3D room shell → walkable multi-room tour). The GPU **Gaussian-Splatting** engine is designed behind the same interface and documented (doc 03) for when a GPU worker is available.
5. SMS/OTP provider, push notifications, maps API key and object storage (S3/R2) are pluggable with local/dev implementations.
