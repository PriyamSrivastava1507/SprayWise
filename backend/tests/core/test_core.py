from datetime import datetime, timedelta, timezone

UTC = timezone.utc

from app.core.config import Settings
from app.models import Field


def test_created_at_is_timezone_aware_utc_after_reload(db):
    field = Field(name="North plot")
    db.add(field)
    db.commit()
    db.expire_all()

    loaded = db.get(Field, field.id)

    assert loaded.created_at.tzinfo is not None
    assert loaded.created_at.utcoffset() == timedelta(0)
    assert loaded.created_at.isoformat().endswith("+00:00")


def test_non_utc_datetime_is_normalised_to_utc(db):
    ist = timezone(timedelta(hours=5, minutes=30))
    stamp = datetime(2026, 11, 10, 20, 0, tzinfo=ist)

    field = Field(name="IST plot", created_at=stamp)
    db.add(field)
    db.commit()
    db.expire_all()

    assert db.get(Field, field.id).created_at == datetime(2026, 11, 10, 14, 30, tzinfo=UTC)


def test_blank_hf_token_becomes_none():
    assert Settings(hf_token="", _env_file=None).hf_token is None
    assert Settings(hf_token="  ", _env_file=None).hf_token is None
    assert Settings(hf_token="hf_abc", _env_file=None).hf_token == "hf_abc"
