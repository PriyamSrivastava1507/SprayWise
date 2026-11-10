from pathlib import Path

import numpy as np
from datasets import load_dataset
from PIL import Image

MAPPING = {0: 0, 1: 1, 2: 2}

lut = np.full(256, 255, np.uint8)  # unlisted values = ignore
for raw, cls in MAPPING.items():
    lut[raw] = cls

data = load_dataset("Project-AgML/carrot_weeds_germany")
data = data[list(data.keys())[0]]


def export(indices, img_dir, mask_dir):
    Path(img_dir).mkdir(parents=True, exist_ok=True)
    if mask_dir:
        Path(mask_dir).mkdir(parents=True, exist_ok=True)
    for i in indices:
        name = f"carrot{i:03d}"
        data[i]["image"].convert("RGB").save(f"{img_dir}/{name}.png")
        if mask_dir:
            m = np.array(data[i]["mask"])
            if m.ndim == 3:
                m = m[..., 0]
            Image.fromarray(lut[m]).save(f"{mask_dir}/{name}.png")


n = len(data)
tune_idx = range(20)  # first 20 for tuning
test_idx = range(20, n)  # the rest for evaluation
export(tune_idx, "my_photos", None)
export(test_idx, "test_samples/images", "test_samples/masks")
print("tuning photos:", len(tune_idx), "| test photos:", len(test_idx))
