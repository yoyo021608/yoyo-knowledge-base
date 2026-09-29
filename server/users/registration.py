"""账户注册能力。

本文件负责邮箱校验、密码摘要和原子创建用户；不创建登录会话，也不向外暴露凭证记录。
"""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from server.infra.database import Database
from server.users.credentials import PasswordCredentials, normalize_email
from server.users.errors import EmailAlreadyRegistered
from server.users.models import User
from server.users.types import UserProfile


class Registration:
    """创建用户账户并返回不含凭证的公开资料。"""

    def __init__(self, database: Database, credentials: PasswordCredentials) -> None:
        self._database = database
        self._credentials = credentials

    def register(self, email: str, password: str) -> UserProfile:
        """校验输入并原子创建规范化账户。"""
        normalized_email = normalize_email(email)
        password_hash = self._credentials.hash(password)
        user = User(
            id=str(uuid4()),
            email=normalized_email,
            password_hash=password_hash,
        )
        try:
            with self._database.transaction() as session:
                session.add(user)
                session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyRegistered("该邮箱已注册") from exc
        return UserProfile(id=user.id, email=user.email)

    def find_by_email(self, email: str) -> User | None:
        """按邮箱读取内部凭证记录，禁止通过 HTTP 直接返回。"""
        normalized_email = normalize_email(email)
        with self._database.session() as session:
            return session.scalar(select(User).where(User.email == normalized_email))
