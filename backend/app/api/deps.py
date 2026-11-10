"""Dependency providers. Controllers ask for what they need; tests can replace
any of these with dependency_overrides."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.clients.base import SegmentationClient, StorageClient
from app.core.config import Settings
from app.core.database import SessionLocal
from app.repositories.field_repository import FieldRepository
from app.repositories.scan_repository import ScanRepository
from app.services.analysis_service import AnalysisService
from app.services.evaluation_service import EvaluationService
from app.services.export_service import ExportService
from app.services.field_service import FieldService
from app.services.scan_service import ScanService


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> StorageClient:
    return request.app.state.storage


def get_segmenter(request: Request) -> SegmentationClient:
    return request.app.state.segmenter


DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[StorageClient, Depends(get_storage)]
SegmenterDep = Annotated[SegmentationClient, Depends(get_segmenter)]


def get_analysis_service(
    db: DbDep,
    storage: StorageDep,
    segmenter: SegmenterDep,
    settings: SettingsDep,
) -> AnalysisService:
    return AnalysisService(
        scans=ScanRepository(db),
        fields=FieldRepository(db),
        storage=storage,
        segmenter=segmenter,
        settings=settings,
    )


AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]


def get_scan_service(db: DbDep, storage: StorageDep) -> ScanService:
    return ScanService(ScanRepository(db), storage)


def get_field_service(db: DbDep) -> FieldService:
    return FieldService(FieldRepository(db), ScanRepository(db))


ScanServiceDep = Annotated[ScanService, Depends(get_scan_service)]
FieldServiceDep = Annotated[FieldService, Depends(get_field_service)]


def get_export_service(db: DbDep, storage: StorageDep) -> ExportService:
    return ExportService(ScanRepository(db), storage)


def get_evaluation_service(settings: SettingsDep) -> EvaluationService:
    return EvaluationService(settings.evaluation_dir)


ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
EvaluationServiceDep = Annotated[EvaluationService, Depends(get_evaluation_service)]
