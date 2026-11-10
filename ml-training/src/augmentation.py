import random
import cv2
import numpy as np


class SegmentationAugmentation:
    def __init__(
        self,
        horizontal_flip_prob=0.5,
        vertical_flip_prob=0.5,
        rotation_prob=0.5,
        brightness_contrast_prob=0.5
    ):
        self.horizontal_flip_prob = horizontal_flip_prob
        self.vertical_flip_prob = vertical_flip_prob
        self.rotation_prob = rotation_prob
        self.brightness_contrast_prob = brightness_contrast_prob

    def __call__(self, image, mask):

        # Random horizontal flip
        if random.random() < self.horizontal_flip_prob:
            image = cv2.flip(image, 1)
            mask = cv2.flip(mask, 1)

        # Random vertical flip
        if random.random() < self.vertical_flip_prob:
            image = cv2.flip(image, 0)
            mask = cv2.flip(mask, 0)

        # Random rotation between -15 and +15 degrees
        if random.random() < self.rotation_prob:
            height, width = image.shape[:2]

            angle = random.uniform(-15, 15)

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

        # Random brightness and contrast adjustment
        if random.random() < self.brightness_contrast_prob:
            alpha = random.uniform(0.8, 1.2)  # Contrast
            beta = random.uniform(-0.1, 0.1)  # Brightness

            image = image * alpha + beta
            image = np.clip(image, 0.0, 1.0)

        return image.astype(np.float32), mask.astype(np.uint8)