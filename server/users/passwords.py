"""密码修改与密码重置。

本文件管理密码变更、一次性重置凭证及通知端口。邮件或短信的具体发送方式由
装配层提供，users 模块只规定发送能力的接口。
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select, update

from server.infra.database import Database
from server.users.authentication import LoginSessions
from server.users.credentials import PasswordCredentials, normalize_email
from server.users.errors import InvalidCredentials, InvalidEmail, InvalidResetToken
from server.users.models import PasswordResetToken, User, as_utc
from server.users.types import PasswordResetGrant


def _hash_reset_token(token: str) -> str:
    """只保存重置凭证摘要，避免数据库泄露后直接使用原始凭证。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PasswordResetDelivery(Protocol):
    """密码重置通知端口，不暴露账户是否存在的判断。"""

    def ensure_available(self) -> None:
        """在创建凭证前确认通知渠道可用。"""

    def deliver(self, email: str, grant: PasswordResetGrant | None) -> str | None:
        """发送真实凭证；账户不存在时执行不可区分的等价处理。"""
        ...


class PasswordManagement:
    """修改密码并管理短时有效、只能使用一次的重置凭证。"""

    def __init__(
        self,
        database: Database,
        credentials: PasswordCredentials,
        reset_ttl_minutes: int,
        reset_delivery: PasswordResetDelivery,
    ) -> None:
        self._database = database
        self._credentials = credentials
        self._reset_ttl = timedelta(minutes=reset_ttl_minutes)
        self._reset_delivery = reset_delivery

    def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> None:
        """校验原密码、保存新摘要，并撤销该用户的全部登录会话。"""
        new_password_hash = self._credentials.hash(new_password)
        now = datetime.now(UTC)
        with self._database.transaction() as session:
            user = session.get(User, user_id)
            if user is None or not self._credentials.verify(
                old_password, user.password_hash
            ):
                raise InvalidCredentials("原密码错误")
            if self._credentials.verify(new_password, user.password_hash):
                raise InvalidCredentials("新密码不能与原密码相同")
            user.password_hash = new_password_hash
            user.updated_at = now
            LoginSessions.revoke_all(session, user.id, now)

    def request_reset(self, email: str) -> str | None:
        """创建短时重置凭证并交给通知端口，同时隐藏账户是否存在。"""
        # 先检查通知渠道，避免生产环境创建一个永远无法送达的凭证。
        self._reset_delivery.ensure_available()
        now = datetime.now(UTC)
        raw_token = secrets.token_urlsafe(32)
        expires_at = now + self._reset_ttl
        try:
            normalized_email = normalize_email(email)
        except InvalidEmail:
            return self._reset_delivery.deliver(email, None)
        with self._database.transaction() as session:
            user = session.scalar(select(User).where(User.email == normalized_email))
            if user is None:
                return self._reset_delivery.deliver(normalized_email, None)
            session.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .values(used_at=now)
            )
            session.add(
                PasswordResetToken(
                    id=str(uuid4()),
                    token_hash=_hash_reset_token(raw_token),
                    user_id=user.id,
                    expires_at=expires_at,
                )
            )
            grant = PasswordResetGrant(token=raw_token, expires_at=expires_at)
        return self._reset_delivery.deliver(normalized_email, grant)

    def reset_password(self, token: str, new_password: str) -> None:
        """原子消费一次性凭证、更新密码摘要并撤销全部登录会话。"""
        new_password_hash = self._credentials.hash(new_password)
        now = datetime.now(UTC)
        token_hash = _hash_reset_token(token)
        with self._database.transaction() as session:
            reset_token = session.scalar(
                select(PasswordResetToken)
                .where(PasswordResetToken.token_hash == token_hash)
                .with_for_update()
            )
            if (
                reset_token is None
                or reset_token.used_at is not None
                or as_utc(reset_token.expires_at) <= now
            ):
                raise InvalidResetToken("重置凭证无效或已过期")
            user = session.get(User, reset_token.user_id)
            if user is None:
                raise InvalidResetToken("重置凭证无效或已过期")
            reset_token.used_at = now
            user.password_hash = new_password_hash
            user.updated_at = now
            LoginSessions.revoke_all(session, user.id, now)
            session.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .values(used_at=now)
            )
