
from pathlib import Path
import json

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset


class CWFIDataset(Dataset):
    def __init__(self, root_dir, split_file, split="train", transform=None):
        self.root_dir = Path(root_dir)
        self.transform = transform

        # Load train/validation/test IDs
        with open(split_file, "r") as f:
            split_data = json.load(f)

        if split not in split_data:
            raise ValueError(f"Invalid split: {split}")

        self.image_ids = split_data[split]

        self.image_dir = self.root_dir / "images"
        self.mask_dir = self.root_dir / "processed_masks"

    def __len__(self):
        return len(self.image_ids)

    def __getitem__(self, index):
        image_id = self.image_ids[index]

        image_path = self.image_dir / f"{image_id:03d}_image.png"
        mask_path = self.mask_dir / f"{image_id:03d}_mask.png"

        if not image_path.exists() or not mask_path.exists():
            raise FileNotFoundError(
                f"Missing image or mask for ID {image_id}"
            )

        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path)

        image = np.array(image, dtype=np.float32) / 255.0
        mask = np.array(mask, dtype=np.uint8)

        if self.transform is not None:
            image, mask = self.transform(image, mask)

        # HWC -> CHW
        image = torch.from_numpy(
            np.ascontiguousarray(image.transpose(2, 0, 1))
        ).float()

        mask = torch.from_numpy(
            np.ascontiguousarray(mask)
        ).long()

        return image, mask
