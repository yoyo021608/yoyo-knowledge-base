"""账户认证与登录会话。

本文件统一管理登录、注销、访问令牌和当前身份解析。它只回答“用户是谁”以及
“登录会话是否有效”，不判断用户能否访问文档、会话或 Agent 任务。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from server.infra.database import Database
from server.users.credentials import PasswordCredentials, normalize_email
from server.users.errors import InvalidAccessToken, InvalidCredentials, InvalidEmail
from server.users.models import User, UserLoginSession, as_utc
from server.users.types import (
    AuthenticatedUser,
    AuthToken,
    IdentityContext,
    UserProfile,
)


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """访问令牌校验成功后得到的用户标识和登录会话标识。"""

    user_id: str
    session_id: str


class AccessTokenCodec:
    """负责创建和严格校验 users 模块使用的 JWT 访问令牌。"""

    def __init__(self, secret: str, algorithm: str) -> None:
        self._secret = secret
        self._algorithm = algorithm

    def encode(self, user_id: str, session_id: str, expires_at: datetime) -> str:
        """创建同时绑定用户和持久化登录会话的访问令牌。"""
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": user_id,
            "sid": session_id,
            "type": "access",
            "iat": now,
            "exp": expires_at,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> AccessTokenClaims:
        """校验签名、有效期、必要字段和令牌类型。"""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["sub", "sid", "type", "iat", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidAccessToken("登录凭证无效或已过期") from exc
        if payload.get("type") != "access":
            raise InvalidAccessToken("登录凭证类型无效")
        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not isinstance(user_id, str) or not isinstance(session_id, str):
            raise InvalidAccessToken("登录凭证内容无效")
        return AccessTokenClaims(user_id=user_id, session_id=session_id)


class LoginSessions:
    """校验登录密码、创建登录会话、签发凭证并撤销会话。"""

    def __init__(
        self,
        database: Database,
        credentials: PasswordCredentials,
        tokens: AccessTokenCodec,
        ttl_minutes: int,
    ) -> None:
        self._database = database
        self._credentials = credentials
        self._tokens = tokens
        self._ttl = timedelta(minutes=ttl_minutes)

    def login(self, email: str, password: str) -> AuthenticatedUser:
        """校验邮箱和密码，创建会话并返回访问令牌与公开资料。"""
        try:
            normalized_email = normalize_email(email)
        except InvalidEmail:
            self._credentials.consume_dummy_verification(password)
            raise InvalidCredentials("邮箱或密码错误") from None

        with self._database.transaction() as session:
            user = session.scalar(select(User).where(User.email == normalized_email))
            if user is None:
                self._credentials.consume_dummy_verification(password)
                raise InvalidCredentials("邮箱或密码错误")
            if not self._credentials.verify(password, user.password_hash):
                raise InvalidCredentials("邮箱或密码错误")

            expires_at = datetime.now(UTC) + self._ttl
            login_session = UserLoginSession(
                id=str(uuid4()),
                user_id=user.id,
                expires_at=expires_at,
            )
            session.add(login_session)
            session.flush()
            access_token = self._tokens.encode(user.id, login_session.id, expires_at)
            return AuthenticatedUser(
                token=AuthToken(access_token=access_token, expires_at=expires_at),
                profile=UserProfile(id=user.id, email=user.email),
            )

    def logout(self, access_token: str) -> None:
        """只撤销访问令牌所对应的当前登录会话。"""
        claims = self._tokens.decode(access_token)
        now = datetime.now(UTC)
        with self._database.transaction() as session:
            login_session = session.scalar(
                select(UserLoginSession).where(
                    UserLoginSession.id == claims.session_id,
                    UserLoginSession.user_id == claims.user_id,
                )
            )
            if login_session is None:
                raise InvalidAccessToken("登录会话不存在")
            if as_utc(login_session.expires_at) <= now:
                raise InvalidAccessToken("登录会话已过期")
            if login_session.revoked_at is None:
                login_session.revoked_at = now

    @staticmethod
    def revoke_all(session: Session, user_id: str, revoked_at: datetime) -> None:
        """在调用方事务中撤销指定用户的全部有效登录会话。"""
        session.execute(
            update(UserLoginSession)
            .where(
                UserLoginSession.user_id == user_id,
                UserLoginSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )


class IdentityResolver:
    """把访问令牌和持久化会话解析成可信的当前用户身份。"""

    def __init__(self, database: Database, tokens: AccessTokenCodec) -> None:
        self._database = database
        self._tokens = tokens

    def require(self, access_token: str) -> IdentityContext:
        """拒绝过期或已撤销会话，并返回当前用户身份。"""
        claims = self._tokens.decode(access_token)
        with self._database.session() as session:
            row = session.execute(
                select(User, UserLoginSession)
                .join(UserLoginSession, UserLoginSession.user_id == User.id)
                .where(
                    User.id == claims.user_id,
                    UserLoginSession.id == claims.session_id,
                )
            ).one_or_none()
            if row is None:
                raise InvalidAccessToken("登录会话不存在")
            user, login_session = row
            if login_session.revoked_at is not None:
                raise InvalidAccessToken("登录会话已撤销")
            if as_utc(login_session.expires_at) <= datetime.now(UTC):
                raise InvalidAccessToken("登录会话已过期")
            return IdentityContext(user_id=user.id, email=user.email)
