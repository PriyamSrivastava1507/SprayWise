import torch

NUM_CLASSES = 3
IGNORE_INDEX = 255


def update_confusion_matrix(predictions, targets):
    valid = targets != IGNORE_INDEX

    predictions = predictions[valid]
    targets = targets[valid]

    confusion_matrix = torch.bincount(
        NUM_CLASSES * targets + predictions,
        minlength=NUM_CLASSES ** 2
    ).reshape(NUM_CLASSES, NUM_CLASSES)

    return confusion_matrix


def metrics_from_confusion_matrix(confusion_matrix):
    true_positives = confusion_matrix.diag()

    false_positives = confusion_matrix.sum(dim=0) - true_positives
    false_negatives = confusion_matrix.sum(dim=1) - true_positives

    denominator = true_positives + false_positives + false_negatives

    iou = true_positives.float() / denominator.clamp(min=1)

    return {
        "background_iou": iou[0].item(),
        "crop_iou": iou[1].item(),
        "weed_iou": iou[2].item(),
        "mean_iou": iou.mean().item()
    }


def calculate_metrics(predictions, targets):
    confusion_matrix = update_confusion_matrix(predictions, targets)
    return metrics_from_confusion_matrix(confusion_matrix)