"""Data access for fields. No business rules: a missing row is None, and the
service decides what that means."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Field


class FieldRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, field_id: int) -> Field | None:
        return self.db.get(Field, field_id)

    def get_by_name(self, name: str) -> Field | None:
        return self.db.scalar(select(Field).where(Field.name == name))

    def list(self) -> list[Field]:
        return list(self.db.scalars(select(Field).order_by(Field.name)))

    def create(self, name: str) -> Field:
        """Insert a field. Raises IntegrityError if the name already exists
        (the session is rolled back first, so it stays usable)."""
        field = Field(name=name)
        self.db.add(field)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
        self.db.refresh(field)
        return field
