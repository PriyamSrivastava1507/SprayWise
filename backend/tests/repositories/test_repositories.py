from datetime import datetime, timedelta, timezone

UTC = timezone.utc

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.enums import Method, Mode, ResultStatus
from app.models import Field, Scan, ScanResult
from app.repositories.field_repository import FieldRepository
from app.repositories.scan_repository import ScanRepository


def make_scan(field=None, mode=Mode.CLASSICAL, created_at=None, **results) -> Scan:
    """results: method -> (status, weed_pct, saved_pct)"""
    scan = Scan(
        mode=mode, original_key="scans/x/original.jpg", width=100, height=80,
        area_ha=1.0, dose_l_per_ha=2.0, price_per_l=10.0,
        grid_rows=8, grid_cols=8, cell_threshold=0.1,
    )
    if field is not None:
        scan.field = field
    if created_at is not None:
        scan.created_at = created_at
    for method, (status, weed, saved) in results.items():
        scan.results.append(
            ScanResult(method=method, status=status, weed_pct=weed, saved_pct=saved)
        )
    return scan


# ---- fields -----------------------------------------------------------------

def test_field_create_get_and_list_sorted_by_name(db):
    repo = FieldRepository(db)
    b, a = repo.create("Bravo"), repo.create("Alpha")

    assert repo.get(a.id).name == "Alpha"
    assert repo.get(999) is None
    assert repo.get_by_name("Bravo").id == b.id
    assert repo.get_by_name("nope") is None
    assert [f.name for f in repo.list()] == ["Alpha", "Bravo"]


def test_duplicate_field_name_raises_and_session_stays_usable(db):
    repo = FieldRepository(db)
    repo.create("North")

    with pytest.raises(IntegrityError):
        repo.create("North")

    assert repo.create("South").name == "South"  # rolled back, not stuck


# ---- scans ------------------------------------------------------------------

def test_add_and_get_returns_results_and_field(db):
    field = FieldRepository(db).create("North")
    repo = ScanRepository(db)
    scan = repo.add(make_scan(
        field, Mode.COMPARE,
        classical=(ResultStatus.OK, 8.8, 64.0), ml=(ResultStatus.MODEL_UNAVAILABLE, None, None),
    ))

    db.expire_all()
    loaded = repo.get(scan.id)

    assert loaded.field.name == "North"
    assert [r.method for r in loaded.results] == ["classical", "ml"]
    assert repo.get(999) is None


def test_failed_add_rolls_back_so_the_session_is_usable(db):
    repo = ScanRepository(db)
    bad = make_scan(
        classical=(ResultStatus.OK, 1.0, 1.0)
    )
    bad.results.append(ScanResult(method=Method.CLASSICAL, status=ResultStatus.OK))  # duplicate

    with pytest.raises(IntegrityError):
        repo.add(bad)

    assert repo.count(None) == 0
    repo.add(make_scan(classical=(ResultStatus.OK, 1.0, 1.0)))
    assert repo.count(None) == 1


def test_list_is_newest_first_with_paging_and_field_filter(db):
    fields = FieldRepository(db)
    north, south = fields.create("North"), fields.create("South")
    repo = ScanRepository(db)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        repo.add(make_scan(north if i < 3 else south, created_at=t0 + timedelta(days=i)))

    everything = repo.list(None, limit=10, offset=0)
    assert [s.created_at.day for s in everything] == [5, 4, 3, 2, 1]
    assert [s.created_at.day for s in repo.list(None, limit=2, offset=1)] == [4, 3]

    only_north = repo.list(north.id, limit=10, offset=0)
    assert len(only_north) == 3 and all(s.field_id == north.id for s in only_north)
    assert repo.count(None) == 5 and repo.count(north.id) == 3 and repo.count(12345) == 0


def test_delete_removes_the_scan_and_its_results(db):
    repo = ScanRepository(db)
    scan = repo.add(make_scan(classical=(ResultStatus.OK, 1.0, 1.0), ml=(ResultStatus.OK, 2.0, 2.0)))

    repo.delete(scan)

    assert repo.get(scan.id) is None
    assert db.scalar(select(func.count(ScanResult.id))) == 0


def test_trend_follows_one_method_in_time_order_and_skips_failures(db):
    field = FieldRepository(db).create("North")
    other = FieldRepository(db).create("South")
    repo = ScanRepository(db)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)

    # added out of order on purpose
    repo.add(make_scan(field, created_at=t0 + timedelta(days=2),
                       classical=(ResultStatus.OK, 6.0, 50.0)))
    repo.add(make_scan(field, created_at=t0,
                       classical=(ResultStatus.OK, 9.0, 40.0)))
    repo.add(make_scan(field, Mode.COMPARE, created_at=t0 + timedelta(days=1),
                       classical=(ResultStatus.ROWS_NOT_DETECTED, None, None),
                       ml=(ResultStatus.OK, 7.5, 45.0)))
    repo.add(make_scan(other, created_at=t0, classical=(ResultStatus.OK, 99.0, 1.0)))

    classical = repo.trend(field.id, Method.CLASSICAL)
    assert [r.weed_pct for r in classical] == [9.0, 6.0]  # time order, failure skipped
    assert all(r.created_at.tzinfo is not None for r in classical)

    assert [r.weed_pct for r in repo.trend(field.id, "ml")] == [7.5]
    assert repo.trend(424242, Method.CLASSICAL) == []
