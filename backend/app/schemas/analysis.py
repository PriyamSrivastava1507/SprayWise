"""Request parameters for POST /analyze."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ScanSettings(BaseModel):
    """The numbers that turn a mask into zones and savings. Shared by
    POST /analyze and POST /scans/{id}/recalculate."""

    area_ha: float = Field(1.0, gt=0, allow_inf_nan=False)
    dose_l_per_ha: float = Field(2.0, ge=0, allow_inf_nan=False)
    price_per_l: float = Field(10.0, ge=0, allow_inf_nan=False)
    grid_rows: int = Field(8, ge=2, le=32)
    grid_cols: int = Field(8, ge=2, le=32)
    cell_threshold: float = Field(0.10, gt=0, lt=1, allow_inf_nan=False)


class AnalyzeParams(ScanSettings):
    """
    Form fields that accompany the uploaded photo.

    The defaults are placeholders: the UI should always send real values.
    Percentages are 0..100 elsewhere in the API, but ``cell_threshold`` is a
    fraction (0..1): a grid cell is sprayed when more than this share of its
    pixels are weed.
    """

    mode: Literal["classical", "ml", "compare"] = "classical"
    field_id: Optional[int] = None
    field_name: Optional[str] = Field(None, min_length=1, max_length=120)
    # ML models to run, by key (e.g. ["cwfid", "we3ds"]). Empty = the default model.
    models: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("models", mode="before")
    @classmethod
    def _split_models(cls, value: object) -> object:
        # Accept "cwfid,we3ds" (a form field) or a list; drop blanks and repeats.
        if value is None:
            return []
        items = value.split(",") if isinstance(value, str) else value
        if not isinstance(items, list):
            return value
        seen: list[str] = []
        for item in items:
            key = str(item).strip()
            if key and key not in seen:
                seen.append(key)
        return seen

    @field_validator("field_id", "field_name", mode="before")
    @classmethod
    def _blank_means_not_given(cls, value: object) -> object:
        """A form sends an empty string for an empty input; treat it as absent."""
        if isinstance(value, str):
            return value.strip() or None
        return value
