# Kamra — Photos/Video → Interactive 3D Walkthrough

## 1. Goal

An owner captures a room with an ordinary phone (photos or one video). Kamra produces an **interactive 3D tour** the seeker can explore: look around 360°, walk inside the room, jump between rooms, and see a "dollhouse" overview — inside the app and on the web.

## 2. Research summary — how the industry does it

| Approach | Used by | Input | Compute | Output quality | Fit for Kamra MVP |
|---|---|---|---|---|---|
| **360° panorama + room layout** (rotation-only capture, stitched to equirectangular, projected on a room shell, hotspots between rooms) | Zillow 3D Home, Kuula, Teleport, Matterport "phone capture" (+ depth) | Phone photos/video taken while rotating in place | CPU, seconds–minutes | Photoreal from the capture point; geometry approximate (box) | ✅ **Shipped engine ("Room-360")** |
| **Photogrammetry** (SfM + MVS → textured mesh) | Polycam (photo mode), RealityCapture, Meta-shape, COLMAP/OpenMVS | 50–300 overlapping photos walking around | CPU heavy (30–120 min/room) or GPU | True geometry; struggles on white walls (textureless), glass | ⚠️ Too slow on CPU for marketplace UX; poor on plain painted walls common in hostels |
| **NeRF** | Luma AI (early), Nerfstudio | Video | GPU, 20–60 min | Photoreal novel views; heavy to render on phones | ❌ |
| **3D Gaussian Splatting** (Kerbl et al. 2023; gsplat, Nerfstudio *splatfacto*) | Luma, Polycam, Scaniverse, KIRI | 1–3 min walk-around video | GPU, ~10–20 min | Photoreal **free** walkthrough, real-time on phones via WebGL splat renderers | ✅ **Premium engine (designed, needs a GPU worker)** |
| LiDAR / depth capture | Matterport, Apple RoomPlan | iPhone Pro LiDAR | On-device | Accurate dimensions | ❌ excludes most PK phones |

**Decision**: ship the **Room-360 engine** now (works on any Android phone, CPU only, robust on textureless walls because it only needs rotational overlap), and keep the **Gaussian-Splat engine** behind the same `ReconstructionEngine` interface for a GPU worker pool.

## 3. Capture guidance (shown in-app, HCI: "help users avoid errors")

1. Stand in the **centre** of the room, phone at **chest height**, lights on, curtains open.
2. **Photos**: turn on the spot, take a photo every ~30° (12+ photos), each overlapping the previous by ~⅓. Add one row tilted up (ceiling) and one tilted down (floor) for best results.
3. **Video**: record **one slow full turn** (≈ 20–30 s), then a slow turn looking slightly up and one looking slightly down.
4. Don't walk while capturing (rotation only), avoid people moving in the frame.
5. Optional: enter room size (or pick "small / medium / large") — used for the 3D room shell.

## 4. Room-360 engine — algorithm

```
inputs (photos | video)
  │
  ├─ video → frame sampling (every ~0.25 s) → sharpness score (variance of Laplacian)
  │          → keep sharpest frame per window → drop near-duplicates (thumbnail diff)
  ├─ photos → EXIF-orientation fix → downscale
  ▼
quality gate: count, blur, exposure  → actionable error/hints if failing
  ▼
features: SIFT (fallback ORB) on ~0.6 MP work images
pairwise matching: BestOf2Nearest (all pairs, ≤ 36 images) + RANSAC homographies
view-graph verification (robust to repeated objects — identical beds, cupboards, tiles):
  · loop consistency: relative rotations from each pair's homography must compose
    around triangles (R_jk·R_ij ≈ R_ik, tol 10°); edges failing most triangles are rejected
  · post-solve residual check: per-pair median reprojection error under the solved
    rotation model; the worst inconsistent pair is banned and the solve repeated
leaveBiggestComponent → drop images that don't connect (reported)
camera estimation: HomographyBasedEstimator → BundleAdjusterRay (focal + rotation)
wave correction (horizontal) → level horizon
  ▼
custom equirectangular compositor (exact spherical mapping, handles the 360° seam):
  for every output pixel (θ, φ): ray d → each camera p = K Rᵀ d → sample if in front & inside
  weights = feathered distance-to-border (sharp centre priority)
  per-image gain compensation (least-squares on overlaps) → removes exposure steps
  ▼
hole filling (uncaptured ceiling/floor caps & gaps): inpaint at low res + soft blend
  ▼
outputs per room: pano_4096.jpg, pano_2048.jpg (low-end devices), preview.jpg, quality.json
  ▼
tour manifest (JSON): rooms[], dims (w,l,h), capture height, yaw offset, layout positions, hotspots
```

