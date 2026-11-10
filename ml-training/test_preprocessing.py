from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dataset import CWFIDataset
from preprocessing import SegmentationPreprocessor

dataset = CWFIDataset(
    root_dir=PROJECT_ROOT / "CWFID",
    split_file=PROJECT_ROOT / "ml-training" / "configs" / "split.json",
    split="train"
)

preprocessor = SegmentationPreprocessor(image_size=(512, 512))

image, mask = dataset[0]

image = image.permute(1, 2, 0).numpy()
mask = mask.numpy()

processed_image, processed_mask = preprocessor(image, mask)

print("Processed image shape:", processed_image.shape)
print("Processed mask shape:", processed_mask.shape)
print("Image dtype:", processed_image.dtype)
print("Mask dtype:", processed_mask.dtype)
print("Mask classes:", sorted(set(processed_mask.flatten().tolist())))