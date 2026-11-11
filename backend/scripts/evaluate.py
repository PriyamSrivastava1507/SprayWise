"""
Score a segmentation method on labelled test images.

Images and masks are paired by file name (``photo.jpg`` <-> ``photo.png``, or
``001_image.png`` <-> ``001_mask.png``).
Masks hold 0 soil, 1 crop, 2 weed and 255 ignore. The photo is downscaled to the
working width exactly as the app does, and the mask with nearest-neighbour, so
the numbers describe the real pipeline.

A classical result of ``None`` (crop rows not found) is counted separately and
never as a correct prediction. The metrics are computed only over the photos
where rows were found, so always read them together with ``rows_detected_rate``.

Run it from ``backend/``::

    python -m scripts.evaluate test_samples/images test_samples/masks \
        --dataset "NAME OF TEST SET" --out data/evaluation/classical.json

For the ML method, call ``evaluate`` from Python and pass the client's predict
function instead of ``classical_segment``.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from typing import TypedDict

import numpy as np
from PIL import Image

from app.engine import (
    IGNORE,
    classical_segment,
    confusion_matrix,
    metrics_from_cm,
    resize_mask_nearest,
)

from .common import DEFAULT_WIDTH, RGB, Labels, list_images, load_rgb

Predictor = Callable[[RGB], Labels | None]

N_CLASSES = 3
MAX_CLASS_ID = 2
MASK_NDIM = 2  # a label mask is (H, W); colour masks are (H, W, 3)
ASPECT_TOLERANCE = 0.01  # image and mask may differ by 1% in aspect ratio
MAX_SHOWN_VALUES = 8


class EvaluationResult(TypedDict):
    iou: list[float]  # per class: soil, crop, weed
    precision: list[float]
    recall: list[float]
    mean_iou_all: float
    mean_iou_crop_weed: float
    n_images: int  # image/mask pairs that were processed
    n_evaluated: int  # of those, how many produced a mask
    rows_detected_rate: float
    ms_per_image: float | None


def load_mask(path: Path) -> Labels:
    """Read a ground-truth mask and check that it uses the 0/1/2/255 format."""
    with closing(Image.open(path)) as image:
        mask = np.asarray(image)

    if mask.ndim != MASK_NDIM:
        message = (
            f"{path.name}: mask must be a single-channel image, got shape "
            f"{mask.shape}. Convert colour masks to class ids 0/1/2 first."
        )
        raise ValueError(message)

    invalid = (mask > MAX_CLASS_ID) & (mask != IGNORE)

    if invalid.any():
        found = np.unique(mask[invalid]).tolist()[:MAX_SHOWN_VALUES]
        message = (
            f"{path.name}: mask holds values {found}; only 0 soil, 1 crop, "
            "2 weed and 255 ignore are allowed. Map the dataset's classes first."
        )
        raise ValueError(message)

    return mask.astype(np.uint8)


def _check_same_aspect(name: str, rgb: RGB, gt: Labels) -> None:
    """Catch masks that do not belong to the photo (for example rotated)."""
    image_aspect = rgb.shape[1] / rgb.shape[0]
    mask_aspect = gt.shape[1] / gt.shape[0]

    if abs(image_aspect - mask_aspect) / image_aspect > ASPECT_TOLERANCE:
        message = (
            f"{name}: image is {rgb.shape[1]}x{rgb.shape[0]} (after EXIF "
            f"rotation) but the mask is {gt.shape[1]}x{gt.shape[0]}; they do "
            "not line up."
        )
        raise ValueError(message)


def find_mask(masks_dir: Path, image_path: Path) -> Path | None:
    """
    Find the ground-truth mask that belongs to an image.

    Accepted names, in order (all ``.png``):
        photo.jpg        -> photo.png
        001_image.png    -> 001_mask.png   (the shared test-dataset convention)
        photo.jpg        -> photo_mask.png
    """
    stem = image_path.stem
    candidates = [stem]

    if stem.endswith("_image"):
        candidates.append(f"{stem[: -len('_image')]}_mask")

    candidates.append(f"{stem}_mask")

    for name in candidates:
        path = masks_dir / f"{name}.png"
        if path.exists():
            return path

    return None


def evaluate(
    images_dir: Path,
    masks_dir: Path,
    predict: Predictor,
    width: int = DEFAULT_WIDTH,
) -> EvaluationResult:
    """Run ``predict`` on every image/mask pair and score it."""
    cm = np.zeros((N_CLASSES, N_CLASSES), np.int64)
    n_images = 0
    n_scored = 0
    times_ms: list[float] = []
    without_mask: list[str] = []

    for image_path in list_images(images_dir):
        mask_path = find_mask(masks_dir, image_path)

        if mask_path is None:
            without_mask.append(image_path.name)
            continue

        rgb = load_rgb(image_path, width)
        gt = load_mask(mask_path)
        _check_same_aspect(image_path.name, rgb, gt)
        gt = resize_mask_nearest(gt, (rgb.shape[1], rgb.shape[0]))

        n_images += 1
        start = time.perf_counter()
        pred = predict(rgb)
        times_ms.append((time.perf_counter() - start) * 1000)

        if pred is None:  # classical: crop rows not found, counted separately
            continue

        if pred.shape != gt.shape:
            message = f"{image_path.name}: prediction {pred.shape} != mask {gt.shape}"
            raise ValueError(message)

        cm += confusion_matrix(gt, pred)
        n_scored += 1

    if without_mask:
        print(
            f"warning: {len(without_mask)} image(s) have no mask and were "
            f"skipped, for example {without_mask[0]}",
            file=sys.stderr,
        )

    if n_images == 0:
        message = f"no image/mask pairs found in {images_dir} and {masks_dir}"
        raise ValueError(message)

    metrics = metrics_from_cm(cm)

    return {
        "iou": metrics["iou"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "mean_iou_all": metrics["mean_iou_all"],
        "mean_iou_crop_weed": metrics["mean_iou_crop_weed"],
        "n_images": n_images,
        "n_evaluated": n_scored,
        "rows_detected_rate": round(n_scored / n_images, 3),
        "ms_per_image": round(float(np.mean(times_ms)), 1),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Score the classical engine, or one ML model (--model), on labelled images. "
            "Save as data/evaluation/<variant>__<test-set>.json, for example "
            "classical__cwfid-test.json or ml-we3ds__cwfid-test.json."
        ),
    )
    parser.add_argument("images", type=Path, help="folder with the test photos")
    parser.add_argument("masks", type=Path, help="folder with the masks (.png)")
    parser.add_argument("--dataset", default="", help="name of the test set")
    parser.add_argument("--out", type=Path, help="write the JSON result here")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument(
        "--model",
        help="score this ML model (a key from ML_MODELS in .env) instead of the classical engine",
    )
    args = parser.parse_args(argv)

    for folder in (args.images, args.masks):
        if not folder.is_dir():
            parser.error(f"not a folder: {folder}")

    predictor: Predictor = classical_segment
    model_fields: dict[str, object] = {"method": "classical"}
    if args.model:
        from app.clients.registry import ModelRegistry, UnknownModelKey
        from app.core.config import Settings

        registry = ModelRegistry.from_settings(Settings())
        try:
            chosen = registry.get(args.model)
        except UnknownModelKey:
            parser.error(f"unknown model '{args.model}'. Available: {', '.join(registry.keys)}")
        if not chosen.client.is_ready():
            print(f"error: model '{args.model}' is not available: {chosen.client.detail}", file=sys.stderr)
            return 1
        predictor = chosen.client.predict
        model_fields = {
            "method": "ml",
            "model_key": chosen.key,
            "model_label": chosen.label,
            "model_id": chosen.client.model_id,
        }

    try:
        result = evaluate(args.images, args.masks, predictor, args.width)
    except ValueError as error:  # bad masks, no pairs: show the message only
        print(f"error: {error}", file=sys.stderr)
        return 1

    payload: dict[str, object] = {**result, **model_fields}
    if args.dataset:
        payload["dataset"] = args.dataset

    text = json.dumps(payload, indent=2)
    print(text)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
