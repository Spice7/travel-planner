from fastapi import APIRouter

from backend.api.deps import CurrentUser
from backend.api.errors import ApiError
from backend.schemas.analysis import AnalysisResult, AnalyzeRequest
from backend.services import analysis as analysis_service

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=AnalysisResult)
async def analyze(request: AnalyzeRequest, user: CurrentUser) -> AnalysisResult:
    # 로그인한 사용자만 모델(GPU)을 쓸 수 있게 한다. user는 인증 확인용이다.
    try:
        return await analysis_service.analyze(request)
    except analysis_service.ModelUnavailable as error:
        raise ApiError(503, "MODEL_UNAVAILABLE", str(error)) from None
    except analysis_service.ModelOutputInvalid as error:
        raise ApiError(422, "MODEL_OUTPUT_INVALID", str(error)) from None
