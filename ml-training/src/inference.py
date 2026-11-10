
from pathlib import Path

import numpy as np
import torch
import matplotlib.pyplot as plt

from PIL import Image
from torch.utils.data import DataLoader

if __package__:
    from .model import build_model
    from .dataset import CWFIDataset
    from .preprocessing import SegmentationPreprocessor
    from .evaluate import (
        update_confusion_matrix,
        metrics_from_confusion_matrix
    )
else:
    from model import build_model
    from dataset import CWFIDataset
    from preprocessing import SegmentationPreprocessor
    from evaluate import (
        update_confusion_matrix,
        metrics_from_confusion_matrix
    )


NUM_CLASSES = 3

CLASS_NAMES = {
    0: "Background",
    1: "Crop",
    2: "Weed"
}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_model(checkpoint_path):

    checkpoint_path = Path(checkpoint_path)

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}"
        )

    model = build_model()

    checkpoint = torch.load(
        checkpoint_path,
        map_location=DEVICE,
        weights_only=False
    )

    # Support both full training checkpoints and plain state dictionaries.
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.to(DEVICE)
    model.eval()

    print(f"Model loaded successfully on {DEVICE}")

    if "epoch" in checkpoint:
        print("Checkpoint epoch:", checkpoint["epoch"])

    if "best_foreground_miou" in checkpoint:
        print(
            "Best foreground mIoU:",
            checkpoint["best_foreground_miou"]
        )

    return model


def predict(model, image_path, image_size=(512, 512)):

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(image_path)

    original_image = Image.open(image_path).convert("RGB")
    original_array = np.array(original_image, dtype=np.float32) / 255.0

    preprocessor = SegmentationPreprocessor(image_size=image_size)

    processed_image = preprocessor.preprocess_image(original_array)

    image_tensor = torch.from_numpy(
        np.ascontiguousarray(processed_image.transpose(2, 0, 1))
    ).float().unsqueeze(0).to(DEVICE)

    with torch.no_grad():

        outputs = model(pixel_values=image_tensor)

        logits = torch.nn.functional.interpolate(
            outputs.logits,
            size=image_size,
            mode="bilinear",
            align_corners=False
        )

        prediction = torch.argmax(logits, dim=1)[0]

    prediction = prediction.cpu().numpy().astype(np.uint8)

    # Resize prediction to original image dimensions for visualization.
    prediction_image = Image.fromarray(prediction)

    prediction_image = prediction_image.resize(
        original_image.size,
        resample=Image.Resampling.NEAREST
    )

    return original_array, np.array(prediction_image), prediction


def visualize_prediction(
    original_image,
    prediction,
    ground_truth=None,
    title="Segmentation Prediction"
):

    panels = 3 if ground_truth is not None else 2

    fig, axes = plt.subplots(
        1,
        panels,
        figsize=(6 * panels, 6)
    )

    if panels == 2:
        axes = list(axes)

    axes[0].imshow(original_image)
    axes[0].set_title("Original Image")
    axes[0].axis("off")

    if ground_truth is not None:
        axes[1].imshow(
            ground_truth,
            vmin=0,
            vmax=2,
            cmap="viridis",
            interpolation="nearest"
        )
        axes[1].set_title("Ground Truth")
        axes[1].axis("off")

        prediction_axis = axes[2]

    else:
        prediction_axis = axes[1]

    prediction_axis.imshow(
        prediction,
        vmin=0,
        vmax=2,
        cmap="viridis",
        interpolation="nearest"
    )

    prediction_axis.set_title(title)
    prediction_axis.axis("off")

    plt.tight_layout()
    plt.show()


def evaluate_test_set(
    model,
    root_dir,
    split_file,
    batch_size=2,
    image_size=(512, 512)
):

    preprocessor = SegmentationPreprocessor(
        image_size=image_size
    )

    test_dataset = CWFIDataset(
        root_dir=root_dir,
        split_file=split_file,
        split="test",
        transform=preprocessor
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=torch.cuda.is_available()
    )

    confusion_matrix = torch.zeros(
        NUM_CLASSES,
        NUM_CLASSES,
        dtype=torch.long
    )

    model.eval()

    with torch.no_grad():

        for images, masks in test_loader:

            images = images.to(DEVICE)
            masks = masks.to(DEVICE)

            outputs = model(pixel_values=images)

            logits = torch.nn.functional.interpolate(
                outputs.logits,
                size=masks.shape[-2:],
                mode="bilinear",
                align_corners=False
            )

            predictions = torch.argmax(logits, dim=1)

            batch_confusion = update_confusion_matrix(
                predictions,
                masks
            )

            confusion_matrix += batch_confusion.cpu()

    metrics = metrics_from_confusion_matrix(
        confusion_matrix
    )

    diagonal = confusion_matrix.diag().sum().item()
    total_pixels = confusion_matrix.sum().item()

    pixel_accuracy = (
        diagonal / total_pixels if total_pixels > 0 else 0.0
    )

    foreground_miou = (
        metrics["crop_iou"] + metrics["weed_iou"]
    ) / 2

    print("\n" + "=" * 55)
    print("FINAL TEST SET EVALUATION")
    print("=" * 55)

    print("Test images:", len(test_dataset))
    print("Background IoU:", round(metrics["background_iou"], 4))
    print("Crop IoU:", round(metrics["crop_iou"], 4))
    print("Weed IoU:", round(metrics["weed_iou"], 4))
    print("Overall mIoU:", round(metrics["mean_iou"], 4))
    print("Foreground mIoU:", round(foreground_miou, 4))
    print("Pixel Accuracy:", round(pixel_accuracy, 4))

    print("\nConfusion Matrix:")
    print(confusion_matrix.numpy())

    return {
        **metrics,
        "foreground_miou": foreground_miou,
        "pixel_accuracy": pixel_accuracy,
        "confusion_matrix": confusion_matrix.numpy()
    }