Each room is processed in a **separate spawned process** with a 15-minute timeout and one retry, so a native crash or pathological upload never takes down the API/worker.

### 4.1 Viewer (three.js)

* Each room is a **box mesh** (floor, 4 walls, ceiling) sized from owner dimensions (default 3.7 × 4.3 × 3.0 m).
* A custom shader **projects the panorama from the capture point** onto the box: for each fragment `dir = normalize(P - C)`, `uv = (atan2(dir.x, dir.z)/2π + ½, acos(-dir.y)/π)`. From the capture point this is pixel-exact; when walking, walls/floor stay consistent so the room feels three-dimensional.
* **Walk**: tap/click on the floor to glide there; WASD/arrow keys; on-screen joystick on touch. Collision keeps the camera inside the room.
* **Look**: drag/swipe; pinch/scroll zoom (FOV).
* **Rooms**: hotspots (door rings) and a room bar; smooth fade transitions.
* **Dollhouse**: ceilings hidden, orbit camera above the layout — shows the whole space at once.
* Mobile-first: 2048 px textures on low-memory devices, `devicePixelRatio` capped at 2, works offline-cached.

### 4.2 Limitations (honest)

* Geometry is a box: furniture appears "painted" on walls/floor when you walk far from the capture point. The capture point itself is photo-accurate.
* Rotation-only capture is required; walking while capturing introduces parallax → stitching seams (the quality report flags it).
* Plain featureless walls with < 30 % overlap can fail to register → user gets a precise hint ("take more photos with more overlap").

## 5. Gaussian-Splat engine (premium, GPU) — design

```
video (1–3 min walk-around) → ffmpeg frames (2 fps, sharpest) → COLMAP / GLOMAP SfM (poses)
→ gsplat / Nerfstudio splatfacto training (≈ 7–30 k iters, 10–20 min on RTX 4090/L4)
→ pruning + SH-degree reduction + compression (.splat / .spz / SOGS, 10–40 MB)
→ viewer: WebGL splat renderer (e.g. @mkkellogg/gaussian-splats-3d or Spark) with free walk
```
* Runs on a remote GPU worker (RunPod / Modal / AWS g5) — the API enqueues with `engine="gsplat"`, the worker calls back with output URLs.
* `GaussianSplatEngine` in `backend/app/recon/engines.py` implements the interface and is enabled when `GPU_WORKER_URL` is configured; otherwise the API rejects `engine=gsplat` with a clear message.
* Cost: ≈ USD 0.10–0.40 per room at spot GPU prices → sold as a premium "Photoreal 3D" add-on.

## 6. Verification strategy

`backend/tests/test_recon.py` builds a **synthetic textured room** with known ground-truth panorama, renders perspective "phone photos" (65° FOV, with exposure jitter and noise) and a rotating **video**, runs the full engine, and checks:
* the stitch succeeds and covers ≥ 90 % of the horizontal field,
* the reconstructed panorama matches ground truth (normalised cross-correlation after yaw alignment),
* the video path extracts frames and produces a panorama,
* the manifest validates and the viewer can load it (browser test).
