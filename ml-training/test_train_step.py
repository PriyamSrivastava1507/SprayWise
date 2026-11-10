from pathlib import Path
import sys
import torch
from torch.utils.data import DataLoader, Subset
import torch.optim as optim

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = Path(__file__).resolve().parent / "src"

sys.path.insert(0, str(SRC_DIR))

from train import (
    build_dataloaders,
    calculate_class_weights,
    train_one_epoch
)
from model import build_model, build_loss


root_dir = PROJECT_ROOT / "CWFID"
split_file = PROJECT_ROOT / "ml-training" / "configs" / "split.json"

device = torch.device("cpu")

train_loader, _ = build_dataloaders(
    root_dir, split_file, batch_size=1
)

# Use only one training sample
single_sample = Subset(train_loader.dataset, [0])

test_loader = DataLoader(single_sample, batch_size=1)

class_weights = calculate_class_weights(root_dir, split_file)

model = build_model().to(device)
criterion = build_loss(class_weights.tolist()).to(device)

optimizer = optim.AdamW(model.parameters(), lr=6e-5)

loss = train_one_epoch(
    model,
    test_loader,
    criterion,
    optimizer,
    device
)

print("Training step successful!")
print("Loss:", loss)