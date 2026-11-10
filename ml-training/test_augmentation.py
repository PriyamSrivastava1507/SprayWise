from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dataset import CWFIDataset
from augmentation import SegmentationAugmentation

dataset = CWFIDataset(
    root_dir=PROJECT_ROOT / "CWFID",
    split_file=PROJECT_ROOT / "ml-training" / "configs" / "split.json",
    split="train"
)

augment = SegmentationAugmentation()

image, mask = dataset[0]

image = image.permute(1, 2, 0).numpy()
mask = mask.numpy()

aug_image, aug_mask = augment(image, mask)

print("Augmented image shape:", aug_image.shape)
print("Augmented mask shape:", aug_mask.shape)
print("Image dtype:", aug_image.dtype)
print("Mask dtype:", aug_mask.dtype)
print("Mask classes:", sorted(np.unique(aug_mask).tolist()))