"""邮箱规范化与密码凭证规则。

本文件只负责凭证规则；账户创建、登录和密码变更仍由各自的业务能力负责。
"""

import re

from pwdlib import PasswordHash

from server.users.errors import InvalidEmail, WeakPassword

_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_email(value: str) -> str:
    """规范化邮箱以便身份匹配，并拒绝无效输入。"""
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_PATTERN.fullmatch(email):
        raise InvalidEmail("请输入有效的邮箱地址")
    return email


class PasswordCredentials:
    """统一管理 users 模块的密码规则和 Argon2 摘要。"""

    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash("not-a-real-user-password")

    @staticmethod
    def validate(password: str) -> None:
        """执行注册和密码变更共同使用的密码规则。"""
        if len(password) < 10:
            raise WeakPassword("密码至少需要 10 个字符")
        if len(password) > 128:
            raise WeakPassword("密码不能超过 128 个字符")
        if password.isspace():
            raise WeakPassword("密码不能只包含空白字符")

    def hash(self, password: str) -> str:
        """校验密码并使用 Argon2 生成摘要。"""
        self.validate(password)
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """校验密码；摘要格式损坏时按不匹配处理。"""
        try:
            return self._hasher.verify(password, password_hash)
        except Exception:
            return False

    def consume_dummy_verification(self, password: str) -> None:
        """账户不存在时执行等量摘要校验，降低时序泄露风险。"""
        self.verify(password, self._dummy_hash)
