from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent / "src")
)

from train import calculate_class_weights

weights = calculate_class_weights(
    root_dir=PROJECT_ROOT / "CWFID",
    split_file=PROJECT_ROOT / "ml-training" / "configs" / "split.json"
)

print("Class weights:", weights)
print("Background:", weights[0].item())
print("Crop:", weights[1].item())
print("Weed:", weights[2].item())