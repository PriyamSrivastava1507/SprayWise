import numpy as np
import cv2


class SegmentationPreprocessor:
    def __init__(self, image_size=(512, 512)):
        self.image_size = image_size

        self.mean = np.array(
            [0.485, 0.456, 0.406], dtype=np.float32
        )

        self.std = np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )

    def resize_and_pad(self, image, is_mask=False):
        target_h, target_w = self.image_size
        original_h, original_w = image.shape[:2]

        scale = min(
            target_w / original_w,
            target_h / original_h
        )

        new_w = int(round(original_w * scale))
        new_h = int(round(original_h * scale))

        interpolation = (
            cv2.INTER_NEAREST if is_mask
            else cv2.INTER_LINEAR
        )

        resized = cv2.resize(
            image,
            (new_w, new_h),
            interpolation=interpolation
        )

        pad_h = target_h - new_h
        pad_w = target_w - new_w

        top = pad_h // 2
        bottom = pad_h - top
        left = pad_w // 2
        right = pad_w - left

        if is_mask:
            padded = cv2.copyMakeBorder(
                resized,
                top, bottom, left, right,
                cv2.BORDER_CONSTANT,
                value=255
            )
        else:
            padded = cv2.copyMakeBorder(
                resized,
                top, bottom, left, right,
                cv2.BORDER_REFLECT_101
            )

        return padded

    def preprocess_image(self, image):
        image = self.resize_and_pad(image)

        image = image.astype(np.float32)
        image = (image - self.mean) / self.std

        return image

    def preprocess_mask(self, mask):
        mask = self.resize_and_pad(mask, is_mask=True)
        return mask.astype(np.uint8)

    def __call__(self, image, mask):
        image = self.preprocess_image(image)
        mask = self.preprocess_mask(mask)

        return image, mask