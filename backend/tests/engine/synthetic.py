"""Synthetic field images with exact ground truth, for engine tests."""

import cv2
import numpy as np
from numpy.typing import NDArray

RGB = NDArray[np.uint8]  # (H, W, 3)
Labels = NDArray[np.uint8]  # (H, W): 0 soil, 1 crop, 2 weed

SOIL_COLOR = (122, 92, 62)  # brown, RGB


def make_field(  # noqa: PLR0913
    h: int = 600,
    w: int = 800,
    spacing: int = 80,
    angle: float = 0.0,
    n_weeds: int = 30,
    n_inrow_weeds: int = 0,
    seed: int = 0,
    plant_gap: int = 34,
) -> tuple[RGB, Labels]:
    """
    Return (rgb, gt). gt: 0 soil, 1 crop, 2 weed.

    Rows run vertically before the image is rotated by ``angle`` degrees.
    """
    rng = np.random.default_rng(seed)

    # Big canvas, rotated then centre-cropped (no border artefacts).
    d = int(np.hypot(h, w)) + 40
    img = np.zeros((d, d, 3), np.uint8)
    img[:] = SOIL_COLOR
    img = np.clip(
        img.astype(np.int16) + rng.integers(-12, 12, img.shape),
        0,
        255,
    ).astype(np.uint8)
    gt = np.zeros((d, d), np.uint8)

    x0 = (d % spacing) // 2 + spacing // 2
    rows_x = np.arange(x0, d, spacing)

    # Crop plants along each row.
    for rx in rows_x:
        for y in range(plant_gap // 2, d, plant_gap):
            c = (int(rx + rng.integers(-4, 5)), int(y + rng.integers(-4, 5)))
            r = int(rng.integers(11, 16))
            col = (
                int(rng.integers(40, 70)),
                int(rng.integers(130, 160)),
                int(rng.integers(40, 70)),
            )
            cv2.circle(img, c, r, col, -1)
            cv2.circle(gt, c, r, 1, -1)

    # Weeds between rows.
    placed = 0
    while placed < n_weeds:
        x, y = int(rng.integers(0, d)), int(rng.integers(0, d))
        if np.min(np.abs(rows_x - x)) < 0.38 * spacing:
            continue
        r = int(rng.integers(8, 14))
        col = (
            int(rng.integers(70, 100)),
            int(rng.integers(150, 185)),
            int(rng.integers(30, 60)),
        )
        cv2.circle(img, (x, y), r, col, -1)
        cv2.circle(gt, (x, y), r, 2, -1)
        placed += 1

    # Small weeds inside the row band.
    for _ in range(n_inrow_weeds):
        rx = int(rng.choice(rows_x))
        y = int(rng.integers(0, d))
        centre = (rx + 3, y + plant_gap // 2)
        cv2.circle(img, centre, 5, (80, 170, 40), -1)
        cv2.circle(gt, centre, 5, 2, -1)

    m = cv2.getRotationMatrix2D((d / 2, d / 2), angle, 1.0)
    img = cv2.warpAffine(
        img,
        m,
        (d, d),
        flags=cv2.INTER_LINEAR,
        borderValue=SOIL_COLOR,
    )
    gt = cv2.warpAffine(gt, m, (d, d), flags=cv2.INTER_NEAREST)

    y0, xc = (d - h) // 2, (d - w) // 2

    # warpAffine is typed as a generic array, so pin the dtype (also copies).
    return (
        img[y0 : y0 + h, xc : xc + w].astype(np.uint8),
        gt[y0 : y0 + h, xc : xc + w].astype(np.uint8),
    )


def make_fallow(
    h: int = 600,
    w: int = 800,
    n_blobs: int = 60,
    seed: int = 1,
) -> tuple[RGB, Labels]:
    """Soil with randomly scattered green weeds and no rows."""
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = SOIL_COLOR
    gt = np.zeros((h, w), np.uint8)

    for _ in range(n_blobs):
        c = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        r = int(rng.integers(8, 20))
        cv2.circle(img, c, r, (75, 165, 45), -1)
        cv2.circle(gt, c, r, 2, -1)

    return img, gt
