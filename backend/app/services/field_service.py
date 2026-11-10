"""Fields (farm plots) and their weed trend."""

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.field_repository import FieldRepository
from app.repositories.scan_repository import ScanRepository
from app.schemas.field import FieldOut, TrendPoint, TrendResponse


def _out(field) -> FieldOut:
    return FieldOut(id=field.id, name=field.name, created_at=field.created_at)


class FieldService:
    def __init__(self, fields: FieldRepository, scans: ScanRepository):
        self.fields = fields
        self.scans = scans

    def list(self) -> list[FieldOut]:
        return [_out(f) for f in self.fields.list()]

    def get(self, field_id: int) -> FieldOut:
        return _out(self._require(field_id))

    def create(self, name: str) -> FieldOut:
        if self.fields.get_by_name(name):
            raise ConflictError(f"A field named '{name}' already exists.")
        try:
            return _out(self.fields.create(name))
        except IntegrityError:  # lost a race with another request
            raise ConflictError(f"A field named '{name}' already exists.") from None

    def trend(self, field_id: int, method: str) -> TrendResponse:
        field = self._require(field_id)
        points = [
            TrendPoint(
                scan_id=row.scan_id,
                created_at=row.created_at,
                weed_pct=row.weed_pct,
                saved_pct=row.saved_pct,
            )
            for row in self.scans.trend(field_id, method)
        ]
        return TrendResponse(field=_out(field), method=method, points=points)  # type: ignore[arg-type]

    def _require(self, field_id: int):
        field = self.fields.get(field_id)
        if field is None:
            raise NotFoundError(f"Field {field_id} does not exist.")
        return field
