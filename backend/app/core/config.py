"""Application settings, read from environment variables (and .env)."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Persistence
    database_url: str = "sqlite:///./data/spraywise.db"
    storage_dir: str = "./data/media"

    # ML segmentation client:
    #   fake        - artificial demo mask (development, frontend work)
    #   unavailable - ML mode reports model_unavailable (test that UI state)
    #   hf          - the real SegFormer model (Hub ID or local folder)
    segmentation_backend: Literal["fake", "unavailable", "hf"] = "fake"
    hf_model_id: str = "YOUR_USERNAME/cropweed-segformer-b0"
    hf_token: str | None = None

    # Uploads and processing
    max_upload_mb: int = 10
    working_width: int = 1024

    # Weed pressure thresholds (weed % of the image). Adjustable placeholders,
    # not agronomic standards.
    pressure_low_max: float = 5.0
    pressure_high_min: float = 15.0

    # CORS. In .env this must be JSON: ALLOWED_ORIGINS=["http://localhost:5173"]
    allowed_origins: list[str] = ["http://localhost:5173"]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
