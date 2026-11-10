from pathlib import Path
import sys
import torch

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from model import build_model, build_loss

model = build_model()

print("Model loaded successfully!")
print("Number of labels:", model.config.num_labels)
print("Labels:", model.config.id2label)

criterion = build_loss()
print("Loss function:", criterion)

print("Total parameters:", sum(p.numel() for p in model.parameters()))

model.eval()

dummy_input = torch.randn(1, 3, 512, 512)

with torch.no_grad():
    output = model(pixel_values=dummy_input)

print("Input shape:", dummy_input.shape)
print("Output logits shape:", output.logits.shape)