"""由接入层统一转换的 sessions 领域预期错误。"""


class SessionsError(Exception):
    """会话领域预期错误的基类。"""


class InvalidSessionInput(SessionsError):
    """输入不符合会话业务规则。"""


class SessionNotFound(SessionsError):
    """会话不存在或不属于当前用户。"""


class MessageNotFound(SessionsError):
    """消息不存在或不属于当前用户。"""


class SessionBusy(SessionsError):
    """会话已有另一个活动 Run。"""


class SessionDeleting(SessionsError):
    """会话已进入删除流程，不能接收新结果。"""


class IdempotencyConflict(SessionsError):
    """同一业务键被重复使用且内容不一致。"""


class ResultNotFound(SessionsError):
    """研究、对比或练习结果不存在。"""
