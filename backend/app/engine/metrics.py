"""Segmentation metrics shared by the evaluation script and the tests."""

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray

from .constants import IGNORE
from .engine_types import LabelMask

EPS = 1e-9

ConfusionMatrix = NDArray[np.int64]


class Metrics(TypedDict):
    iou: list[float]
    precision: list[float]
    recall: list[float]
    mean_iou_all: float
    mean_iou_crop_weed: float


def confusion_matrix(
    gt: LabelMask,
    pred: LabelMask,
    n: int = 3,
) -> ConfusionMatrix:
    """
    Rows = ground truth, columns = prediction.

    Pixels whose ground truth is ``IGNORE`` (255) are skipped.
    """
    g = gt.ravel().astype(np.int64)
    p = pred.ravel().astype(np.int64)
    keep = g != IGNORE

    counts = np.bincount(g[keep] * n + p[keep], minlength=n * n)

    return counts.reshape(n, n).astype(np.int64)


def metrics_from_cm(cm: ConfusionMatrix) -> Metrics:
    """Per-class IoU, precision and recall from a confusion matrix."""
    tp = np.diag(cm).astype(np.float64)
    fp = cm.sum(axis=0) - tp
    fn = cm.sum(axis=1) - tp

    iou = tp / (tp + fp + fn + EPS)
    precision = tp / (tp + fp + EPS)
    recall = tp / (tp + fn + EPS)

    return {
        "iou": iou.round(4).tolist(),
        "precision": precision.round(4).tolist(),
        "recall": recall.round(4).tolist(),
        "mean_iou_all": round(float(iou.mean()), 4),
        "mean_iou_crop_weed": round(float(iou[1:].mean()), 4),
    }
