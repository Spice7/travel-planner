import unittest
from types import SimpleNamespace

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.api.deps import get_current_user
from backend.db.session import get_session
from backend.main import app
from scrap_fixtures import build_engine


class ScrapApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = await build_engine()
        sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def test_session():
            async with sessions() as session:
                yield session
        app.dependency_overrides[get_session] = test_session
        self.login(1)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()

    def login(self, user_id: int) -> None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id=user_id)

    async def post(self, **body) -> httpx.Response:
        return await self.client.post("/api/v1/scraps", json=body)

    async def test_place_scrap_once_with_place_summary(self):
        first = await self.post(place_id=31, title="뮤지엄 원", source_type="external")
        self.assertEqual(first.status_code, 201)
        body = first.json()
        self.assertEqual(body["source_type"], "internal")  # 클라이언트가 보낸 값은 무시
        self.assertEqual(body["place"], {"place_id": 31, "name": "뮤지엄 원", "category": "attraction", "region": "haeundae"})
        again = await self.post(place_id=31)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["error"], {"code": "ALREADY_EXISTS", "message": "이미 스크랩한 장소입니다."})

    async def test_other_reviews_of_same_place_are_allowed(self):
        review_a = await self.post(review_id=101)
        self.assertEqual(review_a.status_code, 201)
        self.assertEqual(review_a.json()["place_id"], 31)  # 리뷰의 장소를 함께 저장
        self.assertEqual((await self.post(review_id=102)).status_code, 201)
        self.assertEqual((await self.post(place_id=31)).status_code, 201)  # 장소 찜은 리뷰 저장과 별개
        again = await self.post(review_id=101)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["error"]["message"], "이미 스크랩한 리뷰입니다.")

    async def test_external_link_is_external(self):
        response = await self.post(source_url="https://example.com/post")
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.json()["source_type"], response.json()["place"]), ("external", None))

    async def test_missing_or_mismatched_targets(self):
        self.assertEqual((await self.post(place_id=999)).json()["error"]["code"], "PLACE_NOT_FOUND")
        self.assertEqual((await self.post(review_id=999)).json()["error"]["code"], "REVIEW_NOT_FOUND")
        mismatch = await self.post(review_id=101, place_id=32)
        self.assertEqual((mismatch.status_code, mismatch.json()["error"]["code"]), (400, "INVALID_REQUEST"))

    async def test_list_is_paged_filtered_and_per_user(self):
        for body in ({"place_id": 31}, {"place_id": 32}, {"source_url": "https://example.com/a"}):
            await self.post(**body)
        self.login(2)
        await self.post(place_id=31)
        self.login(1)

        page = (await self.client.get("/api/v1/scraps", params={"page": 1, "size": 2})).json()
        self.assertEqual((page["page"], page["size"], page["total"], len(page["items"])), (1, 2, 3, 2))
        self.assertEqual(page["items"][0]["source_type"], "external")  # 최신순
        by_place = (await self.client.get("/api/v1/scraps", params={"place_id": 32})).json()
        self.assertEqual([item["place"]["name"] for item in by_place["items"]], ["지역 없는 곳"])
        self.assertIsNone(by_place["items"][0]["place"]["region"])
        external = (await self.client.get("/api/v1/scraps", params={"source_type": "external"})).json()
        self.assertEqual(external["total"], 1)

        self.login(2)
        mine = (await self.client.get("/api/v1/scraps")).json()
        self.assertEqual((mine["total"], mine["items"][0]["user_id"]), (1, 2))
