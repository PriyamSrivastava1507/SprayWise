import numpy as np
import cv2


class SegmentationPreprocessor:
    def __init__(self, image_size=(512, 512)):
        """
        image_size: (height, width)
        """
        self.image_size = image_size

        # ImageNet normalization values
        self.mean = np.array(
            [0.485, 0.456, 0.406], dtype=np.float32
        )

        self.std = np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )

    def preprocess_image(self, image):
        """
        Resize, normalize and return an RGB image.

        Input: H x W x 3, values in [0, 1]
        Output: H x W x 3, normalized float32
        """

        height, width = self.image_size

        image = cv2.resize(
            image,
            (width, height),
            interpolation=cv2.INTER_LINEAR
        )

        image = image.astype(np.float32)

        image = (image - self.mean) / self.std

        return image

    def preprocess_mask(self, mask):
        """
        Resize segmentation mask without changing class IDs.

        Classes:
        0 = Background
        1 = Crop
        2 = Weed
        255 = Ignore
        """

        height, width = self.image_size

        mask = cv2.resize(
            mask,
            (width, height),
            interpolation=cv2.INTER_NEAREST
        )

        return mask.astype(np.uint8)

    def __call__(self, image, mask):
        image = self.preprocess_image(image)
        mask = self.preprocess_mask(mask)

        return image, mask