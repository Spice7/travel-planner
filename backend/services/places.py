from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories import places as place_repository
from backend.models.place import Place
from backend.schemas.places import (
    EvidenceReview, PlaceDetailRead, PlaceImageRead, PlaceListItem, PlacePage, PlaceProfile, PlaceRead,
    PlaceTagRead, ProfileAspect, ProfileContext,
)


def _percent(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _place_fields(place: Place, category: str, district: str | None, region: str | None) -> dict:
    """목록과 상세가 함께 쓰는 장소 필드."""
    return {
        **PlaceRead.model_validate(place).model_dump(),
        "name": place.place_name, "category": category, "district": district, "region": region,
        "summary": place.intro_text or "",
    }


async def list_places(session: AsyncSession, *, page: int, size: int) -> PlacePage:
    rows = await place_repository.list_places(session, limit=size, offset=(page - 1) * size)
    items = [
        PlaceListItem(**_place_fields(place, category, district, region),
                      main_image_url=main_image_url, review_count=review_count)
        for place, category, district, region, review_count, main_image_url in rows
    ]
    return PlacePage(items=items, page=page, size=size, total=await place_repository.count_places(session))


async def get_place_detail(session: AsyncSession, place_id: int) -> PlaceDetailRead | None:
    info = await place_repository.place_detail_info(session, place_id)
    if info is None:
        return None
    place, category, district, region = info
    images = [PlaceImageRead(image_url=image.image_url, is_main=image.is_main, sort_order=image.sort_order)
              for image in await place_repository.place_images(session, place_id)]
    tags = [PlaceTagRead(category=tag_category, tag_name=tag_name)
            for tag_category, tag_name in await place_repository.place_tags(session, place_id)]
    return PlaceDetailRead(
        **_place_fields(place, category, district, region),
        main_image_url=next((image.image_url for image in images if image.is_main), None),
        review_count=await place_repository.count_reviews(session, place_id),
        images=images, tags=tags,
    )


async def get_profile(session: AsyncSession, place_id: int) -> PlaceProfile | None:
    if await place_repository.get_place(session, place_id) is None:
        return None
    review_count = await place_repository.count_reviews(session, place_id)

    mentions = await place_repository.aspect_mentions(session, place_id)
    aspects = sorted(
        (ProfileAspect(aspect=aspect, polarity=sentiment, share=_percent(count, review_count), mentions=count)
         for aspect, sentiment, count in mentions),
        key=lambda item: (-item.mentions, item.aspect, item.polarity),
    )

    contexts = sorted(
        (ProfileContext(context=code, ratio=_percent(count, review_count))
         for code, count in await place_repository.context_counts(session, place_id)),
        key=lambda item: (-item.ratio, item.context),
    )

    polarity: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for code, sentiment, count in await place_repository.context_sentiments(session, place_id):
        polarity[code][sentiment] += count
    satisfaction = {
        code: _percent(counts["positive"], counts["positive"] + counts["negative"])
        for code, counts in sorted(polarity.items())
        if counts["positive"] + counts["negative"]
    }

    return PlaceProfile(
        place_id=place_id, review_count=review_count, aspects=aspects,
        contexts=contexts, context_satisfaction=satisfaction,
    )


async def get_evidence(
    session: AsyncSession, *, place_id: int, aspect: str, sentiment: str | None, context: str | None, limit: int,
) -> list[EvidenceReview] | None:
    if await place_repository.get_place(session, place_id) is None:
        return None
    rows = await place_repository.evidence(
        session, place_id=place_id, aspect=aspect, sentiment=sentiment, context=context, limit=limit,
    )
    contexts = await place_repository.review_contexts(session, sorted({row[0] for row in rows}))
    return [
        EvidenceReview(
            review_id=review_id, text=text, context=", ".join(contexts.get(review_id, [])), attribute=attribute,
            sentiment=row_sentiment, evidence_start=start, evidence_end=end,
        )
        for review_id, text, attribute, row_sentiment, start, end in rows
    ]
