"""스크랩 테스트가 함께 쓰는 SQLite DB. unittest discover가 tests/를 경로에 넣어 바로 불러올 수 있다."""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.models.aspect import Aspect, AspectValue
from backend.models.catalog import District, PlaceCategory, Region
from backend.models.companion import CompanionType
from backend.models.place import Place
from backend.models.place_assets import PlaceImage

# SQLite는 BIGINT 기본 키에 번호를 자동으로 매기지 않고 JSONB도 없어, 같은 열과 같은 조건부 고유 인덱스로 직접 만든다.
SCRAP_DDL = [
    """CREATE TABLE scraps (
        scrap_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, place_id INTEGER, review_id INTEGER,
        source_url VARCHAR(1000), title VARCHAR(300), source_type VARCHAR(30) NOT NULL DEFAULT 'internal',
        status VARCHAR(20) NOT NULL DEFAULT 'ready', content_hash VARCHAR(64),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE UNIQUE INDEX ux_scraps_user_place ON scraps (user_id, place_id) WHERE source_type = 'internal' AND review_id IS NULL",
    "CREATE UNIQUE INDEX ux_scraps_user_review ON scraps (user_id, review_id) WHERE review_id IS NOT NULL",
    "CREATE UNIQUE INDEX ux_scraps_user_place_content ON scraps (user_id, place_id, content_hash) WHERE content_hash IS NOT NULL",
    """CREATE TABLE scrap_contents (
        scrap_id INTEGER PRIMARY KEY, content_text TEXT, extraction_method VARCHAR(30), fetched_at DATETIME,
        promo_signals JSON NOT NULL DEFAULT '[]', traveler_context JSON NOT NULL DEFAULT '[]',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE scrap_annotations (
        annotation_id INTEGER PRIMARY KEY AUTOINCREMENT, scrap_id INTEGER NOT NULL, aspect_id INTEGER NOT NULL,
        attribute_value VARCHAR(100) NOT NULL, sentiment VARCHAR(10) NOT NULL, evidence_text TEXT NOT NULL,
        evidence_start INTEGER NOT NULL, evidence_end INTEGER NOT NULL, status VARCHAR(10) NOT NULL DEFAULT 'suggested',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    # Review 모델의 JSONB는 SQLite에서 만들 수 없어, 스크랩이 쓰는 열만 둔다.
    "CREATE TABLE reviews (review_id INTEGER PRIMARY KEY, place_id INTEGER)",
    "INSERT INTO reviews VALUES (101, 31), (102, 31)",
]

# (aspect_id, category_id, aspect_name, [attribute ...])
ASPECTS = [
    (1, 1, "scenery", ["sea", "city"]),
    (2, 1, "walking_burden", ["high", "low"]),
    (3, 2, "food_quality", ["good", "bad"]),
    (4, 2, "staff_service", ["kind", "unkind"]),
    (5, 2, "price", ["expensive", "reasonable"]),
]


async def build_engine() -> AsyncEngine:
    """장소 31·32(관광지), 33(식당)과 각 카테고리의 aspect·허용 값, 동행 유형이 들어 있다."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Region.metadata.create_all(sync, tables=[
            Region.__table__, District.__table__, PlaceCategory.__table__, Place.__table__,
            PlaceImage.__table__, Aspect.__table__, AspectValue.__table__, CompanionType.__table__,
        ]))
        await connection.execute(Region.__table__.insert(), {"region_id": 1, "region_code": "haeundae", "region_name": "해운대"})
        await connection.execute(District.__table__.insert(), {"district_id": 1, "region_id": 1, "district_name": "해운대구"})
        await connection.execute(PlaceCategory.__table__.insert(), [
            {"category_id": 1, "category_code": "attraction", "category_name": "관광지"},
            {"category_id": 2, "category_code": "restaurant", "category_name": "식당"},
        ])
        place = {"source": "t", "district_id": 1, "created_at": now, "updated_at": now}
        await connection.execute(Place.__table__.insert(), [
            place | {"place_id": 31, "category_id": 1, "source_place_id": "31", "place_name": "뮤지엄 원"},
            place | {"place_id": 32, "category_id": 1, "source_place_id": "32", "place_name": "지역 없는 곳", "district_id": None},
            place | {"place_id": 33, "category_id": 2, "source_place_id": "33", "place_name": "고릴라브루잉"},
        ])
        await connection.execute(Aspect.__table__.insert(), [
            {"aspect_id": aspect_id, "category_id": category_id, "aspect_name": name, "is_active": True}
            for aspect_id, category_id, name, _ in ASPECTS
        ])
        await connection.execute(AspectValue.__table__.insert(), [
            {"value_id": aspect_id * 10 + i, "aspect_id": aspect_id, "value_name": value, "sort_order": i, "is_active": True}
            for aspect_id, _, _, values in ASPECTS for i, value in enumerate(values)
        ])
        await connection.execute(CompanionType.__table__.insert(), [
            {"companion_type_id": 1, "companion_code": "family_with_kids", "companion_name": "아이", "is_active": True},
            {"companion_type_id": 2, "companion_code": "parents", "companion_name": "부모님", "is_active": True},
        ])
        for statement in SCRAP_DDL:
            await connection.execute(text(statement))
    return engine
