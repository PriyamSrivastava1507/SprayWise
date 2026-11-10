"""Contract test for the REAL ML model. Run it once your teammate's model is available:

    RUN_ML_TESTS=1 HF_MODEL_ID=user/cropweed-segformer-b0 python -m pytest tests/contracts -q
    RUN_ML_TESTS=1 HF_MODEL_ID=./path/to/best_model      python -m pytest tests/contracts -q

HF_MODEL_ID may be a Hub ID or a local folder holding the model AND the processor.
"""

import os

import numpy as np
import pytest

from app.clients.factory import build_segmentation_client
from app.core.config import Settings

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_ML_TESTS") != "1", reason="set RUN_ML_TESTS=1 to run"
)

SIZES = [(480, 640), (300, 300), (768, 1024), (97, 131), (640, 480)]


@pytest.fixture(scope="module")
def client():
    loaded = build_segmentation_client(Settings(segmentation_backend="hf"))
    assert loaded.is_ready(), f"model did not load: {loaded.detail}"
    return loaded


@pytest.mark.parametrize("size", SIZES)
def test_real_model_meets_the_mask_contract(client, size):
    rgb = np.random.default_rng(1).integers(0, 256, (*size, 3), dtype=np.uint8)

    mask = client.predict(rgb)

    assert mask.dtype == np.uint8
    assert mask.shape == size
    assert set(np.unique(mask)).issubset({0, 1, 2})  # 255 must never appear in output
