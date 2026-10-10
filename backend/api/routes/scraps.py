from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from backend.api.deps import CurrentUser, Session
from backend.api.errors import ApiError
from backend.schemas.scraps import ScrapCreate, ScrapDetail, ScrapPage, ScrapRead, ScrapUpdate
from backend.services import scraps as scrap_service

router = APIRouter(prefix="/scraps", tags=["scraps"])

_DUPLICATE = {"place": "이미 스크랩한 장소입니다.", "review": "이미 스크랩한 리뷰입니다."}
_TARGET_NOT_FOUND = {
    "place": ("PLACE_NOT_FOUND", "장소를 찾을 수 없습니다."),
    "review": ("REVIEW_NOT_FOUND", "리뷰를 찾을 수 없습니다."),
}


def _not_found() -> ApiError:
    # 다른 사용자의 스크랩도 존재 여부를 드러내지 않도록 404로 응답한다.
    return ApiError(404, "SCRAP_NOT_FOUND", "스크랩을 찾을 수 없습니다.")


@router.post("", status_code=201, response_model=ScrapRead)
async def create_scrap(request: ScrapCreate, user: CurrentUser, session: Session) -> ScrapRead:
    try:
        return await scrap_service.create_scrap(session, user_id=user.user_id, request=request)
    except scrap_service.DuplicateScrap as error:
        raise ApiError(409, "ALREADY_EXISTS", _DUPLICATE[error.target]) from None
    except scrap_service.TargetNotFound as error:
        raise ApiError(404, *_TARGET_NOT_FOUND[error.target]) from None
    except scrap_service.TargetMismatch:
        raise ApiError(400, "INVALID_REQUEST", "리뷰가 지정한 장소의 리뷰가 아닙니다.") from None


@router.get("", response_model=ScrapPage)
async def list_scraps(
    user: CurrentUser,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    source_type: Literal["internal", "external"] | None = None,
    place_id: Annotated[int | None, Query(gt=0)] = None,
) -> ScrapPage:
    return await scrap_service.list_scraps(
        session, user_id=user.user_id, page=page, size=size, source_type=source_type, place_id=place_id,
    )


@router.get("/{scrap_id}", response_model=ScrapDetail)
async def get_scrap(scrap_id: int, user: CurrentUser, session: Session) -> ScrapDetail:
    scrap = await scrap_service.get_scrap(session, scrap_id=scrap_id, user_id=user.user_id)
    if scrap is None:
        raise _not_found()
    return scrap


@router.patch("/{scrap_id}", response_model=ScrapRead)
async def update_scrap(scrap_id: int, request: ScrapUpdate, user: CurrentUser, session: Session) -> ScrapRead:
    scrap = await scrap_service.update_scrap(session, scrap_id=scrap_id, user_id=user.user_id, request=request)
    if scrap is None:
        raise _not_found()
    return scrap


@router.delete("/{scrap_id}", status_code=204)
async def delete_scrap(scrap_id: int, user: CurrentUser, session: Session) -> Response:
    if not await scrap_service.delete_scrap(session, scrap_id=scrap_id, user_id=user.user_id):
        raise _not_found()
    return Response(status_code=204)
