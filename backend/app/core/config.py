"""Application settings, read from environment variables (and .env)."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


MODEL_KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


class ModelSpec(BaseModel):
    """One ML model the app can use. In .env, ML_MODELS is a JSON list of these."""

    key: str  # short id used in the API, URLs and file names, e.g. "cwfid"
    label: str  # name shown to people, e.g. "ML (CWFID)"
    backend: Literal["fake", "unavailable", "hf"] = "hf"
    path: str = ""  # local folder or Hugging Face Hub ID (hf only)

    @field_validator("key")
    @classmethod
    def _key_format(cls, value: str) -> str:
        if not MODEL_KEY.match(value):
            raise ValueError("model key must be 1-32 lowercase letters, digits or '-'")
        return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Persistence
    database_url: str = "sqlite:///./data/spraywise.db"
    storage_dir: str = "./data/media"
    evaluation_dir: str = "./data/evaluation"  # classical.json, ml.json written by scripts/evaluate.py

    # ML segmentation client:
    #   fake        - artificial demo mask (development, frontend work)
    #   unavailable - ML mode reports model_unavailable (test that UI state)
    #   hf          - the real SegFormer model (Hub ID or local folder)
    segmentation_backend: Literal["fake", "unavailable", "hf"] = "fake"
    hf_model_id: str = "YOUR_USERNAME/cropweed-segformer-b0"
    hf_token: str | None = None

    # Several models at once. When set, it replaces SEGMENTATION_BACKEND and
    # HF_MODEL_ID. Example (.env, one line, JSON):
    # ML_MODELS=[{"key":"cwfid","label":"ML (CWFID)","path":"./models/segformer-cwfid"},
    #            {"key":"we3ds","label":"ML (WE3DS)","path":"./models/segformer-we3ds"}]
    ml_models: list[ModelSpec] = []
    default_ml_model: Optional[str] = None  # a key from ML_MODELS; first one if empty

    log_level: str = "INFO"

    # Uploads and processing
    max_upload_mb: int = 10
    working_width: int = 1024

    # Weed pressure thresholds (weed % of the image). Adjustable placeholders,
    # not agronomic standards.
    pressure_low_max: float = 5.0
    pressure_high_min: float = 15.0

    # CORS. In .env this must be JSON: ALLOWED_ORIGINS=["http://localhost:5173"]
    allowed_origins: list[str] = ["http://localhost:5173"]

    @field_validator("hf_token", mode="before")
    @classmethod
    def _blank_token_is_none(cls, value: object) -> object:
        """`HF_TOKEN=` in .env arrives as "", which the Hub would treat as a token."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("default_ml_model", mode="before")
    @classmethod
    def _blank_default_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _check_models(self) -> "Settings":
        keys = [m.key for m in self.ml_models]
        if len(keys) != len(set(keys)):
            raise ValueError("ML_MODELS has duplicate keys")
        if self.ml_models and self.default_ml_model and self.default_ml_model not in keys:
            raise ValueError(f"DEFAULT_ML_MODEL '{self.default_ml_model}' is not one of {keys}")
        return self

    def model_specs(self) -> list[ModelSpec]:
        """The models to load. Without ML_MODELS: one model from the older
        SEGMENTATION_BACKEND / HF_MODEL_ID settings, under the key "default"."""
        if self.ml_models:
            return list(self.ml_models)
        return [
            ModelSpec(
                key="default",
                label="ML segmentation",
                backend=self.segmentation_backend,
                path=self.hf_model_id,
            )
        ]

    def default_model_key(self) -> str:
        specs = self.model_specs()
        return self.default_ml_model or specs[0].key

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
