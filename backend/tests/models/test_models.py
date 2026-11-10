import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.database import Base
from app.core.enums import Method, Mode, ResultStatus
from app.models import Field, Scan, ScanResult


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def make_scan(**overrides) -> Scan:
    values = dict(
        mode=Mode.COMPARE, original_key="scans/abc/original.jpg", width=1024, height=768,
        area_ha=2.5, dose_l_per_ha=2.0, price_per_l=10.0,
        grid_rows=8, grid_cols=8, cell_threshold=0.1,
    )
    values.update(overrides)
    return Scan(**values)


def test_scan_with_two_results_round_trips(db):
    field = Field(name="North plot")
    scan = make_scan(field=field)
    scan.results.append(ScanResult(
        method=Method.CLASSICAL, status=ResultStatus.OK, weed_pct=8.8,
        grid=[[0.0, 0.12]], spray_cells=[[0, 1]],
    ))
    scan.results.append(ScanResult(
        method=Method.ML, status=ResultStatus.MODEL_UNAVAILABLE,
        status_detail="model not loaded",
    ))
    db.add(scan)
    db.commit()
    db.expire_all()

    loaded = db.get(Scan, scan.id)
    assert loaded.created_at is not None and loaded.field.name == "North plot"
    assert [r.method for r in loaded.results] == ["classical", "ml"]
    assert loaded.results[0].grid == [[0.0, 0.12]]
    assert loaded.results[0].spray_cells == [[0, 1]]
    assert loaded.results[1].weed_pct is None  # not-ok results keep stats NULL
    assert loaded.results[1].status_detail == "model not loaded"


def test_field_names_are_unique(db):
    db.add(Field(name="A"))
    db.commit()
    db.add(Field(name="A"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_one_result_per_method_per_scan(db):
    scan = make_scan()
    scan.results.append(ScanResult(method=Method.ML, status=ResultStatus.OK))
    scan.results.append(ScanResult(method=Method.ML, status=ResultStatus.OK))
    db.add(scan)
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_a_scan_deletes_its_results(db):
    scan = make_scan(mode=Mode.CLASSICAL)
    scan.results.append(ScanResult(method=Method.CLASSICAL, status=ResultStatus.OK))
    db.add(scan)
    db.commit()

    db.delete(scan)
    db.commit()

    assert db.scalar(select(func.count(ScanResult.id))) == 0
