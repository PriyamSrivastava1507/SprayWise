import torch
import torch.nn as nn

from transformers import (
    SegformerConfig,
    SegformerForSemanticSegmentation
)


ID2LABEL = {
    0: "background",
    1: "crop",
    2: "weed"
}

LABEL2ID = {
    "background": 0,
    "crop": 1,
    "weed": 2
}

PRETRAINED_MODEL = "nvidia/mit-b0"
IGNORE_INDEX = 255


def build_model():
    config = SegformerConfig.from_pretrained(PRETRAINED_MODEL)

    config.num_labels = 3
    config.id2label = ID2LABEL
    config.label2id = LABEL2ID

    model = SegformerForSemanticSegmentation.from_pretrained(
        PRETRAINED_MODEL,
        config=config,
        ignore_mismatched_sizes=True
    )

    return model


def build_loss(class_weights=None):
    if class_weights is not None:
        class_weights = torch.tensor(
            class_weights,
            dtype=torch.float32
        )

    criterion = nn.CrossEntropyLoss(
        weight=class_weights,
        ignore_index=IGNORE_INDEX
    )

    return criterion