import io
from typing import cast

import cv2
from PIL import Image

from .engine_types import BinaryMask, RGBImage


def resize_to_width(
    rgb: RGBImage,
    width: int,
) -> RGBImage:
    h, w = rgb.shape[:2]

    if w <= width:
        return rgb

    new_height = max(1, round(h * width / w))

    resized = cv2.resize(
        rgb,
        (width, new_height),
        interpolation=cv2.INTER_AREA,
    )

    return cast("RGBImage", resized)


def resize_mask_nearest(
    mask: BinaryMask,
    size_wh: tuple[int, int],
) -> BinaryMask:
    resized = cv2.resize(
        mask,
        size_wh,
        interpolation=cv2.INTER_NEAREST,
    )

    return cast("BinaryMask", resized)


def encode_jpeg(
    rgb: RGBImage,
    quality: int = 90,
) -> bytes:
    buffer = io.BytesIO()

    Image.fromarray(rgb).save(
        buffer,
        format="JPEG",
        quality=quality,
    )

    return buffer.getvalue()
