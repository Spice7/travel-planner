"""붙여 넣은 글 스크랩: 장소 후보 찾기 → 장소 관련 단락 고르기 → QLoRA 분석 → 제안 라벨 저장 → 사용자 확정.

외부 사이트에는 접속하지 않는다. 원문 주소는 출처로만 저장한다.
"""

import hashlib
import re

import httpx
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients.ollama_client import OllamaClient
from backend.core.config import get_settings
from backend.models.scrap import Scrap
from backend.repositories import scraps as scrap_repository
from backend.schemas.scraps import AnnotationConfirm, PlaceCandidate, PostCreate, ScrapDetail
from backend.services.analysis import SYSTEM_PROMPT, ModelUnavailable
from backend.services.label_validation import load_vocab, validate
from backend.services.scraps import DuplicateScrap, TargetNotFound, get_scrap

MAX_CHUNKS = 5  # 글 1건에 모델을 부르는 최대 횟수
CHUNK_SIZE = 450  # 이어진 단락을 이 길이까지 한 번에 분석한다
CHUNK_LIMIT = 650  # 단락 하나가 이보다 길면 잘라서 넣는다
MIN_CHUNK = 15
CANDIDATE_LIMIT = 5
# 실험에서 소규모 모델은 홍보 글을 가려내지 못해 규칙으로 찾는다. 경고만 하고 분석은 그대로 한다.
PROMO_PATTERNS = ("원고료", "협찬", "제공받", "소정의", "체험단", "광고", "쿠폰", "업체로부터")

_BRANCH = re.compile(r"\s+(-\s*)?[가-힣A-Za-z]*점$|\s*\([^)]*\)$")  # 지점명("광안점")이나 괄호 설명


class NotAPost(Exception):
    """장소 찜·리뷰 저장처럼 본문이 없는 스크랩."""


class UnknownAnnotation(Exception):
    """이 스크랩의 라벨이 아닌 id."""


def clean_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def content_hash(text: str) -> str:
    """공백 차이는 같은 글로 본다."""
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8")).hexdigest()


def promo_signals(text: str) -> list[str]:
    return [pattern for pattern in PROMO_PATTERNS if pattern in text]


def _norm(text: str) -> str:
    return re.sub(r"[\s\-·()&,.'\"]", "", text.lower())


def place_keys(name: str) -> set[str]:
    """글에서 장소를 찾을 때 쓰는 이름들. 띄어쓰기·by/바이·지점명 차이를 무시한다."""
    core = _BRANCH.sub("", name).strip()
    keys = {_norm(name), _norm(core), _norm(name).replace("by", "바이"), _norm(core).replace("by", "바이")}
    return {key for key in keys if len(key) >= 3}


def select_chunks(content: str, place_name: str) -> list[tuple[int, int]]:
    """분석할 본문 구간 (시작, 끝). 장소 이름이 나온 단락과 그 앞뒤를 고르고, 없으면 앞에서부터.

    구간은 항상 content의 연속된 부분이라 근거 구절의 위치를 그대로 계산할 수 있다.
    """
    spans = [(m.start(), m.end()) for m in re.finditer(r"[^\n]+", content) if m.group().strip()]
    keys = place_keys(place_name)
    hits = [i for i, (a, b) in enumerate(spans) if any(key in _norm(content[a:b]) for key in keys)]
    picked = sorted({j for i in hits for j in (i - 1, i, i + 1) if 0 <= j < len(spans)}) or list(range(len(spans)))
    chunks: list[tuple[int, int]] = []
    previous = None
    for j in picked:
        a, b = spans[j]
        if chunks and previous == j - 1 and b - chunks[-1][0] <= CHUNK_SIZE:
            chunks[-1] = (chunks[-1][0], b)
        else:
            chunks.append((a, b))
        previous = j
    chunks = [(a, min(b, a + CHUNK_LIMIT)) for a, b in chunks if b - a >= MIN_CHUNK]
    return chunks[:MAX_CHUNKS]


async def analyze(
    content: str, place_name: str, category: str, vocab: dict, companions: list[str], client: OllamaClient | None = None,
) -> tuple[list[dict], list[str]]:
    """(라벨, 동행 유형). 라벨은 자동 검증(허용 aspect·attribute·감성, 근거가 원문에 그대로 있는지)을 통과한 것만."""
    model = get_settings().ollama_model
    if not model:
        raise ModelUnavailable("'qlora' 모델이 설정되지 않았습니다.")
    client = client or OllamaClient()
    labels: list[dict] = []
    contexts: list[str] = []
    seen: set[tuple] = set()
    for a, b in select_chunks(content, place_name):
        chunk = content[a:b]
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"[카테고리]\n{category}\n\n[리뷰]\n{chunk}"}]
        try:
            output = await client.chat(model, messages)
        except httpx.HTTPError as error:
            raise ModelUnavailable("분석 모델 서버에 연결할 수 없습니다.") from error
        result = validate(output, chunk, category, vocab, companions)
        contexts += [context for context in result["traveler_context"] if context not in contexts]
        for item in result["aspects"]:
            start = a + chunk.find(item["evidence"])
            key = (item["category"], item["attribute"], item["sentiment"], start)
            if key in seen:
                continue
            seen.add(key)
            labels.append({"aspect": item["category"], "attribute_value": item["attribute"], "sentiment": item["sentiment"],
                           "evidence_text": item["evidence"], "evidence_start": start, "evidence_end": start + len(item["evidence"])})
    return labels, contexts


