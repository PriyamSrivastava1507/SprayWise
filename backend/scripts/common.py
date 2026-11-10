"""Helpers shared by the command-line scripts."""

from contextlib import closing
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

from app.engine import resize_to_width

RGB = NDArray[np.uint8]  # (H, W, 3)
Labels = NDArray[np.uint8]  # (H, W): 0 soil, 1 crop, 2 weed

IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png"})
DEFAULT_WIDTH = 1024  # working width, the same one the app uses


def list_images(folder: Path) -> list[Path]:
    """Return the image files in ``folder``, sorted by name."""
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )


def load_rgb(path: Path, width: int = DEFAULT_WIDTH) -> RGB:
    """
    Decode a photo exactly as the app does.

    RGB order (not BGR), EXIF orientation applied, then downscaled to the
    working width. Scripts and production must agree on this step.
    """
    # closing() instead of ``with Image.open(...)``: type checkers on Python 3.10
    # lose the type of Pillow's own context manager.
    with closing(Image.open(path)) as image:
        rgb = np.asarray(
            ImageOps.exif_transpose(image).convert("RGB"),
            dtype=np.uint8,
        )

    return resize_to_width(rgb, width)
