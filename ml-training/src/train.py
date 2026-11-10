import json
from pathlib import Path
from PIL import Image
import numpy as np
import torch

from torch.utils.data import DataLoader
from dataset import CWFIDataset
from preprocessing import SegmentationPreprocessor
from augmentation import SegmentationAugmentation

import torch.nn.functional as F
import torch.optim as optim

from model import build_model, build_loss
from evaluate import (
    update_confusion_matrix,
    metrics_from_confusion_matrix
)


def calculate_class_weights(root_dir, split_file):
    root_dir = Path(root_dir)

    with open(split_file, "r") as f:
        split_data = json.load(f)

    train_ids = split_data["train"]
    mask_dir = root_dir / "processed_masks"

    pixel_counts = np.zeros(3, dtype=np.int64)

    for image_id in train_ids:
        mask_path = mask_dir / f"{image_id:03d}_mask.png"

        mask = np.array(
            Image.open(mask_path),
            dtype=np.uint8
        )

        valid_pixels = mask[mask != 255]

        pixel_counts += np.bincount(
            valid_pixels,
            minlength=3
        )[:3]

    if np.any(pixel_counts == 0):
        raise ValueError("One or more classes have no valid training pixels.")

    frequencies = pixel_counts / pixel_counts.sum()

    # Inverse square-root frequency weighting
    weights = 1.0 / np.sqrt(frequencies)

    # Normalize weights to mean 1
    weights = weights / weights.mean()

    return torch.tensor(weights, dtype=torch.float32)

class SegmentationTransform:
    def __init__(self, augment=False, image_size=(512, 512)):
        self.augment = augment
        self.preprocessor = SegmentationPreprocessor(image_size)

        if augment:
            self.augmentation = SegmentationAugmentation()

    def __call__(self, image, mask):
        if self.augment:
            image, mask = self.augmentation(image, mask)

        image, mask = self.preprocessor(image, mask)

        return image, mask

def build_dataloaders(root_dir, split_file, batch_size=2):

    train_dataset = CWFIDataset(
        root_dir=root_dir,
        split_file=split_file,
        split="train",
        transform=SegmentationTransform(augment=True)
    )

    val_dataset = CWFIDataset(
        root_dir=root_dir,
        split_file=split_file,
        split="validation",
        transform=SegmentationTransform(augment=False)
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available()
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available()
    )

    return train_loader, val_loader

def train_one_epoch(model, loader, criterion, optimizer, device):

    model.train()
    total_loss = 0.0

    for images, masks in loader:

        images = images.to(device)
        masks = masks.to(device)

        optimizer.zero_grad()

        outputs = model(pixel_values=images)

        logits = F.interpolate(
            outputs.logits,
            size=masks.shape[-2:],
            mode="bilinear",
            align_corners=False
        )

        loss = criterion(logits, masks)

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(loader)

def validate(model, loader, criterion, device):

    model.eval()

    total_loss = 0.0

    confusion_matrix = torch.zeros(
        (3, 3),
        dtype=torch.int64
    )

    with torch.no_grad():

        for images, masks in loader:

            images = images.to(device)
            masks = masks.to(device)

            outputs = model(pixel_values=images)

            logits = F.interpolate(
                outputs.logits,
                size=masks.shape[-2:],
                mode="bilinear",
                align_corners=False
            )

            loss = criterion(logits, masks)

            total_loss += loss.item()

            predictions = torch.argmax(logits, dim=1)

            batch_confusion = update_confusion_matrix(
                predictions,
                masks
            )

            confusion_matrix += batch_confusion.cpu()

    metrics = metrics_from_confusion_matrix(confusion_matrix)

    average_loss = total_loss / len(loader)

    return average_loss, metrics


def train_model(
    root_dir,
    split_file,
    epochs=30,
    batch_size=2,
    learning_rate=6e-5
):

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("Training device:", device)

    train_loader, val_loader = build_dataloaders(
        root_dir,
        split_file,
        batch_size
    )

    class_weights = calculate_class_weights(
        root_dir,
        split_file
    )

    print("Class weights:", class_weights)

    model = build_model().to(device)

    criterion = build_loss(
        class_weights.tolist()
    ).to(device)

    optimizer = optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=0.01
    )

    checkpoint_dir = Path(__file__).resolve().parents[1] / "artifacts" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    best_miou = -1.0

    for epoch in range(epochs):

        train_loss = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device
        )

        val_loss, metrics = validate(
            model,
            val_loader,
            criterion,
            device
        )

        print(f"\nEpoch [{epoch + 1}/{epochs}]")
        print(f"Training Loss: {train_loss:.4f}")
        print(f"Validation Loss: {val_loss:.4f}")

        print(f"Background IoU: {metrics['background_iou']:.4f}")
        print(f"Crop IoU:       {metrics['crop_iou']:.4f}")
        print(f"Weed IoU:       {metrics['weed_iou']:.4f}")
        print(f"Mean IoU:       {metrics['mean_iou']:.4f}")

        if metrics["mean_iou"] > best_miou:

            best_miou = metrics["mean_iou"]

            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_miou": best_miou
                },
                checkpoint_dir / "best_model.pt"
            )

            print("Best model checkpoint saved!")

    print("\nTraining completed.")
    print(f"Best validation mIoU: {best_miou:.4f}")


if __name__ == "__main__":

    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    train_model(
        root_dir=PROJECT_ROOT / "CWFID",
        split_file=PROJECT_ROOT / "ml-training" / "configs" / "split.json"
    )