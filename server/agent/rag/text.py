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
    """按实际预算估算截取前缀，长英文串和标点也不能绕过上限。"""
    if limit <= 0:
        return ""
    if token_count(text) <= limit:
        return text.strip()
    lower, upper = 0, len(text)
    while lower < upper:
        middle = (lower + upper + 1) // 2
        if token_count(text[:middle]) <= limit:
            lower = middle
        else:
            upper = middle - 1
    return text[:lower].strip()
