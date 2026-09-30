"""账户与认证操作的 HTTP 边界。

本 controller 校验请求数据、解析 Bearer 凭证、调用 users 公开能力并转换领域错误，
不直接查询账户数据表。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from server.config import Settings
from server.users.errors import (
    EmailAlreadyRegistered,
    InvalidAccessToken,
    InvalidCredentials,
    InvalidEmail,
    InvalidResetToken,
    ResetDeliveryUnavailable,
    WeakPassword,
)
from server.users.module import UsersModule
from server.users.types import IdentityContext

router = APIRouter(prefix="/api", tags=["users"])
_bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    """创建账户的 HTTP 输入。"""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    """密码登录的 HTTP 输入。"""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """不含任何凭证字段的公开账户身份。"""

    id: str
    email: str


class LoginResponse(BaseModel):
    """包含一个可撤销 Bearer 会话的登录响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """登录用户修改密码的 HTTP 输入。"""

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class PasswordResetRequest(BaseModel):
    """申请密码重置通知的 HTTP 输入。"""

    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirmRequest(BaseModel):
    """消费一次性重置凭证的 HTTP 输入。"""

    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=10, max_length=128)


class MessageResponse(BaseModel):
    """不泄露账户是否存在的响应；凭证字段只供本地开发使用。"""

    message: str
    development_reset_token: str | None = None


def get_users(request: Request) -> UsersModule:
    """从应用状态取得已经装配完成的 users 能力。"""
    return request.app.state.users  # type: ignore[no-any-return]


def get_runtime_settings(request: Request) -> Settings:
    """取得只影响 HTTP 响应行为的运行配置。"""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """提取 Bearer 凭证，此处暂不解析领域身份。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def require_identity(
    users: Annotated[UsersModule, Depends(get_users)],
    access_token: Annotated[str, Depends(get_access_token)],
) -> IdentityContext:
    """通过 users 模块解析并校验当前调用者身份。"""
    try:
        return users.identity.require(access_token)
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/users/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    body: RegisterRequest,
    users: Annotated[UsersModule, Depends(get_users)],
) -> UserResponse:
    """创建账户并只返回公开资料。"""
    try:
        profile = users.registration.register(body.email, body.password)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except (InvalidEmail, WeakPassword) as exc:
        raise _bad_request(exc) from exc
    return UserResponse(id=profile.id, email=profile.email)


@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    users: Annotated[UsersModule, Depends(get_users)],
) -> LoginResponse:
    """校验登录信息并返回绑定持久化会话的访问令牌。"""
    try:
        authenticated = users.login_sessions.login(body.email, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return LoginResponse(
        access_token=authenticated.token.access_token,
        expires_at=authenticated.token.expires_at,
        user=UserResponse(
            id=authenticated.profile.id,
            email=authenticated.profile.email,
        ),
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    users: Annotated[UsersModule, Depends(get_users)],
    access_token: Annotated[str, Depends(get_access_token)],
) -> Response:
    """只撤销传入凭证所代表的当前登录会话。"""
    try:
        users.login_sessions.logout(access_token)
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me", response_model=UserResponse)
def current_user(
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> UserResponse:
    """返回当前请求已经校验完成的用户身份。"""
    return UserResponse(id=identity.user_id, email=identity.email)


@router.post("/users/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    users: Annotated[UsersModule, Depends(get_users)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> Response:
    """修改密码并撤销当前用户的全部登录会话。"""
    try:
        users.passwords.change_password(
            identity.user_id,
            body.old_password,
            body.new_password,
        )
    except (InvalidCredentials, WeakPassword) as exc:
        raise _bad_request(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/auth/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    body: PasswordResetRequest,
    users: Annotated[UsersModule, Depends(get_users)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> MessageResponse:
    """受理重置请求，同时避免泄露邮箱是否已经注册。"""
    try:
        development_token = users.passwords.request_reset(body.email)
    except ResetDeliveryUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return MessageResponse(
        message="如果该邮箱存在，密码重置请求已受理",
        # 本地开发没有邮件服务；未知账户也返回同形态伪凭证，避免泄露账户状态。
        development_reset_token=(
            development_token if settings.app_env in {"development", "test"} else None
        ),
    )


@router.post("/auth/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    body: PasswordResetConfirmRequest,
    users: Annotated[UsersModule, Depends(get_users)],
) -> Response:
    """消费重置凭证、替换密码并撤销全部登录会话。"""
    try:
        users.passwords.reset_password(body.token, body.new_password)
    except (InvalidResetToken, WeakPassword) as exc:
        raise _bad_request(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
