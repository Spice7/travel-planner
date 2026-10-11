from typing import Annotated, Literal

from fastapi import APIRouter, Query

from backend.api.deps import Session
from backend.api.errors import ApiError
from backend.schemas.places import EvidenceReview, PlaceDetailRead, PlacePage, PlaceProfile
from backend.services import places as place_service

router = APIRouter(prefix="/places", tags=["places"])

Sentiment = Literal["positive", "negative", "neutral"]


def _not_found() -> ApiError:
    return ApiError(404, "PLACE_NOT_FOUND", "장소를 찾을 수 없습니다.")


@router.get("", response_model=PlacePage)
async def list_places(
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> PlacePage:
    return await place_service.list_places(session, page=page, size=size, q=q)


@router.get("/{place_id}", response_model=PlaceDetailRead)
async def get_place(place_id: int, session: Session) -> PlaceDetailRead:
    place = await place_service.get_place_detail(session, place_id)
    if place is None:
        raise _not_found()
    return place


@router.get("/{place_id}/profile", response_model=PlaceProfile)
async def get_profile(place_id: int, session: Session) -> PlaceProfile:
    profile = await place_service.get_profile(session, place_id)
    if profile is None:
        raise _not_found()
    return profile


@router.get("/{place_id}/evidence", response_model=list[EvidenceReview])
async def get_evidence(
    place_id: int,
    session: Session,
    aspect: Annotated[str, Query(min_length=1, max_length=100)],
    sentiment: Sentiment | None = None,
    context: Annotated[str | None, Query(max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[EvidenceReview]:
    evidence = await place_service.get_evidence(
        session, place_id=place_id, aspect=aspect, sentiment=sentiment, context=context, limit=limit,
    )
    if evidence is None:
        raise _not_found()
    return evidence
