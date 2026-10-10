import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend.api.deps import get_current_user
from backend.db.session import get_session
from backend.main import app
from backend.services import places as place_service


class ErrorResponseTests(unittest.IsolatedAsyncioTestCase):
    """API 명세서의 공통 에러 형식 {"error": {"code", "message"}}을 지키는지 확인한다."""

    async def asyncSetUp(self):
        async def fake_session():
            yield object()
        app.dependency_overrides[get_session] = fake_session
        # 처리되지 않은 예외도 500 응답으로 받아 보려고 앱 예외를 테스트로 다시 던지지 않는다.
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()

    def assertError(self, response: httpx.Response, status: int, code: str) -> str:
        self.assertEqual(response.status_code, status)
        body = response.json()
        self.assertEqual(set(body), {"error"})
        self.assertEqual(body["error"]["code"], code)
        return body["error"]["message"]

    async def test_route_error_uses_its_code_and_korean_message(self):
        with patch.object(place_service, "get_place_detail", new=AsyncMock(return_value=None)):
            response = await self.client.get("/api/v1/places/999")
        self.assertEqual(self.assertError(response, 404, "PLACE_NOT_FOUND"), "장소를 찾을 수 없습니다.")

    async def test_missing_token_is_unauthorized(self):
        response = await self.client.get("/api/v1/users/me")
        self.assertEqual(self.assertError(response, 401, "UNAUTHORIZED"), "로그인이 필요합니다.")
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    async def test_validation_error_is_400_and_names_the_field(self):
        response = await self.client.get("/api/v1/places", params={"size": 0})
        self.assertIn("size", self.assertError(response, 400, "INVALID_REQUEST"))

    async def test_validator_message_is_shown_as_is(self):
        app.dependency_overrides[get_current_user] = lambda: object()
        response = await self.client.post("/api/v1/scraps", json={})
        self.assertEqual(self.assertError(response, 400, "INVALID_REQUEST"), "place_id, review_id, source_url 중 하나는 있어야 합니다.")

    async def test_unknown_path_and_unhandled_error(self):
        self.assertError(await self.client.get("/api/v1/nowhere"), 404, "NOT_FOUND")
        with patch.object(place_service, "get_place_detail", new=AsyncMock(side_effect=RuntimeError("boom"))):
            with self.assertLogs("backend.api.errors", level="ERROR"):
                response = await self.client.get("/api/v1/places/1")
        self.assertEqual(self.assertError(response, 500, "INTERNAL_ERROR"), "서버 오류가 발생했습니다.")
