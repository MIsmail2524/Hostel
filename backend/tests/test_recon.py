"""Reconstruction accuracy against ground truth, including realistic hand-held parallax."""
import cv2
import numpy as np
import pytest

from app.recon.frames import load_images
from app.recon.stitch import StitchError, stitch_equirect
from app.recon.synthetic import Room, RoomRenderer, capture_photos


def _ncc(gt, pano):
    pano = cv2.resize(pano, (gt.shape[1], gt.shape[0]))
    H = gt.shape[0]
    band = slice(int(H * 0.35), int(H * 0.65))
    A = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY)[band].astype(np.float32)
    B = cv2.cvtColor(pano, cv2.COLOR_BGR2GRAY)[band].astype(np.float32)
    a = A - A.mean()
    return max(float((a * (np.roll(B, s, 1) - B.mean())).sum() / np.sqrt((a * a).sum() * ((B - B.mean()) ** 2).sum())) for s in range(0, A.shape[1], 4))


@pytest.mark.parametrize(
    "arm,min_ncc",
    [
        (0.0, 0.9),   # ideal: phone rotated about its own centre
        (0.3, 0.7),   # realistic: person turns their body, phone 30 cm in front → parallax
    ],
)
def test_rotation_capture_accuracy(tmp_path, arm, min_ncc):
    room = Room(seed=7)
    imgs = load_images(capture_photos(room, tmp_path, arm=arm))
    res = stitch_equirect(imgs, out_w=2048)
    assert res.horizontal_coverage >= 0.95
    assert len(res.used) >= 20
    assert _ncc(RoomRenderer(room).equirect(1024), res.pano) >= min_ncc


def test_too_few_images():
    with pytest.raises(StitchError):
        stitch_equirect([np.zeros((480, 640, 3), np.uint8)])
