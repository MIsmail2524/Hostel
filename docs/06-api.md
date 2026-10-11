# Kamra — REST API Reference

Base URL: `/api/v1` · Auth: `Authorization: Bearer <access_token>` · Interactive docs (dev): `/docs` · Machine-readable: `/openapi.json`.

Errors are JSON: `{"detail": "Human readable message", "errors": [{"field": "rent_monthly", "message": "…"}]}`. Rate-limited responses return **429** with `Retry-After`.

Auth levels: **public** · **user** (any signed-in) · **verified** (contact verified) · **owner** (verified + owner tools) · **admin**.

## auth

| Method | Path | Summary | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Register | public/optional |
| POST | `/api/v1/auth/login` | Login | public/optional |
| POST | `/api/v1/auth/refresh` | Refresh | public/optional |
| POST | `/api/v1/auth/logout` | Logout | public/optional |
| POST | `/api/v1/auth/logout-all` | Logout All | bearer |
| POST | `/api/v1/auth/otp/request` | Otp Request | bearer |
| POST | `/api/v1/auth/otp/verify` | Otp Verify | bearer |
| POST | `/api/v1/auth/password/forgot` | Forgot | public/optional |
| POST | `/api/v1/auth/password/reset` | Reset | public/optional |
| POST | `/api/v1/auth/password/change` | Change Password | bearer |

## me

| Method | Path | Summary | Auth |
|---|---|---|---|
| GET | `/api/v1/me` | Me | bearer |
| PATCH | `/api/v1/me` | Update Me | bearer |
| POST | `/api/v1/me/delete` | Delete Account | bearer |
| GET | `/api/v1/me/favorites` | Favorites | bearer |

## listings

| Method | Path | Summary | Auth |
|---|---|---|---|
| GET | `/api/v1/listings` | Search | public/optional |
| POST | `/api/v1/listings` | Create | bearer |
| GET | `/api/v1/listings/cities` | Cities | public/optional |
| GET | `/api/v1/listings/mine` | Mine | bearer |
| GET | `/api/v1/listings/{listing_id}` | Get Listing | bearer |
| PUT | `/api/v1/listings/{listing_id}` | Update | bearer |
| DELETE | `/api/v1/listings/{listing_id}` | Delete | bearer |
| PATCH | `/api/v1/listings/{listing_id}/availability` | Availability | bearer |
| POST | `/api/v1/listings/{listing_id}/status` | Change Status | bearer |
| POST | `/api/v1/listings/{listing_id}/photos` | Upload Photos | bearer |
| DELETE | `/api/v1/listings/{listing_id}/photos/{photo_id}` | Delete Photo | bearer |
| PUT | `/api/v1/listings/{listing_id}/photos/order` | Reorder | bearer |
| POST | `/api/v1/listings/{listing_id}/favorite` | Favorite | bearer |
| DELETE | `/api/v1/listings/{listing_id}/favorite` | Unfavorite | bearer |
| GET | `/api/v1/listings/{listing_id}/reviews` | Reviews | public/optional |
| POST | `/api/v1/listings/{listing_id}/reviews` | Add Review | bearer |
| POST | `/api/v1/listings/{listing_id}/reviews/{review_id}/reply` | Reply Review | bearer |

## tours

| Method | Path | Summary | Auth |
|---|---|---|---|
| POST | `/api/v1/listings/{listing_id}/tour` | Create Tour | bearer |
| GET | `/api/v1/tours/{tour_id}` | Get Tour | bearer |
| POST | `/api/v1/tours/{tour_id}/rooms` | Add Room | bearer |
| PATCH | `/api/v1/tours/{tour_id}/rooms/{room_id}` | Update Room | bearer |
| DELETE | `/api/v1/tours/{tour_id}/rooms/{room_id}` | Delete Room | bearer |
| POST | `/api/v1/tours/{tour_id}/rooms/{room_id}/inputs` | Upload Inputs | bearer |
| DELETE | `/api/v1/tours/{tour_id}/rooms/{room_id}/inputs` | Clear Inputs | bearer |
| POST | `/api/v1/tours/{tour_id}/process` | Process | bearer |
| POST | `/api/v1/tours/{tour_id}/preview-link` | Preview Link | bearer |
| GET | `/api/v1/tours/{tour_id}/manifest` | Manifest | public/optional |

## social

| Method | Path | Summary | Auth |
|---|---|---|---|
| GET | `/api/v1/conversations` | Conversations | bearer |
| POST | `/api/v1/conversations` | Start Conversation | bearer |
| GET | `/api/v1/conversations/unread-count` | Unread Count | bearer |
| GET | `/api/v1/conversations/{conv_id}` | Get Conversation | bearer |
| GET | `/api/v1/conversations/{conv_id}/messages` | Messages | bearer |
| POST | `/api/v1/conversations/{conv_id}/messages` | Send Message | bearer |
| GET | `/api/v1/visits` | Visits | bearer |
| POST | `/api/v1/visits` | Request Visit | bearer |
| PATCH | `/api/v1/visits/{visit_id}` | Update Visit | bearer |
| POST | `/api/v1/reports` | Report | bearer |

## admin

| Method | Path | Summary | Auth |
|---|---|---|---|
| GET | `/api/v1/admin/stats` | Stats | bearer |
| GET | `/api/v1/admin/listings/pending` | Pending | bearer |
| POST | `/api/v1/admin/listings/{listing_id}/moderate` | Moderate | bearer |
| GET | `/api/v1/admin/reports` | Reports | bearer |
| POST | `/api/v1/admin/reports/{report_id}` | Resolve Report | bearer |
| PATCH | `/api/v1/admin/users/{user_id}` | Update User | bearer |
| GET | `/api/v1/admin/audit` | Audit Log | bearer |

## Tour manifest (viewer contract)

```json
{
  "id": "uuid", "version": 1, "engine": "room360", "title": "Listing title", "listing_id": "uuid",
  "rooms": [{"id": "uuid", "name": "Bedroom", "pano": "/media/…jpg (4096×2048 equirect)", "pano_small": "/media/…_2k.jpg",
             "preview": "/media/…_preview.jpg", "width": 3.7, "length": 4.3, "height": 3.0, "camera_height": 1.5,
             "yaw_offset": 0, "origin": [1.85, 0.0]}],
  "links": [{"from": "room-uuid", "to": "room-uuid"}]
}
```
