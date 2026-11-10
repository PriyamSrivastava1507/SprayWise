"""Extra checks for the client layer: failure reasons, safer storage, blank tokens."""

import numpy as np
import pytest

from app.clients import (
    FakeSegmentationClient,
    LocalStorageClient,
    UnavailableSegmentationClient,
    build_segmentation_client,
)
from app.core.config import Settings
from app.core.exceptions import ModelUnavailableError


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def photo() -> np.ndarray:
    rgb = np.zeros((60, 80, 3), np.uint8)
    rgb[:] = (122, 92, 62)
    rgb[10:30, 10:30] = (50, 150, 50)
    return rgb


# ---- storage -------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path):
    return LocalStorageClient(tmp_path / "media")


@pytest.mark.parametrize("key", ["../evil.txt", "scans/../../evil.txt", "/etc/passwd", "", "."])
def test_storage_rejects_keys_that_escape_or_equal_the_root(storage, key):
    for call in (
        lambda: storage.save(key, b"x"),
        lambda: storage.read(key),
        lambda: storage.delete(key),
        lambda: storage.url(key),
    ):
        with pytest.raises(ValueError, match="bad storage key"):
            call()


def test_storage_overwrite_leaves_no_temp_file(storage):
    storage.save("scans/a/x.png", b"one")
    storage.save("scans/a/x.png", b"two")

    assert storage.read("scans/a/x.png") == b"two"
    assert [p.name for p in (storage.root / "scans" / "a").iterdir()] == ["x.png"]


def test_storage_delete_removes_the_empty_scan_folder_but_not_the_root(storage):
    storage.save("scans/abc/original.jpg", b"a")
    storage.save("scans/abc/classical_overlay.png", b"b")

    storage.delete("scans/abc/original.jpg")
    assert (storage.root / "scans" / "abc").exists()  # overlay still there

    storage.delete("scans/abc/classical_overlay.png")
    assert not (storage.root / "scans" / "abc").exists()
    assert storage.root.exists()


# ---- unavailable client: always says why --------------------------------------------


def test_unavailable_client_always_has_a_reason():
    default = UnavailableSegmentationClient(model_id="m")
    assert default.backend == "unavailable" and default.detail
    with pytest.raises(ModelUnavailableError, match="not loaded or is offline"):
        default.predict(photo())

    custom = UnavailableSegmentationClient(model_id="m", detail="switched off")
    assert custom.detail == "switched off"
    with pytest.raises(ModelUnavailableError, match="switched off"):
        custom.predict(photo())


def test_factory_unavailable_mode_explains_itself():
    client = build_segmentation_client(settings(segmentation_backend="unavailable"))

    assert not client.is_ready()
    assert "SEGMENTATION_BACKEND=unavailable" in (client.detail or "")


def test_factory_hf_load_failure_falls_back_with_a_short_reason():
    client = build_segmentation_client(
        settings(segmentation_backend="hf", hf_model_id="/definitely/not/a/model")
    )

    assert client.backend == "unavailable" and not client.is_ready()
    assert (client.detail or "").startswith("Could not load the ML model")
    assert len(client.detail or "") < 300


def test_fake_client_reports_backend_and_no_detail():
    client = FakeSegmentationClient()

    assert client.backend == "fake" and client.detail is None


# ---- config ---------------------------------------------------------------------------


def test_blank_hf_token_becomes_none():
    assert settings(hf_token="").hf_token is None
    assert settings(hf_token="  ").hf_token is None
    assert settings(hf_token="hf_abc").hf_token == "hf_abc"
