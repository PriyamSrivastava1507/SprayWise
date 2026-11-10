"""Shared test helpers: image bytes and a recording fake storage."""

import io

import numpy as np
from PIL import Image

from tests.engine.synthetic import make_fallow, make_field


def to_bytes(rgb: np.ndarray, fmt: str = "JPEG", exif_orientation: int | None = None) -> bytes:
    buffer = io.BytesIO()
    image = Image.fromarray(rgb)
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        image.save(buffer, format=fmt, exif=exif)
    else:
        image.save(buffer, format=fmt)
    return buffer.getvalue()


def field_photo(fmt: str = "JPEG") -> bytes:
    rgb, _ = make_field()
    return to_bytes(rgb, fmt)


def fallow_photo() -> bytes:
    rgb, _ = make_fallow()
    return to_bytes(rgb)