async def place_candidates(session: AsyncSession, text: str) -> list[PlaceCandidate]:
    """본문에 이름이 나온 장소. 모델을 쓰지 않는다."""
    body = _norm(text)
    found = []
    for place_id, (name, category, region) in (await scrap_repository.place_summaries(session, None)).items():
        hits = max((body.count(key) for key in place_keys(name or "")), default=0)
        if hits:
            found.append(PlaceCandidate(place_id=place_id, name=name, category=category, region=region, hits=hits))
    return sorted(found, key=lambda c: (-c.hits, c.name or ""))[:CANDIDATE_LIMIT]


async def _analyze_into(session: AsyncSession, scrap: Scrap, content: str) -> None:
    """분석해 제안 라벨로 바꿔 넣는다. 모델을 쓸 수 없으면 상태만 failed로 남기고 예외를 다시 던진다."""
    name, category, _ = (await scrap_repository.place_summaries(session, [scrap.place_id]))[scrap.place_id]
    vocab, companions = await load_vocab(session)
    try:
        labels, contexts = await analyze(content, name or "", category, vocab, companions)
    except ModelUnavailable:
        scrap.status = "failed"
        await session.commit()
        raise
    ids = await scrap_repository.aspect_ids(session, category)
    await scrap_repository.replace_annotations(session, scrap.scrap_id, [
        {key: value for key, value in label.items() if key != "aspect"} | {"aspect_id": ids[label["aspect"]]}
        for label in labels if label["aspect"] in ids
    ])
    stored = await scrap_repository.get_content(session, scrap.scrap_id)
    stored.traveler_context = contexts
    scrap.status = "analyzed"
    scrap.updated_at = func.current_timestamp()
    await session.commit()


async def create_post(session: AsyncSession, *, user_id: int, request: PostCreate) -> ScrapDetail:
    """글을 저장하고 바로 분석한다. 모델을 쓸 수 없어도 글은 저장하고 failed로 남겨 다시 분석할 수 있게 한다."""
    if not await scrap_repository.place_exists(session, request.place_id):
        raise TargetNotFound("place")
    content = clean_text(request.text)
    digest = content_hash(content)
    if await scrap_repository.find_post(session, user_id=user_id, place_id=request.place_id, content_hash=digest):
        raise DuplicateScrap("post")
    title = request.title or content.split("\n", 1)[0][:60]
    try:
        scrap = await scrap_repository.create_post(
            session, user_id=user_id, place_id=request.place_id, title=title, source_url=request.source_url,
            content_text=content, content_hash=digest, promo_signals=promo_signals(content),
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DuplicateScrap("post") from error
    try:
        await _analyze_into(session, scrap, content)
    except ModelUnavailable:
        pass  # 글은 저장됐고 상태가 failed다. 화면에서 다시 분석한다.
    return await get_scrap(session, scrap_id=scrap.scrap_id, user_id=user_id)


async def _post(session: AsyncSession, scrap_id: int, user_id: int) -> Scrap | None:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is not None and scrap.content_hash is None:
        raise NotAPost
    return scrap


async def reanalyze(session: AsyncSession, *, scrap_id: int, user_id: int) -> ScrapDetail | None:
    """이전 라벨(확정 포함)을 지우고 다시 제안한다. 모델을 쓸 수 없으면 ModelUnavailable."""
    scrap = await _post(session, scrap_id, user_id)
    if scrap is None:
        return None
    content = (await scrap_repository.get_content(session, scrap_id)).content_text or ""
    await _analyze_into(session, scrap, content)
    return await get_scrap(session, scrap_id=scrap_id, user_id=user_id)


async def confirm(session: AsyncSession, *, scrap_id: int, user_id: int, request: AnnotationConfirm) -> ScrapDetail | None:
    """고른 라벨은 확정, 나머지는 제외로 남긴다. 제외한 라벨도 aspect별 제외율 집계를 위해 지우지 않는다."""
    scrap = await _post(session, scrap_id, user_id)
    if scrap is None:
        return None
    known = {annotation.annotation_id for annotation, _ in await scrap_repository.annotations(session, scrap_id)}
    if not set(request.confirmed) <= known:
        raise UnknownAnnotation
    await scrap_repository.set_annotation_statuses(session, scrap_id, set(request.confirmed))
    scrap.status = "confirmed"
    scrap.updated_at = func.current_timestamp()
    await session.commit()
    return await get_scrap(session, scrap_id=scrap_id, user_id=user_id)
