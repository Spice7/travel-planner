from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.aspect import Aspect
from backend.models.catalog import District, PlaceCategory, Region
from backend.models.place import Place
from backend.models.review import Review
from backend.models.scrap import Scrap, ScrapAnnotation, ScrapContent
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
        query = query.where(Scrap.place_id == request.place_id, Scrap.review_id.is_(None), Scrap.source_type == "internal")
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


async def place_summaries(
    session: AsyncSession, place_ids: list[int] | None,
) -> dict[int, tuple[str | None, str, str | None]]:
    """{place_id: (이름, category_code, region_code)}. place_ids가 None이면 모든 장소."""
    if place_ids is not None and not place_ids:
        return {}
    query = (
        select(Place.place_id, Place.place_name, PlaceCategory.category_code, Region.region_code)
        .join(PlaceCategory, PlaceCategory.category_id == Place.category_id)
        .outerjoin(District, District.district_id == Place.district_id)
        .outerjoin(Region, Region.region_id == District.region_id)
    )
    if place_ids is not None:
        query = query.where(Place.place_id.in_(place_ids))
    rows = await session.execute(query)
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


# --- 글 스크랩 ---

async def create_post(
    session: AsyncSession, *, user_id: int, place_id: int, title: str | None, source_url: str | None,
    content_text: str, content_hash: str, promo_signals: list[str],
) -> Scrap:
    scrap = Scrap(user_id=user_id, place_id=place_id, title=title, source_url=source_url,
                  source_type="external", status="analyzed", content_hash=content_hash)
    session.add(scrap)
    await session.flush()
    session.add(ScrapContent(scrap_id=scrap.scrap_id, content_text=content_text, extraction_method="user_paste",
                             promo_signals=promo_signals, traveler_context=[]))
    await session.flush()
    await session.refresh(scrap)
    return scrap


async def find_post(session: AsyncSession, *, user_id: int, place_id: int, content_hash: str) -> Scrap | None:
    return await session.scalar(select(Scrap).where(
        Scrap.user_id == user_id, Scrap.place_id == place_id, Scrap.content_hash == content_hash).limit(1))


async def aspect_ids(session: AsyncSession, category: str) -> dict[str, int]:
    """{aspect_name: aspect_id} — 이 카테고리의 aspect."""
    rows = await session.execute(
        select(Aspect.aspect_name, Aspect.aspect_id)
        .join(PlaceCategory, PlaceCategory.category_id == Aspect.category_id)
        .where(PlaceCategory.category_code == category)
    )
    return {name: aspect_id for name, aspect_id in rows}


async def replace_annotations(session: AsyncSession, scrap_id: int, labels: list[dict]) -> None:
    """다시 분석하면 이전 라벨을 모두 지우고 새 제안으로 바꾼다."""
    await session.execute(delete(ScrapAnnotation).where(ScrapAnnotation.scrap_id == scrap_id))
    session.add_all(ScrapAnnotation(scrap_id=scrap_id, status="suggested", **label) for label in labels)
    await session.flush()


async def annotations(session: AsyncSession, scrap_id: int) -> list[tuple[ScrapAnnotation, str]]:
    """(라벨, aspect_name), 본문 위치 순."""
    rows = await session.execute(
        select(ScrapAnnotation, Aspect.aspect_name)
        .join(Aspect, Aspect.aspect_id == ScrapAnnotation.aspect_id)
        .where(ScrapAnnotation.scrap_id == scrap_id)
        .order_by(ScrapAnnotation.evidence_start, ScrapAnnotation.annotation_id)
    )
    return [tuple(row) for row in rows]


async def set_annotation_statuses(session: AsyncSession, scrap_id: int, confirmed_ids: set[int]) -> None:
    for status, matches in (("confirmed", True), ("rejected", False)):
        condition = ScrapAnnotation.annotation_id.in_(confirmed_ids) if matches else ScrapAnnotation.annotation_id.not_in(confirmed_ids)
        await session.execute(
            update(ScrapAnnotation).where(ScrapAnnotation.scrap_id == scrap_id, condition)
            .values(status=status, updated_at=func.current_timestamp())
        )
