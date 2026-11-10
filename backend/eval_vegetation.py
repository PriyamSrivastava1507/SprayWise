import json
from pathlib import Path

from app.engine import IGNORE, resize_mask_nearest, vegetation_mask
from scripts.common import list_images, load_rgb
from scripts.evaluate import load_mask

IMAGES, MASKS = Path("test_samples/images"), Path("test_samples/masks")

tp = fp = fn = 0
n = 0
for img_path in list_images(IMAGES):
    mask_path = MASKS / f"{img_path.stem}.png"
    if not mask_path.exists():
        continue
    rgb = load_rgb(img_path)
    gt = resize_mask_nearest(load_mask(mask_path), (rgb.shape[1], rgb.shape[0]))
    keep = gt != IGNORE
    truth = (gt > 0)[keep]  # crop or weed = vegetation
    pred = (vegetation_mask(rgb) > 0)[keep]
    tp += int((truth & pred).sum())
    fp += int((~truth & pred).sum())
    fn += int((truth & ~pred).sum())
    n += 1

result = {
    "n_images": n,
    "vegetation_iou": round(tp / (tp + fp + fn + 1e-9), 4),
    "vegetation_precision": round(tp / (tp + fp + 1e-9), 4),
    "vegetation_recall": round(tp / (tp + fn + 1e-9), 4),
}
print(json.dumps(result, indent=2))
