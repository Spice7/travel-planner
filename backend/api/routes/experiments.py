from fastapi import APIRouter

from backend.api.errors import ApiError
from backend.schemas.experiments import ExperimentMetricRow
from backend.services import experiments as experiment_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentMetricRow])
async def list_experiments() -> list[ExperimentMetricRow]:
    try:
        return experiment_service.list_metrics()
    except experiment_service.MetricsNotFound:
        raise ApiError(404, "METRICS_NOT_FOUND", "평가 결과 파일을 찾을 수 없습니다.") from None
