from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.catalog import District, PlaceCategory, Region
from backend.models.place import Place
from backend.models.review import Review
from backend.models.scrap import Scrap, ScrapContent
from backend.schemas.scraps import ScrapCreate


async def create_scrap(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> Scrap:
    source_type = "external" if request.source_url else "internal"
    scrap = Scrap(user_id=user_id, source_type=source_type, **request.model_dump())
    session.add(scrap)
    await session.flush()
    await session.refresh(scrap)
    return scrap


async def find_duplicate(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> Scrap | None:
    """같은 리뷰를 이미 저장했거나 같은 장소를 이미 찜했으면 그 스크랩. 외부 글은 여기서 판단하지 않는다."""
    query = select(Scrap).where(Scrap.user_id == user_id)
    if request.review_id is not None:
        query = query.where(Scrap.review_id == request.review_id)
    elif request.source_url is None and request.place_id is not None:
        query = query.where(Scrap.place_id == request.place_id, Scrap.review_id.is_(None), Scrap.source_url.is_(None))
    else:
        return None
    return await session.scalar(query.limit(1))


async def place_exists(session: AsyncSession, place_id: int) -> bool:
    return await session.scalar(select(Place.place_id).where(Place.place_id == place_id)) is not None


async def review_place(session: AsyncSession, review_id: int) -> int | None:
    """리뷰가 속한 장소. 리뷰가 없으면 None."""
    return await session.scalar(select(Review.place_id).where(Review.review_id == review_id))


def _filtered(user_id: int, source_type: str | None, place_id: int | None) -> Select:
    query = select(Scrap).where(Scrap.user_id == user_id)
    if source_type is not None:
        query = query.where(Scrap.source_type == source_type)
    if place_id is not None:
        query = query.where(Scrap.place_id == place_id)
    return query


async def list_scraps(
    session: AsyncSession, *, user_id: int, limit: int, offset: int,
    source_type: str | None = None, place_id: int | None = None,
) -> list[Scrap]:
    result = await session.scalars(
        _filtered(user_id, source_type, place_id)
        .order_by(Scrap.created_at.desc(), Scrap.scrap_id.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def count_scraps(
    session: AsyncSession, *, user_id: int, source_type: str | None = None, place_id: int | None = None,
) -> int:
    query = _filtered(user_id, source_type, place_id).with_only_columns(func.count())
    return await session.scalar(query) or 0


async def place_summaries(session: AsyncSession, place_ids: list[int]) -> dict[int, tuple[str | None, str, str | None]]:
    """{place_id: (이름, category_code, region_code)}."""
    if not place_ids:
        return {}
    rows = await session.execute(
        select(Place.place_id, Place.place_name, PlaceCategory.category_code, Region.region_code)
        .join(PlaceCategory, PlaceCategory.category_id == Place.category_id)
        .outerjoin(District, District.district_id == Place.district_id)
        .outerjoin(Region, Region.region_id == District.region_id)
        .where(Place.place_id.in_(place_ids))
    )
    return {place_id: (name, category, region) for place_id, name, category, region in rows}


async def get_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> Scrap | None:
    return await session.scalar(
        select(Scrap).where(Scrap.scrap_id == scrap_id, Scrap.user_id == user_id)
    )


async def get_content(session: AsyncSession, scrap_id: int) -> ScrapContent | None:
    return await session.get(ScrapContent, scrap_id)


async def update_title(session: AsyncSession, scrap: Scrap, title: str | None) -> Scrap:
    scrap.title = title
    scrap.updated_at = func.current_timestamp()
    await session.flush()
    await session.refresh(scrap)
    return scrap


async def delete_scrap(session: AsyncSession, scrap: Scrap) -> None:
    await session.delete(scrap)
