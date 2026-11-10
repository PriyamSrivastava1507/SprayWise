
import os
import json
import random
from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from torch.utils.data import DataLoader

from dataset import CWFIDataset
from preprocessing import SegmentationPreprocessor
from augmentation import SegmentationAugmentation

from model import build_model
from evaluate import (
    update_confusion_matrix,
    metrics_from_confusion_matrix
)

from huggingface_hub import HfApi, hf_hub_download
from kaggle_secrets import UserSecretsClient


# ============================================================
# CONFIGURATION
# ============================================================

NUM_CLASSES = 3
IGNORE_INDEX = 255

EPOCHS = 50
BATCH_SIZE = 2
LEARNING_RATE = 6e-5
WEIGHT_DECAY = 0.01

EARLY_STOPPING_PATIENCE = 10

DEVICE = torch.device(
    "cuda:0" if torch.cuda.is_available() else "cpu"
)

USE_AMP = DEVICE.type == "cuda"

# Automatic recovery settings
AUTO_RESUME = True

# Set this to a checkpoint path to resume from a specific file.
# Leave as None for automatic local/Hugging Face recovery.
RESUME_FROM = None


# ============================================================
# HUGGING FACE BACKUP CONFIGURATION
# ============================================================

HF_REPO_ID = "Smitika-2005/SprayWise-segformer-b0"
HF_UPLOAD_EVERY = 3

user_secrets = UserSecretsClient()
HF_TOKEN = user_secrets.get_secret("HF_TOKEN")

hf_api = HfApi(token=HF_TOKEN)

print("Hugging Face backup configured.")


# ============================================================
# HUGGING FACE BACKUP AND RECOVERY FUNCTIONS
# ============================================================

def upload_checkpoint_to_hf(checkpoint_path, remote_filename):
    """Upload a locally saved checkpoint to the private HF repository."""

    checkpoint_path = Path(checkpoint_path)

    if not checkpoint_path.exists():
        print(f"Backup skipped: {checkpoint_path} does not exist.")
        return False

    try:
        hf_api.upload_file(
            path_or_fileobj=str(checkpoint_path),
            path_in_repo=remote_filename,
            repo_id=HF_REPO_ID,
            repo_type="model",
            commit_message=f"Backup {remote_filename}"
        )

        print(f"Successfully backed up: {remote_filename}")
        return True

    except Exception as e:
        print(f"WARNING: Hugging Face backup failed: {e}")
        return False


def download_checkpoint_from_hf(remote_filename):
    """Download a checkpoint from Hugging Face for recovery."""

    try:
        checkpoint_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=remote_filename,
            repo_type="model",
            token=HF_TOKEN,
            force_download=True
        )

        print(f"Recovered checkpoint: {remote_filename}")
        return checkpoint_path

    except Exception as e:
        print(f"No remote checkpoint available: {e}")
        return None


def resolve_resume_checkpoint(local_checkpoint):
    """Prefer a local checkpoint; otherwise recover it from Hugging Face."""

    local_checkpoint = Path(local_checkpoint)

    if local_checkpoint.exists():
        print(f"Resuming from local checkpoint: {local_checkpoint}")
        return str(local_checkpoint)

    print("Local checkpoint not found. Trying Hugging Face recovery...")

    recovered_path = download_checkpoint_from_hf("last_checkpoint.pt")

    if recovered_path:
        return recovered_path

    print("No previous checkpoint found. Starting fresh.")
    return None


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(seed=42):

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ============================================================
# CLASS WEIGHTS
# ============================================================

def calculate_class_weights(root_dir, split_file):

    root_dir = Path(root_dir)

    with open(split_file, "r") as f:
        split_data = json.load(f)

    train_ids = split_data["train"]

    mask_dir = root_dir / "processed_masks"

    pixel_counts = np.zeros(NUM_CLASSES, dtype=np.int64)

    for image_id in train_ids:

        mask_path = mask_dir / f"{image_id:03d}_mask.png"

        mask = np.array(
            Image.open(mask_path),
            dtype=np.uint8
        )

        valid_pixels = mask[mask != IGNORE_INDEX]

        pixel_counts += np.bincount(
            valid_pixels,
            minlength=NUM_CLASSES
        )[:NUM_CLASSES]

    if np.any(pixel_counts == 0):
        raise ValueError("A class has no valid training pixels.")

    frequencies = pixel_counts / pixel_counts.sum()

    weights = 1.0 / np.sqrt(frequencies)

    weights = weights / weights.mean()

    return torch.tensor(weights, dtype=torch.float32)


