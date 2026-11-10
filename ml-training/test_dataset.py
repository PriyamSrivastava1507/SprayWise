from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from dataset import CWFIDataset

dataset = CWFIDataset(
    root_dir=PROJECT_ROOT / "CWFID",
    split_file=PROJECT_ROOT / "ml-training" / "configs" / "split.json",
    split="train"
)

image, mask = dataset[0]

print("Training samples:", len(dataset))
print("Image shape:", image.shape)
print("Mask shape:", mask.shape)
print("Mask classes:", mask.unique().tolist())