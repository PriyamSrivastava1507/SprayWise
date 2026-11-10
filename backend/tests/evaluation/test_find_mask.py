"""The evaluation script must pair images with masks under the project's naming."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scripts.evaluate import evaluate, find_mask


def touch(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_bytes(b"x")
    return path


@pytest.mark.parametrize(
    ("image_name", "mask_name"),
    [
        ("photo.jpg", "photo.png"),  # same name
        ("001_image.png", "001_mask.png"),  # shared test-dataset convention
        ("field7.jpg", "field7_mask.png"),  # <stem>_mask
    ],
)
def test_find_mask_supported_names(tmp_path, image_name, mask_name):
    images, masks = tmp_path / "images", tmp_path / "masks"
    images.mkdir()
    masks.mkdir()
    image = touch(images, image_name)
    expected = touch(masks, mask_name)

    assert find_mask(masks, image) == expected


def test_find_mask_returns_none_when_missing(tmp_path):
    (tmp_path / "masks").mkdir()

    assert find_mask(tmp_path / "masks", tmp_path / "001_image.png") is None


def test_evaluate_pairs_the_shared_dataset_naming(tmp_path):
    images, masks = tmp_path / "images", tmp_path / "masks"
    images.mkdir()
    masks.mkdir()

    rgb = np.zeros((40, 60, 3), np.uint8)
    rgb[:] = (122, 92, 62)
    gt = np.zeros((40, 60), np.uint8)
    Image.fromarray(rgb).save(images / "001_image.png")
    Image.fromarray(gt).save(masks / "001_mask.png")

    result = evaluate(images, masks, lambda image: np.zeros(image.shape[:2], np.uint8))

    assert result["n_images"] == 1
