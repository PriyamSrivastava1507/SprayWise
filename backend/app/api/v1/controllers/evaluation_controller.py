from fastapi import APIRouter

from app.api.deps import EvaluationServiceDep
from app.schemas.evaluation import EvaluationResponse

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation", response_model=EvaluationResponse, summary="Stored evaluation metrics")
def evaluation(service: EvaluationServiceDep) -> EvaluationResponse:
    return service.get()
