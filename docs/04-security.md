# Kamra — Security Design & Controls

Standards followed: **OWASP ASVS 4.0 (Level 2)**, **OWASP API Security Top 10 (2023)**, **OWASP MASVS v2 (L1)**, Pakistan's PECA 2016 / draft Personal Data Protection Bill principles (consent, minimisation, purpose limitation).

## 1. Threat model (STRIDE summary)

| Asset | Threats | Main controls |
|---|---|---|
| Accounts | Credential stuffing, brute force, session theft | Argon2id, lockout + rate limits, short-lived JWT, rotating refresh tokens with reuse detection, global logout |
| Seekers' safety (esp. women) | Stalking via address/phone, harassment | Exact address & coords hidden until owner accepts a visit; phone never exposed; in-app chat; report/auto-hide; suspension |
| Listings | Scams, fake photos, bait-and-switch | Contact verification before listing, admin moderation, re-review on material edits, verified-owner badge, reports |
| Uploaded media | Malware/polyglots, decompression bombs, EXIF GPS leak, parser exploits | Magic-byte sniffing, size caps while streaming, Pillow bomb guard, re-encode (strips EXIF), raw inputs in non-served storage, CV pipeline isolated in child processes with timeouts |
| API | IDOR/BOLA, mass assignment, injection, DoS | Object-level ownership checks (404), UUIDv4 IDs, Pydantic `extra="forbid"`, ORM parameterisation, rate limits, body-size limit, pagination caps |
| Viewer / web | XSS, clickjacking, open redirect | Strict CSP (`script-src 'self'`, no inline), `frame-ancestors` allow-list, viewer path allow-listing in app, no `innerHTML` with user data |
| Infra / secrets | Leaked keys, insecure prod config | Secrets only via env; app refuses to boot in production with dev secret/DEBUG/wildcard CORS/SQLite/non-HTTPS |

## 2. Controls mapped to OWASP API Top 10 (2023)

| # | Risk | Implementation (file) |
|---|---|---|
| API1 | Broken Object Level Authorization | `deps.owned_listing`, `tours._owned_tour`, `social._conv_for`, visit role checks — non-owners get **404** (no existence leak). Tests: `test_idor_other_owner_cannot_touch`, chat non-participant test |
| API2 | Broken Authentication | Argon2id (`security.py`), 15-min access JWT with issuer/type/version claims, HS256 pinned (no `alg=none`), refresh tokens are random 384-bit, stored as SHA-256, rotated on every use, **reuse ⇒ family revoked**, lockout after 5 failures, generic errors, timing-equalised dummy hash. Tests: `test_auth_security.py` |
| API3 | Broken Object Property Level Authorization | Separate input/output schemas; `extra="forbid"` blocks `is_admin`, `status`, `owner_id` injection; private fields (`address_line`, `lat/lng`, `views`, `rejection_reason`) only serialised for owner/admin/accepted visitor |
| API4 | Unrestricted Resource Consumption | Per-IP and per-user rate limits (Redis), 413 on oversized bodies, streaming upload caps (15 MB image / 200 MB video / 180 s), max photos/rooms/inputs, page size ≤ 50, recon timeout 15 min per room |
| API5 | Broken Function Level Authorization | `owner_user`, `verified_user`, `admin_user` dependencies; admin routes under `/admin` with audit log |
| API6 | Unrestricted Access to Sensitive Business Flows | Contact verification before chatting/listing; one pending visit per listing; report de-dup; auto-hide on 3 distinct reporters |
| API7 | SSRF | Server never fetches user-supplied URLs; GPU engine callback URL is configuration, not user input |
| API8 | Security Misconfiguration | Security headers on every response (CSP, nosniff, Referrer-Policy, Permissions-Policy, COOP, HSTS on HTTPS, X-Frame-Options), `/docs` disabled in production, production config guard, no stack traces to clients (generic 500 handler) |
| API9 | Improper Inventory Management | Versioned API (`/api/v1`), OpenAPI generated from code |
| API10 | Unsafe Consumption of APIs | SMS/GPU providers isolated behind adapters; responses validated |

## 3. Authentication & session details

