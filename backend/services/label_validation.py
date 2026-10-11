"""모델 출력 라벨의 자동 검증. 모델 비교(model_compare)와 글 스크랩이 같은 규칙을 쓴다."""

import json
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SENTIMENTS = {"positive", "negative", "neutral"}


async def load_vocab(session: AsyncSession) -> tuple[dict[str, dict[str, set[str]]], list[str]]:
    """({카테고리: {aspect: 허용 attribute}}, 동행 유형 코드)."""
    rows = await session.execute(text(
        "select pc.category_code, a.aspect_name, av.value_name from aspects a"
        " join place_categories pc using (category_id)"
        " join aspect_values av on av.aspect_id = a.aspect_id and av.is_active where a.is_active"
    ))
    vocab: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for category, aspect, value in rows:
        vocab[category][aspect].add(value)
    companions = (await session.execute(text(
        "select companion_code from companion_types where is_active order by companion_type_id"
    ))).scalars().all()
    return vocab, list(companions)


def validate(output: str, review: str, category: str, vocab: dict[str, dict[str, set[str]]], companions: list[str]) -> dict:
    """서비스 라벨과 같은 자동 검증: JSON, 허용 aspect·attribute·sentiment, evidence가 원문에 그대로 있는지."""
    start, end = output.find("{"), output.rfind("}")
    try:
        data = json.loads(output[start:end + 1]) if 0 <= start < end else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return {"parse_ok": False, "aspects": [], "rejected": {}, "traveler_context": []}
    aspects, rejected = [], defaultdict(int)
    for item in data.get("aspects") if isinstance(data.get("aspects"), list) else []:
        if not isinstance(item, dict):
            rejected["not_object"] += 1
        elif item.get("category") not in vocab[category]:
            rejected["unknown_aspect"] += 1
        elif item.get("attribute") not in vocab[category][item["category"]]:
            rejected["unknown_attribute"] += 1
        elif item.get("sentiment") not in SENTIMENTS:
            rejected["unknown_sentiment"] += 1
        elif not isinstance(item.get("evidence"), str) or not item["evidence"].strip() or item["evidence"] not in review:
            rejected["evidence_not_in_review"] += 1
        else:
            aspects.append({key: item[key] for key in ("category", "attribute", "sentiment", "evidence")})
    contexts = data.get("traveler_context") if isinstance(data.get("traveler_context"), list) else []
    return {"parse_ok": True, "aspects": aspects, "rejected": dict(rejected),
            "traveler_context": [c for c in contexts if c in companions]}
