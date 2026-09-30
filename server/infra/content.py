"""外部资料读取的基础设施契约。"""

from dataclasses import dataclass
from typing import Protocol


class DocumentContentError(ValueError):
    """网页或文件因为网络、格式或安全限制无法读取。"""


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    """从网页或文件中提取的标题和纯文本正文。"""

    title: str
    content: str


class DocumentContentLoader(Protocol):
    """供业务模块注入使用的网页抓取和文件解析端口。"""

    def fetch_web(self, url: str) -> ExtractedContent:
        """安全抓取公开网页并提取可读正文。"""

    def extract_file(
        self, name: str, content: bytes, content_type: str
    ) -> ExtractedContent:
        """按文件格式提取可建立索引的文本。"""
