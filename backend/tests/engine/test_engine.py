import io

import numpy as np
import pytest
from PIL import Image

from app.engine import (
    analyze_grid,
    classical_segment,
    classical_segment_with_info,
    compute_savings,
    confusion_matrix,
    metrics_from_cm,
    pressure_level,
    render_overlay,
    resize_mask_nearest,
    vegetation_mask,
)
from tests.engine.synthetic import RGB, SOIL_COLOR, make_fallow, make_field


def _bare_soil(h: int = 300, w: int = 400) -> RGB:
    soil = np.zeros((h, w, 3), np.uint8)
    soil[:] = SOIL_COLOR
    noise = np.random.default_rng(0).integers(-12, 12, soil.shape)
    return np.clip(soil.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def test_vegetation_mask_finds_green_not_soil() -> None:
    rgb, gt = make_field(seed=0)
    veg = vegetation_mask(rgb) > 0
    plants = gt > 0
    assert veg[plants].mean() > 0.9  # almost all plant pixels detected
    assert veg[~plants].mean() < 0.05  # almost no soil pixels flagged


def test_vegetation_mask_bare_soil_is_empty() -> None:
    assert (vegetation_mask(_bare_soil()) > 0).sum() == 0


@pytest.mark.parametrize("angle", [0, 12, -20, 90])
def test_rows_found_at_several_angles(angle: int) -> None:
    rgb, gt = make_field(angle=angle, seed=3)
    mask, info = classical_segment_with_info(rgb)
    assert mask is not None
    assert info["rows_detected"]
    # Optional keys are read with .get(): they exist only when rows were found.
    assert 4 <= info.get("n_rows", 0) <= 14
    assert abs(info.get("spacing_px", 0.0) - 80) < 6
    m = metrics_from_cm(confusion_matrix(gt, mask))
    print(
        f"angle {angle}: est {info.get('angle_deg', float('nan')):.1f}, "
        f"rows {info.get('n_rows', 0)}, IoU soil/crop/weed {m['iou']}",
    )
    assert m["iou"][1] > 0.80  # crop
    assert m["iou"][2] > 0.60  # weed


@pytest.mark.parametrize("seed", range(12))
def test_rows_not_found_on_fallow_fields(seed: int) -> None:
    rgb, _ = make_fallow(h=768, w=1024, n_blobs=15 + 12 * seed, seed=100 + seed)
    assert classical_segment(rgb) is None


def test_tight_rows_found_but_touching_weeds_are_a_known_limitation() -> None:
    # Rows only 60 px apart, so many weeds touch the crop and merge with it.
    rgb, gt = make_field(h=768, w=1024, spacing=60, angle=11.0, seed=19, n_weeds=22)
    mask, info = classical_segment_with_info(rgb)
    assert mask is not None
    assert abs(info.get("spacing_px", 0.0) - 60) < 6
    m = metrics_from_cm(confusion_matrix(gt, mask))
    assert m["iou"][1] > 0.9  # crop is still labelled well
    assert m["precision"][2] > 0.7  # reported weeds are real; recall suffers


def test_stress_random_angles_spacings_and_lighting() -> None:
    rng = np.random.default_rng(42)
    cm = np.zeros((3, 3), np.int64)

    for i in range(20):
        angle = float(rng.uniform(-80, 80))
        spacing = int(rng.choice([60, 70, 80, 100, 120]))
        rgb, gt = make_field(
            h=768,
            w=1024,
            spacing=spacing,
            angle=angle,
            n_weeds=int(rng.integers(10, 60)),
            n_inrow_weeds=int(rng.integers(0, 8)),
            seed=int(rng.integers(0, 10000)),
        )
        if i % 2 == 0:  # uneven lighting
            gradient = np.linspace(0.7, 1.15, rgb.shape[1])[None, :, None]
            rgb = np.clip(rgb.astype(np.float32) * gradient, 0, 255).astype(np.uint8)

        mask, info = classical_segment_with_info(rgb)
        assert mask is not None, f"rows not found: angle {angle:.1f}, spacing {spacing}"
        assert abs(info.get("spacing_px", 0.0) - spacing) < 8
        assert info.get("periodicity", 0.0) > 0.8
        cm += confusion_matrix(gt, mask)

    m = metrics_from_cm(cm)
    assert m["iou"][1] > 0.9
    assert m["iou"][2] > 0.7


def test_rows_not_found_on_bare_soil() -> None:
    assert classical_segment(_bare_soil()) is None


def test_mask_format() -> None:
    rgb, _ = make_field(seed=5)
    mask = classical_segment(rgb)
    assert mask is not None
    assert mask.dtype == np.uint8
    assert mask.shape == rgb.shape[:2]
    assert set(np.unique(mask).tolist()).issubset({0, 1, 2})


def test_grid_non_divisible_and_stats() -> None:
    mask = np.zeros((101, 203), np.uint8)
    mask[:50, :100] = 2  # weeds fill the top-left quarter-ish
    g = analyze_grid(mask, 8, 8, 0.10)
    assert len(g.density) == 8
    assert len(g.density[0]) == 8
    assert 0 < g.spray_fraction < 1
    assert g.weed_pct == pytest.approx(100 * (50 * 100) / mask.size, abs=0.01)
    assert g.crop_pct == 0
    assert g.vegetation_pct == g.weed_pct


def test_grid_all_clean_and_all_weed() -> None:
    clean = analyze_grid(np.zeros((64, 64), np.uint8), 4, 4, 0.1)
    assert clean.spray_cells == []
    assert clean.spray_fraction == 0

    full = analyze_grid(np.full((64, 64), 2, np.uint8), 4, 4, 0.1)
    assert len(full.spray_cells) == 16
    assert full.spray_fraction == 1


def test_savings_hand_computed() -> None:
    s = compute_savings(2.0, 3.0, 5.0, 0.25)
    assert s == {
        "blanket_cost": 30.0,
        "spot_cost": 7.5,
        "saved_litres": 4.5,
        "saved_pct": 75.0,
    }


def test_pressure_boundaries() -> None:
    assert pressure_level(4.99, 5, 15) == "Low"
    assert pressure_level(5.0, 5, 15) == "Medium"
    assert pressure_level(14.99, 5, 15) == "Medium"
    assert pressure_level(15.0, 5, 15) == "High"


def test_overlay_is_valid_png_same_size() -> None:
    rgb, gt = make_field(seed=2)
    img = Image.open(io.BytesIO(render_overlay(rgb, gt)))
    assert img.format == "PNG"
    assert img.size == (rgb.shape[1], rgb.shape[0])


def test_mask_resize_keeps_class_ids() -> None:
    classes = np.array([0, 1, 2, 255], np.uint8)
    gt = classes[np.random.default_rng(0).integers(0, 4, size=(50, 60))]
    small = resize_mask_nearest(gt, (30, 25))
    assert set(np.unique(small).tolist()).issubset({0, 1, 2, 255})


def test_metrics_ignore_label() -> None:
    gt = np.array([[0, 1, 2, 255]], np.uint8)
    pred = np.array([[0, 1, 1, 2]], np.uint8)
    cm = confusion_matrix(gt, pred)
    assert cm.sum() == 3  # the 255 pixel is skipped
    m = metrics_from_cm(cm)
    assert m["iou"][0] == pytest.approx(1.0, abs=1e-3)
