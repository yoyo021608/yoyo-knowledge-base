"""users 模块对外传递且不依赖框架的数据类型。

这些不可变类型用于把 ORM 模型和密码摘要限制在 users 模块内部。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class UserProfile:
    """允许传出 users 模块的安全账户资料。"""

    id: str
    email: str


@dataclass(frozen=True, slots=True)
class AuthToken:
    """登录后返回的访问凭证及其有效期。"""

    access_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """包含访问凭证和公开资料的登录结果。"""

    token: AuthToken
    profile: UserProfile


@dataclass(frozen=True, slots=True)
class IdentityContext:
    """注入受保护操作的可信调用者身份。"""

    user_id: str
    email: str


@dataclass(frozen=True, slots=True)
class PasswordResetGrant:
    """只允许交给通知适配器的原始重置凭证。"""

    token: str
    expires_at: datetime
