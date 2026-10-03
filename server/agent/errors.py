"""Agent 的可预期领域错误。"""


class AgentError(Exception):
    """所有可映射为稳定接口错误的 Agent 异常。"""


class InvalidAgentInput(AgentError):
    pass


class AgentRunNotFound(AgentError):
    pass


class AgentRunConflict(AgentError):
    pass


class AgentRunCancelled(AgentError):
    pass


class FinalizationInProgress(AgentError):
    pass


class SnapshotConflict(AgentError):
    pass


class InputTooLong(AgentError):
    pass


class RetrievalUnavailable(AgentError):
    pass
