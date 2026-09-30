"""users 模块的 HTTP 入口。"""

from server.controller.users.router import get_users, require_identity, router

__all__ = ["get_users", "require_identity", "router"]