# ============================================================
# DATA TRANSFORMS
# ============================================================

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


# ============================================================
# DATALOADERS
# ============================================================

def build_dataloaders(root_dir, split_file):

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
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        pin_memory=USE_AMP
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=USE_AMP
    )

    return train_loader, val_loader


# ============================================================
# DICE LOSS
# ============================================================

def dice_loss(logits, targets):

    probabilities = torch.softmax(logits.float(), dim=1)

    valid_mask = targets != IGNORE_INDEX

    safe_targets = targets.masked_fill(
        ~valid_mask, 0
    )

    one_hot = F.one_hot(
        safe_targets,
        num_classes=NUM_CLASSES
    ).permute(0, 3, 1, 2).float()

    valid_mask = valid_mask.unsqueeze(1).float()

    probabilities = probabilities * valid_mask
    one_hot = one_hot * valid_mask

    intersection = (probabilities * one_hot).sum(
        dim=(0, 2, 3)
    )

    denominator = (
        probabilities.sum(dim=(0, 2, 3))
        + one_hot.sum(dim=(0, 2, 3))
    )

    dice = (
        2.0 * intersection + 1e-6
    ) / (
        denominator + 1e-6
    )

    return 1.0 - dice[1:].mean()


# ============================================================
# COMBINED LOSS
# ============================================================

class CombinedLoss(nn.Module):

    def __init__(self, class_weights):

        super().__init__()

        self.ce_loss = nn.CrossEntropyLoss(
            weight=class_weights,
            ignore_index=IGNORE_INDEX
        )

    def forward(self, logits, targets):

        ce = self.ce_loss(logits, targets)

        dice = dice_loss(logits, targets)

        return 0.5 * ce + 0.5 * dice


# ============================================================
# MODEL OUTPUT RESIZING
# ============================================================

def get_logits(model, images, target_size):

    outputs = model(pixel_values=images)

    logits = F.interpolate(
        outputs.logits.float(),
        size=target_size,
        mode="bilinear",
        align_corners=False
    )

    return logits


