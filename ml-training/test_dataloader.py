from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent / "src")
)

from train import build_dataloaders

train_loader, val_loader = build_dataloaders(
    root_dir=PROJECT_ROOT / "CWFID",
    split_file=PROJECT_ROOT / "ml-training" / "configs" / "split.json",
    batch_size=2
)

images, masks = next(iter(train_loader))

print("Training batches:", len(train_loader))
print("Validation batches:", len(val_loader))
print("Image batch shape:", images.shape)
print("Mask batch shape:", masks.shape)
print("Mask classes:", masks.unique().tolist())