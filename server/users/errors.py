"""由 HTTP 边界统一转换的 users 领域预期错误。"""


class UsersError(Exception):
    """账户领域预期错误的基类。"""


class InvalidEmail(UsersError):
    """邮箱无法规范化为有效地址时抛出。"""


class WeakPassword(UsersError):
    """密码不符合 users 模块规则时抛出。"""


class EmailAlreadyRegistered(UsersError):
    """注册时邮箱已经存在时抛出。"""


class InvalidCredentials(UsersError):
    """登录或原密码校验失败时抛出。"""


class InvalidAccessToken(UsersError):
    """访问令牌或对应持久化会话无效时抛出。"""


class InvalidResetToken(UsersError):
    """重置凭证不存在、已过期或已使用时抛出。"""


class ResetDeliveryUnavailable(UsersError):
    """没有配置密码重置通知适配器时抛出。"""
