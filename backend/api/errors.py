"""API 명세서의 공통 에러 형식 {"error": {"code", "message"}}으로 응답한다.

라우트는 ApiError로 code와 사용자에게 보여 줄 한국어 message를 정한다. 그 밖의 HTTP 에러(없는 경로 등)는
상태 코드별 기본값을 쓰고, 입력 검증 실패는 명세서대로 422가 아니라 400 INVALID_REQUEST로 바꾼다.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

DEFAULTS: dict[int, tuple[str, str]] = {
    400: ("INVALID_REQUEST", "요청 값을 확인해 주세요."),
    401: ("UNAUTHORIZED", "로그인이 필요합니다."),
    403: ("FORBIDDEN", "접근 권한이 없습니다."),
    404: ("NOT_FOUND", "요청한 항목을 찾을 수 없습니다."),
    405: ("METHOD_NOT_ALLOWED", "지원하지 않는 요청 방식입니다."),
    409: ("ALREADY_EXISTS", "이미 존재합니다."),
    503: ("SERVICE_UNAVAILABLE", "잠시 후 다시 시도해 주세요."),
}


class ApiError(StarletteHTTPException):
    def __init__(self, status_code: int, code: str, message: str, headers: dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code


def error_response(status_code: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code, headers=headers)


def _validation_message(errors: list[dict[str, Any]]) -> str:
    # 모델 검증기가 직접 쓴 문장(ValueError)이 있으면 그대로, 아니면 문제가 된 필드 이름을 알려 준다.
    for error in errors:
        if error.get("type") == "value_error" and "error" in error.get("ctx", {}):
            return str(error["ctx"]["error"])
    fields = sorted({str(error["loc"][-1]) for error in errors if len(error.get("loc", ())) > 1})
    return f"요청 값을 확인해 주세요: {', '.join(fields)}" if fields else DEFAULTS[400][1]


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc, ApiError):
        return error_response(exc.status_code, exc.code, exc.detail, exc.headers)
    code, message = DEFAULTS.get(exc.status_code, ("ERROR", "요청을 처리하지 못했습니다."))
    return error_response(exc.status_code, code, message, exc.headers)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(400, "INVALID_REQUEST", _validation_message(list(exc.errors())))


async def _server_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "INTERNAL_ERROR", "서버 오류가 발생했습니다.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _server_error)
