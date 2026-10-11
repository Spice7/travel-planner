import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.api.deps import get_current_user
from backend.db.session import get_session
from backend.main import app
from backend.repositories import recommendations as recommendation_repository
from backend.schemas.recommendations import AspectWeight, RecommendationRequest
from backend.services import recommendations as recommendation_service
from backend.services import scrap_posts
from scrap_fixtures import build_engine

POST = """광안리 여행 둘째 날

오전에는 뮤지엄 원에 갔다. 전시가 몰입감 있었고 사진 찍기 좋았다.
뮤지엄 원은 바다가 보이는 통창이 정말 멋졌다. 다만 계단이 많아 부모님은 힘들어하셨다.

점심은 고릴라 브루잉 컴퍼니에서 먹었다. 음식이 맛있었지만 직원이 불친절했고 가격이 비쌌다.
이 글은 업체로부터 소정의 원고료를 받아 작성했습니다."""


def model_reply(*aspects: tuple[str, str, str, str], context: tuple[str, ...] = ()) -> str:
    return json.dumps({"traveler_context": list(context), "aspects": [
        {"category": c, "attribute": a, "sentiment": s, "evidence": e} for c, a, s, e in aspects]}, ensure_ascii=False)


class FakeModel:
    """청크에 들어 있는 문장마다 미리 정한 라벨을 모아 돌려준다. 호출 횟수를 센다.

    청크에는 이웃 장소의 단락도 섞일 수 있어 두 장소의 라벨이 함께 나오지만, 고른 장소 카테고리의 허용 aspect만 남는다.
    """

    calls = 0
    down = False

    async def chat(self, model, messages):
        FakeModel.calls += 1
        if FakeModel.down:
            raise httpx.ConnectError("down")
        chunk = messages[-1]["content"]
        aspects, context = [], ()
        if "통창" in chunk:
            aspects += [("scenery", "sea", "positive", "바다가 보이는 통창이 정말 멋졌다"),
                        ("walking_burden", "high", "negative", "계단이 많아 부모님은 힘들어하셨다"),
                        ("unknown_aspect", "x", "positive", "전시가 몰입감 있었고"),  # 허용 aspect가 아니라 버린다
                        ("scenery", "city", "positive", "원문에 없는 문장")]  # 근거가 원문에 없어 버린다
            context = ("parents",)
        if "음식이 맛있었지만" in chunk:
            aspects += [("food_quality", "good", "positive", "음식이 맛있었지만"),
                        ("staff_service", "unkind", "negative", "직원이 불친절했고"),
                        ("price", "expensive", "negative", "가격이 비쌌다")]
        return model_reply(*aspects, context=context)


class PureHelperTests(unittest.TestCase):
    def test_chunks_are_contiguous_slices_around_the_place(self):
        chunks = scrap_posts.select_chunks(POST, "뮤지엄 원")
        self.assertTrue(chunks and len(chunks) <= scrap_posts.MAX_CHUNKS)
        joined = "".join(POST[a:b] for a, b in chunks)
        self.assertIn("바다가 보이는 통창", joined)
        self.assertNotIn("이 글은 업체로부터", joined)  # 장소 이름 앞뒤 단락만
        long_text = "가" * 2000
        (a, b), = scrap_posts.select_chunks(long_text, "없는 장소")  # 이름이 없으면 앞에서부터, 긴 단락은 자른다
        self.assertEqual((a, b), (0, scrap_posts.CHUNK_LIMIT))

    def test_place_names_ignore_spacing_by_and_branch(self):
        self.assertIn("켄트호텔광안리바이켄싱턴", scrap_posts.place_keys("켄트호텔 광안리 by 켄싱턴"))
        self.assertIn("퍼니비어", scrap_posts.place_keys("퍼니비어 광안점"))
        self.assertIn("신세계백화점", scrap_posts.place_keys("신세계백화점 센텀시티점"))

    def test_hash_ignores_whitespace_and_promo_rules(self):
        self.assertEqual(scrap_posts.content_hash("a  b\n\nc"), scrap_posts.content_hash("a b c"))
        self.assertEqual(scrap_posts.promo_signals(POST), ["원고료", "소정의", "업체로부터"])

    def test_one_vote_per_aspect_per_post(self):
        votes, evidence, per_place = recommendation_service.scrap_votes([
            (31, 1, "scenery", "positive", "바다 전망"), (31, 1, "scenery", "positive", "또 바다"),  # 반복은 1표
            (31, 1, "walking_burden", "negative", "계단"),
            (31, 2, "scenery", "positive", "멋진 바다"), (31, 2, "scenery", "negative", "흐린 날"),  # 엇갈리면 중립
        ])
        self.assertEqual(votes, {(31, "scenery", "positive"): 1, (31, "walking_burden", "negative"): 1,
                                 (31, "scenery", "neutral"): 1})
        self.assertEqual(per_place, {31: 3})
        self.assertEqual(evidence[(31, "scenery", "positive")], "바다 전망")


class PostScrapApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = await build_engine()
        sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def test_session():
            async with sessions() as session:
                yield session
        app.dependency_overrides[get_session] = test_session
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id=1)
        FakeModel.calls, FakeModel.down = 0, False
        self.patches = [patch.object(scrap_posts, "OllamaClient", FakeModel),
                        patch.object(scrap_posts, "get_settings", lambda: SimpleNamespace(ollama_model="test-qlora"))]
        for p in self.patches:
            p.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        for p in self.patches:
            p.stop()
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def create(self, place_id: int, text: str = POST) -> httpx.Response:
        return await self.client.post("/api/v1/scraps/posts", json={"text": text, "place_id": place_id})

    async def test_place_candidates_and_search(self):
        found = (await self.client.post("/api/v1/scraps/place-candidates", json={"text": POST})).json()
        self.assertEqual([(c["name"], c["hits"]) for c in found], [("뮤지엄 원", 2), ("고릴라브루잉", 1)])
        self.assertEqual(FakeModel.calls, 0)  # 후보 찾기는 모델을 쓰지 않는다
        search = (await self.client.get("/api/v1/places", params={"q": "뮤지엄"})).json()
        self.assertEqual((search["total"], search["items"][0]["name"]), (1, "뮤지엄 원"))

    async def test_post_is_analyzed_into_verified_labels_with_positions(self):
        response = await self.create(31)
        self.assertEqual(response.status_code, 201)
        scrap = response.json()
        self.assertEqual((scrap["source_type"], scrap["status"], scrap["title"]), ("external", "analyzed", "광안리 여행 둘째 날"))
        content = scrap["content"]["content_text"]
        self.assertEqual(scrap["content"]["promo_signals"], ["원고료", "소정의", "업체로부터"])
        self.assertEqual(scrap["content"]["traveler_context"], ["parents"])
        labels = scrap["annotations"]
        self.assertEqual([(a["aspect"], a["sentiment"], a["status"]) for a in labels],
                         [("scenery", "positive", "suggested"), ("walking_burden", "negative", "suggested")])
        for a in labels:
            self.assertEqual(content[a["evidence_start"]:a["evidence_end"]], a["evidence"])
        self.assertLessEqual(FakeModel.calls, scrap_posts.MAX_CHUNKS)

    async def test_same_post_once_per_place_and_alongside_bookmark(self):
        self.assertEqual((await self.client.post("/api/v1/scraps", json={"place_id": 31})).status_code, 201)
        self.assertEqual((await self.create(31)).status_code, 201)  # 장소 찜과 글 스크랩은 따로
        again = await self.create(31, POST.replace("\n", "\n\n"))  # 공백만 다른 같은 글
        self.assertEqual((again.status_code, again.json()["error"]["message"]), (409, "이미 저장한 글입니다."))
        restaurant = (await self.create(33)).json()  # 같은 글을 다른 장소로
        self.assertEqual([a["aspect"] for a in restaurant["annotations"]], ["food_quality", "staff_service", "price"])

    async def test_failed_analysis_keeps_post_and_can_retry(self):
        FakeModel.down = True
        failed = (await self.create(31)).json()
        self.assertEqual((failed["status"], failed["annotations"]), ("failed", []))
        retry = await self.client.post(f"/api/v1/scraps/{failed['scrap_id']}/analyze")
        self.assertEqual((retry.status_code, retry.json()["error"]["code"]), (503, "MODEL_UNAVAILABLE"))
        FakeModel.down = False
        retry = (await self.client.post(f"/api/v1/scraps/{failed['scrap_id']}/analyze")).json()
        self.assertEqual((retry["status"], len(retry["annotations"])), ("analyzed", 2))

    async def test_confirm_marks_the_rest_rejected(self):
        scrap = (await self.create(31)).json()
        keep = scrap["annotations"][0]["annotation_id"]
        url = f"/api/v1/scraps/{scrap['scrap_id']}/annotations"
        done = (await self.client.put(url, json={"confirmed": [keep]})).json()
        self.assertEqual(done["status"], "confirmed")
        self.assertEqual([a["status"] for a in done["annotations"]], ["confirmed", "rejected"])
        self.assertEqual((await self.client.put(url, json={"confirmed": [999]})).status_code, 400)
        bookmark = (await self.client.post("/api/v1/scraps", json={"place_id": 32})).json()
        not_post = await self.client.put(f"/api/v1/scraps/{bookmark['scrap_id']}/annotations", json={"confirmed": []})
        self.assertEqual(not_post.status_code, 400)


class ScrapVotesInRecommendationTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmed_post_labels_count_one_vote_per_aspect(self):
        repo = recommendation_repository
        with (
            patch.object(repo, "user_scraps", new=AsyncMock(return_value=[SimpleNamespace(scrap_id=1, place_id=31, review_id=None)])),
            patch.object(repo, "review_places", new=AsyncMock(return_value={})),
            patch.object(repo, "places", new=AsyncMock(return_value={31: ("뮤지엄 원", "attraction")})),
            patch.object(repo, "review_counts", new=AsyncMock(return_value={31: 1})),
            patch.object(repo, "evidence", new=AsyncMock(return_value={})),
            patch.object(repo, "sentiment_counts", new=AsyncMock(return_value=[(31, "scenery", "negative", 1)])),
            patch.object(repo, "scrap_labels", new=AsyncMock(return_value=[
                (31, 5, "scenery", "positive", "바다 전망이 멋졌다"), (31, 5, "scenery", "positive", "또 바다"),
                (31, 6, "scenery", "positive", "통창 너머 바다"),
            ])),
            patch.object(recommendation_service, "interpret_requirements", new=AsyncMock(return_value=(
                [AspectWeight(aspect="scenery", label="경치", weight=1.0, keywords=["바다"])], [], "model"))),
        ):
            result = await recommendation_service.recommend(
                object(), user_id=1, request=RecommendationRequest(scrap_ids=[1], requirements="바다"))
        item = result.items[0]
        self.assertEqual(item.scrap_votes, 2)  # 글 2건, 같은 글의 반복은 1표
        self.assertEqual(item.strengths[0].mentions, 3)  # 리뷰 부정 1 + 글 긍정 2
        self.assertEqual(item.strengths[0].evidence, "바다 전망이 멋졌다")  # 리뷰 근거가 없으면 글의 근거