* **Passwords**: min 8, max 128, ≥ 2 character classes, common-password deny-list, must not contain name/email/phone; Argon2id (memory-hard).
* **OTP**: 6 digits from `secrets`, stored as HMAC-SHA256 (keyed), 10-minute expiry, max 5 attempts, 45-second resend throttle, 5 requests/hour; previous codes invalidated on resend. Codes are returned in API responses **only** when `KAMRA_ENV` is `development`/`test`.
* **Password reset**: same response whether or not the account exists; success revokes all sessions.
* **Token storage on device**: refresh token in iOS Keychain / Android Keystore via `expo-secure-store` (`WHEN_UNLOCKED_THIS_DEVICE_ONLY`); access token only in memory. Web build uses `sessionStorage` (cleared on tab close).
* **No cookies** → no CSRF surface; CORS is an explicit allow-list without credentials.

## 4. Media pipeline security

1. Stream upload in 1 MB chunks, abort when the cap is exceeded.
2. Detect type from magic bytes (JPEG/PNG/WebP/MP4/MOV/WebM). Client MIME/extension ignored. HEIC rejected with guidance.
3. Images: `Image.verify()` + full decode with `MAX_IMAGE_PIXELS` (60 MP) → EXIF-orientation applied → **re-encoded JPEG** (drops EXIF/GPS/ICC payloads, neutralises polyglots).
4. Videos: container signature + decodable first frame + duration ≤ 180 s.
5. Storage keys are server-generated UUIDs; `storage.path_for` rejects traversal. Raw captures live in `storage/private/` which is **never** mounted over HTTP. Public files are served with `Content-Security-Policy: default-src 'none'; sandbox` and `nosniff`.
6. Reconstruction (OpenCV native code on untrusted input) runs in a **separate spawned process** per room with a hard timeout; crashes are retried once and surfaced as a friendly error — the API and worker stay up.

## 5. Privacy

* Data minimisation: no CNIC/ID numbers stored in MVP; exact location private by default; approximate coordinates rounded to ~1 km.
* User-initiated account deletion (`POST /me/delete`) cascades listings, photos, chats.
* Audit log of privileged actions (moderation, suspension, password changes, logins) with actor and IP.
* Logs contain request IDs, not request bodies; OTP codes masked outside development.

## 6. Mobile (MASVS) notes

* No secrets in the app bundle (API URL only).
* WebView hardening: origin allow-list, navigation restricted to the API origin, no file access, no mixed content, no multiple windows.
* Camera/photo permissions requested just-in-time with purpose strings; microphone permission not requested (videos are uploaded but audio is ignored); Android `RECORD_AUDIO` blocked.
* Release builds: enable Hermes bytecode, ProGuard/R8, certificate pinning via config plugin (roadmap), Play Integrity / App Attest (roadmap).

## 7. Operational checklist for production

- [ ] `KAMRA_ENV=production`, strong `KAMRA_JWT_SECRET` (≥ 48 random bytes), PostgreSQL, Redis, HTTPS-only `KAMRA_PUBLIC_BASE_URL`.
- [ ] Run behind a TLS-terminating proxy (nginx/Cloudflare) with `--proxy-headers --forwarded-allow-ips=<proxy>` so rate limits see real client IPs.
- [ ] Move `storage/` to S3/R2 (private bucket for `private/`, CDN for `public/`), enable versioning.
- [ ] Wire an SMS gateway in `routers/auth._send_otp` and an email provider.
- [ ] Alembic migrations instead of `create_all`; daily backups with PITR.
- [ ] Sentry/alerting on 5xx, worker failures and rate-limit spikes.
- [ ] Run `pip-audit` / `npm audit` in CI; dependency updates monthly.
- [ ] Annual third-party penetration test before scaling.

## 8. Verified by automated tests

`backend/tests/test_auth_security.py` and `test_marketplace.py` cover: weak/common password rejection, phone normalisation, duplicate accounts, mass-assignment rejection, generic login errors, lockout, OTP verify/resend throttle, refresh rotation + reuse detection, tampered/forged/`alg=none`/wrong-type tokens, session revocation on password change, reset without enumeration, rate limiting, security headers, body-size limit, production config guard, permission tiers, HTML stripping, IDOR, EXIF/GPS stripping, fake-image rejection, corrupt-image rejection, path traversal, private address disclosure rules, chat isolation, review eligibility, report auto-hide, suspension.
