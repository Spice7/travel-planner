from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScrapCreate(BaseModel):
    place_id: int | None = Field(default=None, gt=0)
    review_id: int | None = Field(default=None, gt=0)
    source_url: str | None = Field(default=None, max_length=1000)
    title: str | None = Field(default=None, max_length=300)
    # source_type은 받지 않는다. 서버가 source_url 유무로 internal/external을 정한다.

    @model_validator(mode="after")
    def require_target(self) -> "ScrapCreate":
        if self.place_id is None and self.review_id is None and self.source_url is None:
            raise ValueError("place_id, review_id, source_url 중 하나는 있어야 합니다.")
        return self


class ScrapPlace(BaseModel):
    """목록에서 장소마다 다시 조회하지 않도록 함께 내리는 장소 요약."""

    place_id: int
    name: str | None
    category: str
    region: str | None


class ScrapRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scrap_id: int
    user_id: int
    place_id: int | None
    review_id: int | None
    source_url: str | None
    title: str | None
    source_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    place: ScrapPlace | None = None  # 장소가 없는 외부 링크 스크랩은 null


class ScrapPage(BaseModel):
    items: list[ScrapRead]
    page: int
    size: int
    total: int


class ScrapUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)


class ScrapContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_text: str | None
    extraction_method: str | None
    fetched_at: datetime | None
    promo_signals: list[str] = []  # 본문에서 찾은 홍보 문구 (원고료, 협찬 등)
    traveler_context: list[str] = []


class ScrapAnnotationRead(BaseModel):
    annotation_id: int
    aspect: str
    label: str  # aspect의 한국어 이름
    attribute: str
    sentiment: str
    evidence: str
    evidence_start: int  # content_text 안의 위치
    evidence_end: int
    status: Literal["suggested", "confirmed", "rejected"]


class ScrapDetail(ScrapRead):
    content: ScrapContentRead | None = None
    annotations: list[ScrapAnnotationRead] = []  # 글 스크랩만


MAX_POST_CHARS = 5000


class PostCreate(BaseModel):
    """붙여 넣은 글 스크랩. 원문 주소는 출처로만 저장하고 가져오지 않는다."""

    text: str = Field(min_length=20, max_length=MAX_POST_CHARS)
    place_id: int = Field(gt=0)
    title: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_url(self) -> "PostCreate":
        if self.source_url and not self.source_url.startswith(("http://", "https://")):
            raise ValueError("원문 주소는 http:// 또는 https://로 시작해야 합니다.")
        return self


class PlaceCandidatesRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_POST_CHARS)


class PlaceCandidate(ScrapPlace):
    hits: int  # 본문에서 이 장소 이름이 나온 횟수


class AnnotationConfirm(BaseModel):
    confirmed: list[int] = Field(max_length=500)  # 확정할 라벨 id. 나머지는 제외로 남긴다
