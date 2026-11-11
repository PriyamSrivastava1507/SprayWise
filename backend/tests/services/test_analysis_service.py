import numpy as np
import pytest

from app.clients import LocalStorageClient
from app.clients.factory import UnavailableSegmentationClient
from app.clients.segmentation_fake import FakeSegmentationClient
from app.core.config import Settings
from app.core.exceptions import InvalidImageError, ModelUnavailableError, NotFoundError
from app.repositories.field_repository import FieldRepository
from app.repositories.scan_repository import ScanRepository
from app.schemas.analysis import AnalyzeParams
from app.services.analysis_service import AnalysisService
from tests.helpers import fallow_photo, field_photo, to_bytes


class BrokenSegmenter(FakeSegmentationClient):
    def predict(self, rgb):
        raise RuntimeError("boom")


class BadShapeSegmenter(FakeSegmentationClient):
    def predict(self, rgb):
        return np.zeros((3, 3), np.uint8)


@pytest.fixture
def storage(tmp_path):
    return LocalStorageClient(root=str(tmp_path))


def make_service(db, storage, segmenter=None):
    from app.clients.registry import ModelRegistry

    return AnalysisService(
        scans=ScanRepository(db),
        fields=FieldRepository(db),
        storage=storage,
        models=ModelRegistry.single(segmenter or FakeSegmentationClient()),
        settings=Settings(),
    )


def files_under(path):
    return [p for p in path.rglob("*") if p.is_file()]


def test_classical_success(db, storage, tmp_path):
    scan = make_service(db, storage).analyze(field_photo(), AnalyzeParams(mode="classical"))
    assert scan.mode == "classical"
    assert len(scan.results) == 1
    result = scan.results[0]
    assert result.status == "ok" and result.method == "classical"
    assert 0 <= result.weed_pct <= 100
    assert len(result.grid) == 8 and len(result.grid[0]) == 8
    assert result.savings.saved_pct is not None
    assert result.overlay_url.startswith("/media/")
    assert len(files_under(tmp_path)) == 3  # original + overlay + mask


def test_no_rows_is_a_result_not_an_error(db, storage):
    scan = make_service(db, storage).analyze(fallow_photo(), AnalyzeParams(mode="classical"))
    result = scan.results[0]
    assert result.status == "rows_not_detected"
    assert result.status_detail
    assert result.weed_pct is None and result.overlay_url is None
    assert result.savings.saved_pct is None


def test_ml_mode_with_fake_model(db, storage):
    scan = make_service(db, storage).analyze(field_photo(), AnalyzeParams(mode="ml"))
    result = scan.results[0]
    assert result.status == "ok" and result.model_id == "fake-demo-model"


def test_compare_runs_both(db, storage):
    scan = make_service(db, storage).analyze(field_photo(), AnalyzeParams(mode="compare"))
    assert [r.method for r in scan.results] == ["classical", "ml"]
    assert all(r.status == "ok" for r in scan.results)


def test_compare_keeps_classical_when_ml_unavailable(db, storage):
    service = make_service(db, storage, UnavailableSegmentationClient())
    scan = service.analyze(field_photo(), AnalyzeParams(mode="compare"))
    by_method = {r.method: r for r in scan.results}
    assert by_method["classical"].status == "ok"
    assert by_method["ml"].status == "model_unavailable"
    assert by_method["ml"].status_detail


def test_ml_only_unavailable_raises_and_writes_nothing(db, storage, tmp_path):
    service = make_service(db, storage, UnavailableSegmentationClient())
    with pytest.raises(ModelUnavailableError):
        service.analyze(field_photo(), AnalyzeParams(mode="ml"))
    assert files_under(tmp_path) == []
    assert ScanRepository(db).count(None) == 0


def test_ml_crash_in_compare_is_failed_result(db, storage):
    service = make_service(db, storage, BrokenSegmenter())
    scan = service.analyze(field_photo(), AnalyzeParams(mode="compare"))
    by_method = {r.method: r for r in scan.results}
    assert by_method["classical"].status == "ok"
    assert by_method["ml"].status == "failed"


