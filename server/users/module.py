"""users 模块内部装配。

应用入口在这里注入数据库、配置和外部端口，最终只暴露文档定义的四项业务能力。
"""

from dataclasses import dataclass

from server.config import Settings
from server.infra.database import Database
from server.users.authentication import (
    AccessTokenCodec,
    IdentityResolver,
    LoginSessions,
)
from server.users.credentials import PasswordCredentials
from server.users.passwords import PasswordManagement, PasswordResetDelivery
from server.users.registration import Registration

ACCESS_TOKEN_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = 60


@dataclass(frozen=True, slots=True)
class UsersModule:
    """提供给 controller 和可信调用方的 users 公开能力集合。"""

    registration: Registration
    login_sessions: LoginSessions
    passwords: PasswordManagement
    identity: IdentityResolver

    @classmethod
    def create(
        cls,
        database: Database,
        settings: Settings,
        reset_delivery: PasswordResetDelivery,
    ) -> "UsersModule":
        """使用同一数据库和重置通知端口装配 users 的四项能力。"""
        credentials = PasswordCredentials()
        tokens = AccessTokenCodec(settings.jwt_secret, ACCESS_TOKEN_ALGORITHM)
        return cls(
            registration=Registration(database, credentials),
            login_sessions=LoginSessions(
                database,
                credentials,
                tokens,
                ACCESS_TOKEN_TTL_MINUTES,
            ),
            passwords=PasswordManagement(
                database,
                credentials,
                settings.password_reset_token_ttl_minutes,
                reset_delivery,
            ),
            identity=IdentityResolver(database, tokens),
        )
