from fastapi import APIRouter

from backend.api.deps import Session
from backend.api.errors import ApiError
from backend.schemas.users import LoginRequest, SignupRequest, TokenResponse, UserRead
from backend.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=UserRead)
async def signup(request: SignupRequest, session: Session) -> UserRead:
    try:
        return await user_service.signup(session, request)
    except user_service.EmailAlreadyExists:
        raise ApiError(409, "ALREADY_EXISTS", "이미 가입된 이메일입니다.") from None


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, session: Session) -> TokenResponse:
    token = await user_service.login(session, request)
    if token is None:
        raise ApiError(401, "INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.")
    return token
