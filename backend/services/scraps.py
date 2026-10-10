from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scrap import Scrap
from backend.repositories import scraps as scrap_repository
from backend.schemas.scraps import (
    ScrapContentRead, ScrapCreate, ScrapDetail, ScrapPage, ScrapPlace, ScrapRead, ScrapUpdate,
)

Target = Literal["place", "review"]


class DuplicateScrap(Exception):
    def __init__(self, target: Target):
        self.target = target


class TargetNotFound(Exception):
    def __init__(self, target: Target):
        self.target = target


class TargetMismatch(Exception):
    """리뷰 스크랩에 지정한 장소가 그 리뷰의 장소와 다르다."""


async def _with_places(session: AsyncSession, scraps: list[Scrap]) -> list[ScrapRead]:
    summaries = await scrap_repository.place_summaries(session, sorted({s.place_id for s in scraps if s.place_id}))
    reads = []
    for scrap in scraps:
        read = ScrapRead.model_validate(scrap)
        if scrap.place_id in summaries:
            name, category, region = summaries[scrap.place_id]
            read.place = ScrapPlace(place_id=scrap.place_id, name=name, category=category, region=region)
        reads.append(read)
    return reads


async def create_scrap(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> ScrapRead:
    # 리뷰 스크랩은 그 리뷰의 장소를 함께 저장해 목록·장소별 조회·추천이 장소를 바로 알게 한다.
    if request.review_id is not None:
        place_id = await scrap_repository.review_place(session, request.review_id)
        if place_id is None:
            raise TargetNotFound("review")
        if request.place_id is None:
            request = request.model_copy(update={"place_id": place_id})
        elif request.place_id != place_id:
            raise TargetMismatch
    elif request.place_id is not None and not await scrap_repository.place_exists(session, request.place_id):
        raise TargetNotFound("place")

    target: Target = "review" if request.review_id is not None else "place"
    if await scrap_repository.find_duplicate(session, user_id=user_id, request=request) is not None:
        raise DuplicateScrap(target)
    try:
        scrap = await scrap_repository.create_scrap(session, user_id=user_id, request=request)
        await session.commit()
    except IntegrityError as error:  # 동시에 같은 스크랩을 두 번 만든 경우 DB 고유 인덱스가 막는다
        await session.rollback()
        raise DuplicateScrap(target) from error
    return (await _with_places(session, [scrap]))[0]


async def list_scraps(
    session: AsyncSession, *, user_id: int, page: int, size: int,
    source_type: str | None = None, place_id: int | None = None,
) -> ScrapPage:
    scraps = await scrap_repository.list_scraps(
        session, user_id=user_id, limit=size, offset=(page - 1) * size, source_type=source_type, place_id=place_id,
    )
    total = await scrap_repository.count_scraps(session, user_id=user_id, source_type=source_type, place_id=place_id)
    return ScrapPage(items=await _with_places(session, scraps), page=page, size=size, total=total)


async def get_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> ScrapDetail | None:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return None
    content = await scrap_repository.get_content(session, scrap_id)
    return ScrapDetail(
        **(await _with_places(session, [scrap]))[0].model_dump(),
        content=ScrapContentRead.model_validate(content) if content is not None else None,
    )


async def update_scrap(
    session: AsyncSession, *, scrap_id: int, user_id: int, request: ScrapUpdate,
) -> ScrapRead | None:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return None
    if "title" in request.model_fields_set:
        scrap = await scrap_repository.update_title(session, scrap, request.title)
        await session.commit()
    return (await _with_places(session, [scrap]))[0]


async def delete_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> bool:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return False
    await scrap_repository.delete_scrap(session, scrap)
    await session.commit()
    return True
