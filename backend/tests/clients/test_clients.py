from pathlib import Path
import numpy as np
import pytest

from app.clients import (
    FakeSegmentationClient,
    LocalStorageClient,
    UnavailableSegmentationClient,
    build_segmentation_client,
    build_storage_client,
)
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError
from app.engine.constants import CROP, SOIL, WEED


class TestLocalStorageClient:
    def test_save_read_url_delete(self, tmp_path: Path):
        client = LocalStorageClient(root=tmp_path)
        key = "scans/abc123/original.jpg"
        payload = b"dummy image payload"

        saved_key = client.save(key, payload)
        assert saved_key == key
        assert client.read(key) == payload
        assert client.url(key) == "/media/scans/abc123/original.jpg"

        client.delete(key)
        assert not (tmp_path / key).exists()

        # Delete on non-existent file should not raise
        client.delete(key)

    def test_path_traversal_protection(self, tmp_path: Path):
        client = LocalStorageClient(root=tmp_path)

        with pytest.raises(ValueError, match="bad storage key"):
            client.save("../outside.txt", b"malicious")

        with pytest.raises(ValueError, match="bad storage key"):
            client.read("../../etc/passwd")

        with pytest.raises(ValueError, match="bad storage key"):
            client.url("../forbidden")


class TestFakeSegmentationClient:
    def test_contract_and_behavior(self):
        client = FakeSegmentationClient()
        assert client.model_id == "fake-demo-model"
        assert client.is_ready() is True

        # Create a 100x100 synthetic image with green vegetation across the width
        # Brown soil background
        rgb = np.full((100, 100, 3), (122, 92, 62), dtype=np.uint8)
        # Green patch from x=20 to x=80, y=40 to y=60
        rgb[40:60, 20:80] = (50, 180, 50)

        mask = client.predict(rgb)
        assert mask.shape == (100, 100)
        assert mask.dtype == np.uint8
        assert set(np.unique(mask)).issubset({SOIL, CROP, WEED})

        # Left half of green patch (x in 20..49) should be crop (1)
        assert np.all(mask[40:60, 20:50] == CROP)
        # Right half of green patch (x in 50..79) should be weed (2)
        assert np.all(mask[40:60, 50:80] == WEED)
        # Outside green patch should be soil (0)
        assert mask[0, 0] == SOIL


class TestUnavailableSegmentationClient:
    def test_behavior(self):
        client = UnavailableSegmentationClient(model_id="test-model")
        assert client.model_id == "test-model"
        assert client.is_ready() is False

        rgb = np.zeros((50, 50, 3), dtype=np.uint8)
        with pytest.raises(ModelUnavailableError, match="not loaded or is offline"):
            client.predict(rgb)


class TestFactory:
    def test_build_fake_client(self):
        settings = Settings(segmentation_backend="fake")
        client = build_segmentation_client(settings)
        assert isinstance(client, FakeSegmentationClient)

    def test_build_unavailable_client(self):
        settings = Settings(segmentation_backend="unavailable")
        client = build_segmentation_client(settings)
        assert isinstance(client, UnavailableSegmentationClient)

    def test_build_hf_fallback_on_missing_model_or_dependencies(self):
        settings = Settings(
            segmentation_backend="hf",
            hf_model_id="non-existent/model-path",
        )
        client = build_segmentation_client(settings)
        # Should gracefully return UnavailableSegmentationClient without raising an uncaught exception
        assert isinstance(client, UnavailableSegmentationClient)

    def test_build_storage_client(self, tmp_path: Path):
        settings = Settings(storage_dir=str(tmp_path))
        storage = build_storage_client(settings)
        assert isinstance(storage, LocalStorageClient)
        assert storage.root == tmp_path.resolve()

