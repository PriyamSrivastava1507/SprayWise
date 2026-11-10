import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import get_db
from app.core.config import Settings
from app.core.database import Base
from app.main import create_app


@pytest.fixture
def make_client(tmp_path):
    """Factory so tests can choose the segmentation backend."""
    opened: list[TestClient] = []

    def _make(backend: str = "fake", **overrides) -> TestClient:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)

        def override_db():
            with Session(engine, expire_on_commit=False) as session:
                yield session

        settings = Settings(
            storage_dir=str(tmp_path / "media"),
            segmentation_backend=backend,
            **overrides,
        )
        app = create_app(settings, init_database=False)
        app.dependency_overrides[get_db] = override_db
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        opened.append(client)
        return client

    yield _make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()
