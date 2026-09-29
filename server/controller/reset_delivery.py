"""由应用装配层选择的密码重置通知适配器。

开发适配器向本地界面返回真实凭证或同形态的伪凭证；生产环境禁止通过 HTTP
暴露重置凭证，接入邮件或短信时实现 users 定义的同一端口。
"""

import secrets

from server.config import Settings
from server.users.errors import ResetDeliveryUnavailable
from server.users.passwords import PasswordResetDelivery
from server.users.types import PasswordResetGrant


class DevelopmentHttpResetDelivery:
    """向本地开发界面返回凭证，同时隐藏账户是否存在。"""

    def ensure_available(self) -> None:
        """开发和测试环境始终允许使用本地 HTTP 通知方式。"""

    def deliver(self, email: str, grant: PasswordResetGrant | None) -> str:
        """向本地调用方返回真实凭证或同形态的伪凭证。"""
        del email
        return grant.token if grant is not None else secrets.token_urlsafe(32)


class ProductionResetDelivery:
    """真实外部通知器配置完成前拒绝生产环境重置请求。"""

    def ensure_available(self) -> None:
        """明确报告适配器缺失，避免静默丢失重置凭证。"""
        raise ResetDeliveryUnavailable("密码重置通知服务尚未配置")

    def deliver(self, email: str, grant: PasswordResetGrant | None) -> None:
        """即使绕过可用性预检直接调用，也必须拒绝发送。"""
        del email, grant
        self.ensure_available()


def create_reset_delivery(settings: Settings) -> PasswordResetDelivery:
    """根据运行环境在应用装配边界选择通知适配器。"""

    if settings.app_env in {"development", "test"}:
        return DevelopmentHttpResetDelivery()
    return ProductionResetDelivery()
