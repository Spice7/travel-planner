from datetime import datetime

from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base

# 장소 자체를 찜한 스크랩. 주소 없이 붙여 넣은 글도 review_id·source_url이 비어 있어 source_type으로 구분한다.
PLACE_SCRAP = "source_type = 'internal' AND review_id IS NULL"
REVIEW_SCRAP = "review_id IS NOT NULL"
POST_SCRAP = "content_hash IS NOT NULL"

JsonList = JSON().with_variant(JSONB(), "postgresql")


class Scrap(Base):
    __tablename__ = "scraps"
    __table_args__ = (
        CheckConstraint("place_id IS NOT NULL OR review_id IS NOT NULL OR source_url IS NOT NULL", name="ck_scraps_target"),
        # 종류별 중복 방지: 같은 장소 찜, 같은 리뷰 저장, 같은 장소로 같은 글 저장만 막고 같은 장소의 다른 리뷰·글은 허용한다.
        Index("ux_scraps_user_place", "user_id", "place_id", unique=True,
              postgresql_where=text(PLACE_SCRAP), sqlite_where=text(PLACE_SCRAP)),
        Index("ux_scraps_user_review", "user_id", "review_id", unique=True,
              postgresql_where=text(REVIEW_SCRAP), sqlite_where=text(REVIEW_SCRAP)),
        Index("ux_scraps_user_place_content", "user_id", "place_id", "content_hash", unique=True,
              postgresql_where=text(POST_SCRAP), sqlite_where=text(POST_SCRAP)),
    )

    scrap_id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.place_id", ondelete="SET NULL"))
    review_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("reviews.review_id", ondelete="SET NULL"))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    title: Mapped[str | None] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(30), server_default=text("'internal'"))
    # ready: 찜·리뷰 저장 / 글 스크랩: analyzed → confirmed, 모델을 못 쓰면 failed
    status: Mapped[str] = mapped_column(String(20), server_default=text("'ready'"))
    content_hash: Mapped[str | None] = mapped_column(String(64))  # 글 스크랩만: 공백을 정리한 본문의 sha256
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))


class ScrapContent(Base):
    __tablename__ = "scrap_contents"

    scrap_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scraps.scrap_id", ondelete="CASCADE"), primary_key=True)
    content_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(30))  # user_paste (2단계), fetch (3단계)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    promo_signals: Mapped[list[str]] = mapped_column(JsonList, server_default=text("'[]'"))
    traveler_context: Mapped[list[str]] = mapped_column(JsonList, server_default=text("'[]'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))


class ScrapAnnotation(Base):
    """글 스크랩에서 모델이 뽑은 라벨. 사용자가 확정한 것만 그 사용자의 비교 추천에 쓴다."""

    __tablename__ = "scrap_annotations"
    __table_args__ = (CheckConstraint("evidence_start >= 0 AND evidence_end > evidence_start"),)

    annotation_id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    scrap_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scraps.scrap_id", ondelete="CASCADE"))
    aspect_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("aspects.aspect_id", ondelete="RESTRICT"))
    attribute_value: Mapped[str] = mapped_column(String(100))
    sentiment: Mapped[str] = mapped_column(String(10))
    evidence_text: Mapped[str] = mapped_column(Text)
    evidence_start: Mapped[int] = mapped_column(Integer)
    evidence_end: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), server_default=text("'suggested'"))  # suggested / confirmed / rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
