from __future__ import annotations

import importlib
import threading
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image


NUM_CLASSES = 3  # 0 soil, 1 crop, 2 weed


class HFSegformerClient:
    """Hugging Face SegFormer semantic segmentation client."""

    backend = "hf"
    detail: Optional[str] = None

    def __init__(self, model_id: str, token: Optional[str] = None) -> None:
        try:
            torch = importlib.import_module("torch")
            f_module = importlib.import_module("torch.nn.functional")
            transformers = importlib.import_module("transformers")
            segformer_cls = getattr(transformers, "SegformerForSemanticSegmentation")
            processor_cls = getattr(transformers, "SegformerImageProcessor")
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                "torch and transformers are required to use HFSegformerClient"
            ) from exc

        self.model_id = model_id
        self._lock = threading.Lock()
        self._torch: Any = torch
        self._F: Any = f_module

        # A token only makes sense for the Hub, not for a local folder; a blank
        # token must never reach the Hub as if it were a real one.
        hub_token = None if Path(model_id).is_dir() else (token or None)

        self._proc: Any = processor_cls.from_pretrained(model_id, token=hub_token)
        self._model: Any = segformer_cls.from_pretrained(
            model_id, token=hub_token
        ).eval()

        # Refuse a model that breaks the 3-class contract instead of serving
        # masks with class ids the rest of the app does not understand.
        num_labels = self._model.config.num_labels
        if num_labels != NUM_CLASSES:
            raise ValueError(f"Model has {num_labels} classes, expected {NUM_CLASSES}")

    def is_ready(self) -> bool:
        return True

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        inputs = self._proc(images=Image.fromarray(rgb), return_tensors="pt")
        with self._lock, self._torch.no_grad():
            logits = self._model(**inputs).logits
            logits = self._F.interpolate(
                logits,
                size=rgb.shape[:2],
                mode="bilinear",
                align_corners=False,
            )
            prediction = logits.argmax(1)[0].cpu().numpy().astype(np.uint8)
            return prediction