def test_ml_crash_in_ml_mode_propagates(db, storage, tmp_path):
    service = make_service(db, storage, BrokenSegmenter())
    with pytest.raises(RuntimeError):
        service.analyze(field_photo(), AnalyzeParams(mode="ml"))
    assert files_under(tmp_path) == []  # cleaned up


def test_invalid_model_output_is_failed(db, storage):
    service = make_service(db, storage, BadShapeSegmenter())
    scan = service.analyze(field_photo(), AnalyzeParams(mode="compare"))
    ml = next(r for r in scan.results if r.method == "ml")
    assert ml.status == "failed" and ml.status_detail == "invalid_model_output"


@pytest.mark.parametrize("payload", [b"", b"not an image", b"GIF89a" + b"\x00" * 50])
def test_invalid_bytes_rejected(db, storage, tmp_path, payload):
    with pytest.raises(InvalidImageError):
        make_service(db, storage).analyze(payload, AnalyzeParams())
    assert files_under(tmp_path) == []


def test_png_accepted(db, storage):
    scan = make_service(db, storage).analyze(field_photo("PNG"), AnalyzeParams())
    assert scan.results[0].status == "ok"


def test_exif_orientation_is_applied(db, storage):
    rgb = np.zeros((100, 200, 3), np.uint8)
    rgb[:] = (122, 92, 62)
    scan = make_service(db, storage).analyze(
        to_bytes(rgb, exif_orientation=6),  # rotate 90 degrees
        AnalyzeParams(),
    )
    assert (scan.width, scan.height) == (100, 200)


def test_large_photo_is_resized_to_working_width(db, storage):
    rgb = np.zeros((600, 2000, 3), np.uint8)
    rgb[:] = (122, 92, 62)
    scan = make_service(db, storage).analyze(to_bytes(rgb), AnalyzeParams())
    assert scan.width == 1024


def test_db_failure_deletes_files(db, storage, tmp_path):
    service = make_service(db, storage)

    def explode(_scan):
        raise RuntimeError("db down")

    service.scans.add = explode  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        service.analyze(field_photo(), AnalyzeParams())
    assert files_under(tmp_path) == []


def test_field_resolution(db, storage):
    service = make_service(db, storage)
    first = service.analyze(field_photo(), AnalyzeParams(field_name="North"))
    second = service.analyze(field_photo(), AnalyzeParams(field_name="North"))
    assert first.field.id == second.field.id and first.field.name == "North"

    by_id = service.analyze(field_photo(), AnalyzeParams(field_id=first.field.id))
    assert by_id.field.name == "North"

    anonymous = service.analyze(field_photo(), AnalyzeParams())
    assert anonymous.field is None


def test_field_id_wins_over_name(db, storage):
    service = make_service(db, storage)
    north = service.analyze(field_photo(), AnalyzeParams(field_name="North")).field
    scan = service.analyze(field_photo(), AnalyzeParams(field_id=north.id, field_name="South"))
    assert scan.field.name == "North"
    assert FieldRepository(db).get_by_name("South") is None


def test_unknown_field_id_is_not_found(db, storage, tmp_path):
    with pytest.raises(NotFoundError):
        make_service(db, storage).analyze(field_photo(), AnalyzeParams(field_id=999))
    assert files_under(tmp_path) == []


@pytest.mark.parametrize(
    "bad",
    [
        {"area_ha": 0},
        {"area_ha": float("nan")},
        {"dose_l_per_ha": -1},
        {"grid_rows": 1},
        {"grid_cols": 33},
        {"cell_threshold": 0},
        {"cell_threshold": 1},
        {"mode": "bogus"},
        {"field_name": "x" * 121},
    ],
)
def test_param_validation(bad):
    with pytest.raises(ValueError):
        AnalyzeParams(**bad)


def test_blank_form_values_mean_not_given():
    params = AnalyzeParams(field_id="", field_name="  ")
    assert params.field_id is None and params.field_name is None
