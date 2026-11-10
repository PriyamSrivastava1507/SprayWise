from pathlib import Path
import sys
import torch

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from evaluate import calculate_metrics

# Ground-truth mask
targets = torch.tensor([[
    [0, 0, 1, 1],
    [0, 2, 2, 2],
    [1, 1, 2, 255],
    [0, 0, 2, 255]
]])

# Predicted mask
predictions = torch.tensor([[
    [0, 0, 1, 1],
    [0, 2, 0, 2],
    [1, 1, 2, 1],
    [0, 0, 2, 0]
]])

metrics = calculate_metrics(predictions, targets)

for name, value in metrics.items():
    print(f"{name}: {value:.4f}")