"""只服务 RAG 的文本切词和 token 估算，不作为跨业务通用工具。"""

import re
from math import ceil

_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


def tokens(text: str) -> tuple[str, ...]:
    return tuple(value.casefold() for value in _TOKEN.findall(text))


def token_count(text: str) -> int:
    """给预算使用的保守估算；同时覆盖中文、标点和长英文内容。"""
    if not text:
        return 0
    return max(len(tokens(text)), ceil(len(text.encode("utf-8")) / 3))


def take_tokens(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    matches = list(_TOKEN.finditer(text))
    if len(matches) <= limit:
        return text.strip()
    return text[: matches[limit - 1].end()].strip()
