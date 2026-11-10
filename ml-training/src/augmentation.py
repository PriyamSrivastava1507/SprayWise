import random
import cv2
import numpy as np


class SegmentationAugmentation:
    def __init__(
        self,
        horizontal_flip_prob=0.5,
        vertical_flip_prob=0.1,
        rotation_prob=0.5,
        brightness_contrast_prob=0.5
    ):
        self.horizontal_flip_prob = horizontal_flip_prob
        self.vertical_flip_prob = vertical_flip_prob
        self.rotation_prob = rotation_prob
        self.brightness_contrast_prob = brightness_contrast_prob

    def __call__(self, image, mask):

        # Horizontal flip
        if random.random() < self.horizontal_flip_prob:
            image = cv2.flip(image, 1)
            mask = cv2.flip(mask, 1)

        # Occasional vertical flip
        if random.random() < self.vertical_flip_prob:
            image = cv2.flip(image, 0)
            mask = cv2.flip(mask, 0)

        # Rotation between -10 and +10 degrees
        if random.random() < self.rotation_prob:
            height, width = image.shape[:2]

            angle = random.uniform(-10, 10)

            matrix = cv2.getRotationMatrix2D(
                (width / 2, height / 2),
                angle,
                1.0
            )

            image = cv2.warpAffine(
                image,
                matrix,
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101
            )

            mask = cv2.warpAffine(
                mask,
                matrix,
                (width, height),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255
            )

        # Brightness and contrast
        if random.random() < self.brightness_contrast_prob:
            alpha = random.uniform(0.9, 1.1)
            beta = random.uniform(-0.05, 0.05)

            image = image * alpha + beta
            image = np.clip(image, 0.0, 1.0)

        return image.astype(np.float32), mask.astype(np.uint8)