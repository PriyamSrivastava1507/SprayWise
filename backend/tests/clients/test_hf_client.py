"""Checks HFSegformerClient end to end WITHOUT a trained model or network access:
it builds a tiny randomly-initialised SegFormer, saves it to a local folder and
loads it back through the client (the same path as HF_MODEL_ID=./some/folder).

Skipped automatically when torch / transformers are not installed.
"""

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

from transformers import (  # noqa: E402
    SegformerConfig,
    SegformerForSemanticSegmentation,
    SegformerImageProcessor,
)

from app.clients.segmentation_hf import HFSegformerClient  # noqa: E402


def save_tiny_model(folder, num_labels: int) -> str:
    import torch

    torch.manual_seed(0)
    config = SegformerConfig(
        num_labels=num_labels,
        depths=[1, 1, 1, 1],
        hidden_sizes=[8, 16, 32, 64],
        num_attention_heads=[1, 1, 2, 2],
        decoder_hidden_size=32,
    )
    SegformerForSemanticSegmentation(config).save_pretrained(folder)
    SegformerImageProcessor(do_resize=True, size={"height": 64, "width": 64}).save_pretrained(
        folder
    )
    return str(folder)


@pytest.mark.parametrize("size", [(48, 64), (100, 100), (97, 131), (200, 150)])
def test_output_matches_input_size_dtype_and_classes(tmp_path, size):
    client = HFSegformerClient(save_tiny_model(tmp_path, num_labels=3))
    rgb = np.random.default_rng(0).integers(0, 256, (*size, 3), dtype=np.uint8)

    mask = client.predict(rgb)

    assert client.is_ready() and client.backend == "hf"
    assert mask.dtype == np.uint8
    assert mask.shape == size
    assert set(np.unique(mask)).issubset({0, 1, 2})


def test_model_with_the_wrong_number_of_classes_is_refused(tmp_path):
    with pytest.raises(ValueError, match="expected 3"):
        HFSegformerClient(save_tiny_model(tmp_path, num_labels=5))
