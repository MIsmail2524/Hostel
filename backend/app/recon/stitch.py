"""Rotation-only panorama reconstruction → full equirectangular (360°×180°) image.

Pipeline: SIFT features → pairwise matching → homography camera estimation →
ray bundle adjustment → horizontal wave correction → exact spherical compositing
with per-channel gain compensation and feathered blending → hole filling.

World convention (same as OpenCV's stitching module): x right, y down, z forward.
Equirectangular: column ↔ yaw θ = atan2(x, z) ∈ [-π, π), row ↔ polar angle φ from up (-y).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


class StitchError(Exception):
    def __init__(self, code: str, message: str, hints: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hints = hints or []


@dataclass
class StitchResult:
    pano: np.ndarray  # BGR uint8, H = W/2
    horizontal_coverage: float  # fraction of 360° covered at the horizon
    sphere_coverage: float  # fraction of the sphere covered before hole filling
    used: list[int] = field(default_factory=list)
    dropped: list[int] = field(default_factory=list)
    focal_px: float = 0.0  # median focal at work scale


def _resize_to_megapix(img: np.ndarray, megapix: float) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    s = min(1.0, float(np.sqrt(megapix * 1e6 / (h * w))))
    if s < 1.0:
        img = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    return img, s


def _features(imgs: list[np.ndarray]):
    # Low contrast threshold: hostel rooms are mostly plain painted walls.
    finder = cv2.SIFT_create(nfeatures=4000, contrastThreshold=0.01, edgeThreshold=20)
    return [cv2.detail.computeImageFeatures2(finder, img) for img in imgs]


def _match(feats, match_conf: float = 0.6):
    matcher = cv2.detail_BestOf2NearestMatcher(False, match_conf)
    pairwise = matcher.apply2(feats)
    matcher.collectGarbage()
    # OpenCV zeroes the confidence of near-identical pairs (conf > 3) — common with video
    # keyframes and clean captures — which breaks the chain around the room. Restore them.
    for m in pairwise:
        if m.src_img_idx != m.dst_img_idx and m.confidence == 0 and m.num_inliers >= 12 and m.H is not None and m.H.size:
            m.confidence = min(2.9, m.num_inliers / (8 + 0.3 * len(m.matches)))
    return pairwise


def _solve(feats, pairwise, conf_thresh: float):
    """Homography-based initialisation + ray bundle adjustment on a connected image set."""
    estimator = cv2.detail_HomographyBasedEstimator()
    ok, cameras = estimator.apply(feats, pairwise, None)
    if not ok:
        raise StitchError("estimation_failed", "Camera estimation failed.", ["Capture again with more overlap"])
    for cam in cameras:
        cam.R = cam.R.astype(np.float32)
    adjuster = cv2.detail_BundleAdjusterRay()
    adjuster.setConfThresh(conf_thresh)
    adjuster.setRefinementMask(np.ones((3, 3), np.uint8))
    ok, cameras = adjuster.apply(feats, pairwise, cameras)
    if not ok:
        raise StitchError("adjustment_failed", "Bundle adjustment failed.", ["Capture again with more overlap"])
    return cameras


def _pair_errors(feats, pairwise, cameras, conf_thresh: float = 0.0) -> dict[tuple[int, int], float]:
    """Median reprojection error (px) of each matched pair under the solved rotation-only model."""
    Ks = [c.K().astype(np.float64) for c in cameras]
    Kinv = [np.linalg.inv(k) for k in Ks]
    Rs = [c.R.astype(np.float64) for c in cameras]
    errs: dict[tuple[int, int], float] = {}
    for m in pairwise:
        i, j = m.src_img_idx, m.dst_img_idx
        if i < 0 or j < 0 or i >= j or m.confidence <= 0 or m.confidence < conf_thresh:
            continue
        mask = np.asarray(m.inliers_mask).ravel().astype(bool)
        matches = [d for d, k in zip(m.matches, mask) if k]
        if len(matches) < 6:
            continue
        pi = np.float64([feats[i].keypoints[d.queryIdx].pt for d in matches])
        pj = np.float64([feats[j].keypoints[d.trainIdx].pt for d in matches])
        H = Ks[j] @ Rs[j].T @ Rs[i] @ Kinv[i]
        proj = cv2.perspectiveTransform(pi[None], H)[0]
        errs[(i, j)] = float(np.median(np.linalg.norm(proj - pj, axis=1)))
    return errs


def _rot_from_h(H: np.ndarray, K: np.ndarray) -> np.ndarray | None:
    M = np.linalg.inv(K) @ H @ K
    d = np.linalg.det(M)
    if not np.isfinite(d) or abs(d) < 1e-9:
        return None
    M = M / np.cbrt(d)
    U, _, Vt = np.linalg.svd(M)
    R = U @ Vt
    return R if np.linalg.det(R) > 0 else None


def _angle(R: np.ndarray) -> float:
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def inconsistent_pairs(feats, pairwise, conf_thresh: float, img_shape: tuple[int, int], tol_deg: float = 10.0) -> set[tuple[int, int]]:
    """Reject pairwise matches that violate rotation loop-consistency (R_jk·R_ij ≈ R_ik).

    Repeated objects (identical beds/cupboards/posters, tiles) yield confident but *wrong*
    pairwise homographies; such an edge disagrees with the triangles it closes.
    """
    edges = {}
    for m in pairwise:
        i, j = m.src_img_idx, m.dst_img_idx
        if i < 0 or j < 0 or i == j or m.confidence < max(conf_thresh, 1e-6) or m.H is None or not np.size(m.H):
            continue
        edges[(i, j)] = np.asarray(m.H, np.float64)
    if len(edges) < 3:
        return set()
    try:
        est = cv2.detail_HomographyBasedEstimator()
        ok, cams = est.apply(feats, pairwise, None)
        f = float(np.median([c.focal for c in cams])) if ok else None
    except cv2.error:
        f = None
    if not f or not np.isfinite(f):
        return set()
    h, w = img_shape
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1]], np.float64)
    R = {}
    for (i, j), H in edges.items():
        r = _rot_from_h(H, K)
        if r is not None:
            R[(i, j)] = r
    nodes = sorted({i for e in R for i in e})
    good: dict[tuple[int, int], int] = {}
    total: dict[tuple[int, int], int] = {}
    for (i, j), Rij in R.items():
        if i > j:
            continue
        for k in nodes:
            if k in (i, j) or (j, k) not in R or (i, k) not in R:
                continue
            err = _angle(R[(i, k)].T @ R[(j, k)] @ Rij)
            for e in ((i, j), (j, k), (i, k)):
                e = (min(e), max(e))
                total[e] = total.get(e, 0) + 1
                good[e] = good.get(e, 0) + (err < tol_deg)
    bad = set()
    for e, t in total.items():
        if good.get(e, 0) / t < 0.5:
            bad |= {e, (e[1], e[0])}
    return bad


def estimate_cameras(work_imgs: list[np.ndarray], conf_thresh: float):
    """Return (kept_indices, cameras) or raise StitchError.

    Repetitive structures (identical beds, cupboards, posters, floor tiles) can produce a
    *false* pairwise match that drags the whole solution into ghosting. After each solve we
    check every pair's reprojection error against the global model and ban the worst
    inconsistent pair, then re-solve (a lightweight RANSAC over the view graph).
    """
    feats = _features(work_imgs)
    if sum(1 for f in feats if len(f.keypoints) >= 50) < 2:
        raise StitchError(
            "too_few_features",
            "The photos have too little detail to align.",
            ["Turn on the lights and open curtains", "Include furniture, doors and windows in every shot"],
        )
    orig = list(range(len(work_imgs)))
    pairwise = _match(feats)
    banned: set[tuple[int, int]] = set(inconsistent_pairs(feats, pairwise, conf_thresh, work_imgs[0].shape[:2]))
    cameras = None
    for _ in range(10):
        for m in pairwise:
            if (orig[m.src_img_idx] if m.src_img_idx >= 0 else -1, orig[m.dst_img_idx] if m.dst_img_idx >= 0 else -1) in banned:
                m.confidence = 0.0
        kept = [int(i) for i in np.array(list(cv2.detail.leaveBiggestComponent(feats, pairwise, conf_thresh))).ravel()]
        if len(kept) < 2:
            raise StitchError(
                "no_overlap",
                "The photos could not be connected to each other.",
                ["Overlap each photo with the previous one by about a third", "Rotate on the spot instead of walking"],
            )
        if len(kept) < len(feats):
            # Re-match the connected subset so feature/match indices stay consistent.
            orig = [orig[k] for k in kept]
            feats = [feats[k] for k in kept]
            pairwise = _match(feats)
            continue
        cameras = _solve(feats, pairwise, conf_thresh)
        errs = _pair_errors(feats, pairwise, cameras, conf_thresh)
        if not errs:
            break
        (wi, wj), worst = max(errs.items(), key=lambda kv: kv[1])
        typical = float(np.median(list(errs.values())))
        if worst <= max(4.0, 4.0 * typical):
            break
        banned |= {(orig[wi], orig[wj]), (orig[wj], orig[wi])}
    assert cameras is not None

    rmats = cv2.detail.waveCorrect([np.copy(c.R) for c in cameras], cv2.detail.WAVE_CORRECT_HORIZ)
    # Guard against an upside-down solution: image "down" (+y) must point to world down (+y).
    down = np.mean([r[:, 1] for r in rmats], axis=0)
    if down[1] < 0:
        flip = np.diag([-1.0, -1.0, 1.0]).astype(np.float32)  # 180° about z
        rmats = [flip @ r for r in rmats]
    for cam, r in zip(cameras, rmats):
        cam.R = r.astype(np.float32)

    focals = [c.focal for c in cameras]
    if not all(np.isfinite(focals)) or min(focals) <= 0:
        raise StitchError("estimation_failed", "Camera estimation produced invalid focal lengths.")
    return orig, cameras


def _ray_grid(width: int, height: int, row0: int, row1: int) -> np.ndarray:
    j = (np.arange(width, dtype=np.float32) + 0.5) / width
    i = (np.arange(row0, row1, dtype=np.float32) + 0.5) / height
    theta = j * 2 * np.pi - np.pi
    phi = i * np.pi
    sp, cp = np.sin(phi)[:, None], np.cos(phi)[:, None]
    st, ct = np.sin(theta)[None, :], np.cos(theta)[None, :]
    d = np.empty((row1 - row0, width, 3), np.float32)
    d[..., 0] = sp * st
    d[..., 1] = -cp * np.ones_like(st)
    d[..., 2] = sp * ct
    return d


def _feather(h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    m[1:-1, 1:-1] = 255
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3).astype(np.float32)
    dist /= max(1.0, float(dist.max()))
    return dist**4 + 1e-6  # strong centre priority → narrow blend zones, less parallax ghosting


def _project_maps(d: np.ndarray, K: np.ndarray, R: np.ndarray, w: int, h: int):
    M = (K @ R.T).astype(np.float32)
    p = d @ M.T
    z = p[..., 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        mx = p[..., 0] / z
        my = p[..., 1] / z
    valid = (z > 1e-6) & (mx >= 0) & (mx <= w - 1) & (my >= 0) & (my <= h - 1)
    mx = np.where(valid, mx, -1).astype(np.float32)
    my = np.where(valid, my, -1).astype(np.float32)
    return mx, my, valid


def _gains(imgs, Ks, Rs, size=512) -> np.ndarray:
    """Per-image, per-channel gains (Brown & Lowe least squares on overlaps)."""
    n = len(imgs)
    H = size // 2
    d = _ray_grid(size, H, 0, H)
    samples, valids = [], []
    for img, K, R in zip(imgs, Ks, Rs):
        h, w = img.shape[:2]
        mx, my, valid = _project_maps(d, K, R, w, h)
        s = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT).astype(np.float32)
        samples.append(s)
        valids.append(valid)
    gains = np.ones((n, 3), np.float32)
    alpha, beta = 0.01, 100.0
    for c in range(3):
        A = np.zeros((n, n), np.float64)
        b = np.zeros(n, np.float64)
        for i in range(n):
            for j in range(n):
                ov = valids[i] & valids[j]
                N = float(ov.sum())
                if N < 1:
                    continue
                Iij = float(samples[i][..., c][ov].mean())
                Iji = float(samples[j][..., c][ov].mean())
                b[i] += beta * N
                A[i, i] += beta * N
                if i == j:
                    continue
                A[i, i] += 2 * alpha * Iij * Iij * N
                A[i, j] -= 2 * alpha * Iij * Iji * N
        try:
            gains[:, c] = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            pass
    return np.clip(gains, 0.5, 2.0)


def composite_equirect(imgs, Ks, Rs, out_w: int = 4096, strip: int = 256):
    """Composite calibrated images into an equirectangular panorama. Returns (pano_float, coverage_mask)."""
    out_h = out_w // 2
    gains = _gains(imgs, Ks, Rs) if len(imgs) > 1 else np.ones((1, 3), np.float32)
    feathers = [_feather(*img.shape[:2]) for img in imgs]
    pano = np.zeros((out_h, out_w, 3), np.float32)
    covered = np.zeros((out_h, out_w), bool)
    for r0 in range(0, out_h, strip):
        r1 = min(out_h, r0 + strip)
        d = _ray_grid(out_w, out_h, r0, r1)
        acc = np.zeros((r1 - r0, out_w, 3), np.float32)
        wsum = np.zeros((r1 - r0, out_w), np.float32)
        for img, K, R, g, fw in zip(imgs, Ks, Rs, gains, feathers):
            h, w = img.shape[:2]
            mx, my, valid = _project_maps(d, K, R, w, h)
            if not valid.any():
                continue
            col = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT).astype(np.float32)
            wt = cv2.remap(fw, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * valid
            acc += col * g[None, None, :] * wt[..., None]
            wsum += wt
        ok = wsum > 1e-6
        pano[r0:r1][ok] = acc[ok] / wsum[ok][:, None]
        covered[r0:r1] = ok
    return pano, covered


def fill_holes(pano: np.ndarray, covered: np.ndarray) -> np.ndarray:
    """Fill uncaptured areas (ceiling/floor caps, gaps) smoothly; wraps horizontally."""
    out = np.clip(pano, 0, 255).astype(np.uint8)
    if covered.all():
        return out
    if not covered.any():
        return out
    H, W = covered.shape
    lw, lh = 1024, 512
    small = cv2.resize(out, (lw, lh), interpolation=cv2.INTER_AREA)
    smask = cv2.resize(covered.astype(np.uint8), (lw, lh), interpolation=cv2.INTER_NEAREST)
    pad = 128
    small_p = np.concatenate([small[:, -pad:], small, small[:, :pad]], axis=1)
    hole_p = np.concatenate([smask[:, -pad:], smask, smask[:, :pad]], axis=1) == 0
    filled_p = cv2.inpaint(small_p, hole_p.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
    # Inpainting smears vertical streaks into big ceiling/floor caps; blur holes strongly
    # along the horizontal (wrapped) axis so caps become smooth, plausible gradients.
    wide = cv2.GaussianBlur(filled_p, (0, 0), sigmaX=36, sigmaY=3)
    filled_p = np.where(hole_p[..., None], wide, filled_p)
    filled = cv2.GaussianBlur(filled_p, (0, 0), 4)[:, pad:-pad]
    filled_big = cv2.resize(filled, (W, H), interpolation=cv2.INTER_CUBIC)
    # Feathered transition: blend over ~1.5° near the boundary.
    dist = cv2.distanceTransform(covered.astype(np.uint8), cv2.DIST_L2, 3)
    alpha = np.clip(dist / max(4.0, W / 240), 0, 1)[..., None]
    res = out.astype(np.float32) * alpha + filled_big.astype(np.float32) * (1 - alpha)
    return np.clip(res, 0, 255).astype(np.uint8)


def stitch_equirect(images: list[np.ndarray], out_w: int = 4096, work_megapix: float = 0.8) -> StitchResult:
    if len(images) < 2:
        raise StitchError("too_few_images", "At least 2 overlapping photos are needed.", ["Take 12 or more photos while turning on the spot"])
    work, work_scales = zip(*(_resize_to_megapix(im, work_megapix) for im in images))
    last_err: StitchError | None = None
    for conf in (1.0, 0.8, 0.6, 0.4):
        try:
            kept, cameras = estimate_cameras(list(work), conf)
            break
        except StitchError as e:  # retry with a looser confidence threshold
            last_err = e
        except cv2.error as e:
            last_err = StitchError("estimation_failed", f"Alignment failed ({e.err}).", ["Capture again with more overlap"])
    else:
        assert last_err is not None
        raise last_err

    # Compose at a resolution matching the panorama's angular resolution.
    target_f = 1.3 * out_w / (2 * np.pi)
    imgs, Ks, Rs = [], [], []
    for idx, cam in zip(kept, cameras):
        ws = work_scales[idx]
        f_full = cam.focal / ws
        cs = min(1.0, target_f / f_full)
        full = images[idx]
        img = cv2.resize(full, None, fx=cs, fy=cs, interpolation=cv2.INTER_AREA) if cs < 1.0 else full
        K = cam.K().astype(np.float64)
        K[:2, :] *= cs / ws
        imgs.append(img)
        Ks.append(K)
        Rs.append(cam.R.astype(np.float64))

    # Align yaw so the first kept image faces the panorama centre.
    fwd = Rs[0] @ np.array([0.0, 0.0, 1.0])
    yaw = float(np.arctan2(fwd[0], fwd[2]))
    c, s = np.cos(-yaw), np.sin(-yaw)
    Ry = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    Rs = [Ry @ R for R in Rs]

    pano_f, covered = composite_equirect(imgs, Ks, Rs, out_w=out_w)
    H = covered.shape[0]
    band = covered[int(H * 0.47) : int(H * 0.53)]
    horizontal = float(band.any(axis=0).mean())
    lat_w = np.sin((np.arange(H) + 0.5) / H * np.pi)[:, None]
    sphere = float((covered * lat_w).sum() / (lat_w.sum() * covered.shape[1]))
    pano = fill_holes(pano_f, covered)
    dropped = [i for i in range(len(images)) if i not in kept]
    return StitchResult(pano, horizontal, sphere, kept, dropped, float(np.median([c.focal for c in cameras])))