# ============================================================
# TRAIN ONE EPOCH
# ============================================================

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
    scaler
):

    model.train()

    total_loss = 0.0

    for images, masks in loader:

        images = images.to(DEVICE, non_blocking=True)
        masks = masks.to(DEVICE, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with torch.autocast(
            device_type=DEVICE.type,
            dtype=torch.float16,
            enabled=USE_AMP
        ):

            logits = get_logits(
                model,
                images,
                masks.shape[-2:]
            )

            loss = criterion(logits, masks)

        scaler.scale(loss).backward()

        scaler.step(optimizer)

        scaler.update()

        total_loss += loss.item()

    return total_loss / len(loader)


# ============================================================
# VALIDATION
# ============================================================

def validate(model, loader, criterion):

    model.eval()

    total_loss = 0.0

    confusion_matrix = torch.zeros(
        (NUM_CLASSES, NUM_CLASSES),
        dtype=torch.int64
    )

    with torch.no_grad():

        for images, masks in loader:

            images = images.to(DEVICE, non_blocking=True)
            masks = masks.to(DEVICE, non_blocking=True)

            with torch.autocast(
                device_type=DEVICE.type,
                dtype=torch.float16,
                enabled=USE_AMP
            ):

                logits = get_logits(
                    model,
                    images,
                    masks.shape[-2:]
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

    metrics["foreground_miou"] = (
        metrics["crop_iou"] + metrics["weed_iou"]
    ) / 2.0

    average_loss = total_loss / len(loader)

    return average_loss, metrics


# ============================================================
# CHECKPOINT MANAGEMENT
# ============================================================

def save_checkpoint(checkpoint, path):

    path = Path(path)

    temporary_path = path.with_suffix(".tmp")

    torch.save(checkpoint, temporary_path)

    os.replace(temporary_path, path)


def save_history(history, path):

    temporary_path = path.with_suffix(".tmp")

    with open(temporary_path, "w") as f:
        json.dump(history, f, indent=4)

    os.replace(temporary_path, path)


def create_checkpoint(
    epoch,
    model,
    optimizer,
    scheduler,
    scaler,
    best_foreground_miou,
    epochs_without_improvement,
    history
):

    return {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict(),
        "scaler_state_dict": scaler.state_dict(),
        "best_foreground_miou": best_foreground_miou,
        "epochs_without_improvement": epochs_without_improvement,
        "history": history,
        "python_rng_state": random.getstate(),
        "numpy_rng_state": np.random.get_state(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_state": (
            torch.cuda.get_rng_state_all()
            if torch.cuda.is_available()
            else None
        )
    }


def restore_rng_state(checkpoint):

    random.setstate(checkpoint["python_rng_state"])
    np.random.set_state(checkpoint["numpy_rng_state"])
    torch.set_rng_state(checkpoint["torch_rng_state"])

    if (
        torch.cuda.is_available()
        and checkpoint["cuda_rng_state"] is not None
    ):

        torch.cuda.set_rng_state_all(
            checkpoint["cuda_rng_state"]
        )


# ============================================================
# MAIN TRAINING FUNCTION
# ============================================================

def train_model(root_dir, split_file, resume_from=None):

    set_seed(42)

    print("=" * 60)
    print("SPRAYWISE SEGMENTATION TRAINING")
    print("=" * 60)

    print("Training device:", DEVICE)
    print("Mixed precision:", USE_AMP)

    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    train_loader, val_loader = build_dataloaders(
        root_dir,
        split_file
    )

    print("Training images:", len(train_loader.dataset))
    print("Validation images:", len(val_loader.dataset))

    class_weights = calculate_class_weights(
        root_dir,
        split_file
    )

    print("Class weights:", class_weights.tolist())

    model = build_model().to(DEVICE)

    criterion = CombinedLoss(
        class_weights.to(DEVICE)
    )

    optimizer = optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY
    )

    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=3,
        min_lr=1e-6
    )

    scaler = torch.amp.GradScaler(
        "cuda",
        enabled=USE_AMP
    )

    checkpoint_dir = (
        Path(__file__).resolve().parents[1]
        / "artifacts"
        / "checkpoints"
    )

    checkpoint_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    last_checkpoint_path = checkpoint_dir / "last_checkpoint.pt"
    best_checkpoint_path = checkpoint_dir / "best_model.pt"
    history_path = checkpoint_dir / "training_history.json"

    start_epoch = 0
    best_foreground_miou = -1.0
    epochs_without_improvement = 0
    history = []

    # --------------------------------------------------------
    # AUTOMATIC CHECKPOINT RESOLUTION
    # --------------------------------------------------------

    if resume_from is not None:

        print("\nUsing explicitly provided checkpoint:", resume_from)

    elif AUTO_RESUME:

        resume_from = resolve_resume_checkpoint(
            last_checkpoint_path
        )

    else:

        print("\nAutomatic resume disabled. Starting fresh.")

    # --------------------------------------------------------
    # RESUME TRAINING
    # --------------------------------------------------------

    if resume_from is not None:

        print("\nResuming from:", resume_from)

        checkpoint = torch.load(
            resume_from,
            map_location=DEVICE,
            weights_only=False
        )

        model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        optimizer.load_state_dict(
            checkpoint["optimizer_state_dict"]
        )

        scheduler.load_state_dict(
            checkpoint["scheduler_state_dict"]
        )

        scaler.load_state_dict(
            checkpoint["scaler_state_dict"]
        )

        start_epoch = checkpoint["epoch"]

        best_foreground_miou = checkpoint[
            "best_foreground_miou"
        ]

        epochs_without_improvement = checkpoint[
            "epochs_without_improvement"
        ]

        history = checkpoint["history"]

        restore_rng_state(checkpoint)

        print("Resuming from epoch:", start_epoch + 1)

        print(
            "Previous best foreground mIoU:",
            round(best_foreground_miou, 4)
        )

    # --------------------------------------------------------
    # TRAINING LOOP
    # --------------------------------------------------------

    for epoch in range(start_epoch, EPOCHS):

        print("\n" + "=" * 60)
        print(f"EPOCH {epoch + 1}/{EPOCHS}")
        print("=" * 60)

        train_loss = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            scaler
        )

        val_loss, metrics = validate(
            model,
            val_loader,
            criterion
        )

        current_lr = optimizer.param_groups[0]["lr"]

        scheduler.step(metrics["foreground_miou"])

        print(f"Training Loss:       {train_loss:.4f}")
        print(f"Validation Loss:     {val_loss:.4f}")

        print(f"Background IoU:      {metrics['background_iou']:.4f}")
        print(f"Crop IoU:            {metrics['crop_iou']:.4f}")
        print(f"Weed IoU:            {metrics['weed_iou']:.4f}")

        print(f"Overall mIoU:        {metrics['mean_iou']:.4f}")
        print(f"Foreground mIoU:     {metrics['foreground_miou']:.4f}")
        print(f"Learning Rate:       {current_lr:.7f}")

        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "learning_rate": current_lr,
            **metrics
        })

        # ----------------------------------------------------
        # BEST MODEL CHECKPOINT + IMMEDIATE HF BACKUP
        # ----------------------------------------------------

        improved = (
            metrics["foreground_miou"]
            > best_foreground_miou + 1e-4
        )

        if improved:

            best_foreground_miou = metrics["foreground_miou"]

            epochs_without_improvement = 0

            best_checkpoint = create_checkpoint(
                epoch + 1,
                model,
                optimizer,
                scheduler,
                scaler,
                best_foreground_miou,
                epochs_without_improvement,
                history
            )

            save_checkpoint(
                best_checkpoint,
                best_checkpoint_path
            )

            print("\nBEST MODEL SAVED!")

            upload_checkpoint_to_hf(
                best_checkpoint_path,
                "best_model.pt"
            )

        else:

            epochs_without_improvement += 1

        # ----------------------------------------------------
        # SAVE LATEST CHECKPOINT EVERY EPOCH
        # ----------------------------------------------------

        latest_checkpoint = create_checkpoint(
            epoch + 1,
            model,
            optimizer,
            scheduler,
            scaler,
            best_foreground_miou,
            epochs_without_improvement,
            history
        )

        save_checkpoint(
            latest_checkpoint,
            last_checkpoint_path
        )

        save_history(
            history,
            history_path
        )

        print("\nLatest checkpoint saved locally.")

        # ----------------------------------------------------
        # DETERMINE WHETHER TRAINING WILL STOP
        # ----------------------------------------------------

        early_stopping = (
            epochs_without_improvement
            >= EARLY_STOPPING_PATIENCE
        )

        final_epoch = (epoch + 1) >= EPOCHS

        # ----------------------------------------------------
        # PERIODIC HUGGING FACE BACKUP
        # ----------------------------------------------------

        should_upload_latest = (
            (epoch + 1) % HF_UPLOAD_EVERY == 0
            or final_epoch
            or early_stopping
        )

        if should_upload_latest:

            print("\nUploading latest checkpoint to Hugging Face...")

            upload_checkpoint_to_hf(
                last_checkpoint_path,
                "last_checkpoint.pt"
            )

        else:

            print(
                f"Next latest-checkpoint backup scheduled "
                f"after epoch {((epoch // HF_UPLOAD_EVERY) + 1) * HF_UPLOAD_EVERY}."
            )

        # ----------------------------------------------------
        # EARLY STOPPING
        # ----------------------------------------------------

        if early_stopping:

            print("\nEarly stopping triggered.")
            break

    print("\n" + "=" * 60)
    print("TRAINING COMPLETED")
    print("=" * 60)

    print(
        "Best validation foreground mIoU:",
        round(best_foreground_miou, 4)
    )

    print("Best model:", best_checkpoint_path)
    print("Latest checkpoint:", last_checkpoint_path)
    print("Training history:", history_path)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    train_model(
        root_dir=PROJECT_ROOT / "CWFID",
        split_file=(
            PROJECT_ROOT
            / "ml-training"
            / "configs"
            / "split.json"
        ),
        resume_from=RESUME_FROM
    )
