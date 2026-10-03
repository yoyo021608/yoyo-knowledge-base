"""把受控工具调用转换为 DocumentSearchPort 请求。"""

import json
import logging
from dataclasses import asdict
from typing import Any, cast

from server.agent.ports import DocumentSearchPort
from server.agent.types import (
    RetrievalPlan,
    SearchMode,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

_LOGGER = logging.getLogger(__name__)


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是字符串")
    cleaned = value.strip()
    return cleaned or None


def _identifier_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError(f"{field} 必须是最多 20 项的数组")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} 只能包含非空字符串")
    return tuple(dict.fromkeys(item.strip() for item in value))


class DocumentToolAdapter:
    def __init__(self, port: DocumentSearchPort) -> None:
        self._port = port

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return (
            ToolDefinition(
                name="search_documents",
                description="按问题、专题、标签或指定文档版本查询当前用户的知识片段",
                permission="read",
            ),
        )

    def execute(self, user_id: str, call: ToolCall) -> ToolResult:
        if call.name != "search_documents":
            return ToolResult(False, "", "不支持的工具")
        try:
            arguments = cast(dict[str, Any], json.loads(call.arguments))
            query = arguments["query"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query 必须是非空字符串")
            mode = arguments.get("mode", "hybrid")
            if mode not in {"keyword", "full_text", "vector", "hybrid"}:
                raise ValueError("mode 不受支持")
            # user_id 只取可信调用参数，模型参数即使包含身份字段也会被忽略。
            plan = RetrievalPlan(
                query=query.strip(),
                mode=cast(SearchMode, mode),
                limit=min(max(int(arguments.get("limit", 8)), 1), 50),
                topic_id=_optional_text(arguments.get("topic_id"), "topic_id"),
                tag=_optional_text(arguments.get("tag"), "tag"),
                document_ids=_identifier_tuple(
                    arguments.get("document_ids"), "document_ids"
                ),
                version_ids=_identifier_tuple(
                    arguments.get("version_ids"), "version_ids"
                ),
            )
            values = self._port.search(user_id, plan)
            return ToolResult(
                True,
                json.dumps([asdict(value) for value in values], ensure_ascii=False),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return ToolResult(False, "", f"工具参数无效：{exc}")
        except Exception:
            _LOGGER.exception("agent.document_tool.failed")
            return ToolResult(False, "", "知识检索暂时不可用")
