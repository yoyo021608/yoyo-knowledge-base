"""用户知识导出。

导出只读取当前用户筛选范围内的 active 文档，不修改资料，也不承担重新导入。
"""

import json
from dataclasses import asdict

from server.documents.documents import DocumentEditor
from server.documents.errors import UnsupportedExportFormat
from server.documents.types import DocumentFilter, ExportRequest, ExportResult


class DocumentExporter:
    """把当前版本及来源整理成 Markdown 或 JSON 下载内容。"""

    def __init__(self, editor: DocumentEditor) -> None:
        self._editor = editor

    def export(self, request: ExportRequest) -> ExportResult:
        """按文档、专题和标签筛选后导出，归属由编辑器统一阻断。"""
        if request.format not in {"markdown", "json"}:
            raise UnsupportedExportFormat("导出格式必须是 markdown 或 json")
        documents = self._editor.list(
            request.user_id,
            DocumentFilter(topic_id=request.topic_id, tag=request.tag, status="active"),
        )
        if request.document_ids:
            selected = set(request.document_ids)
            documents = tuple(
                document for document in documents if document.id in selected
            )
        details = tuple(
            self._editor.get(document.id, request.user_id) for document in documents
        )
        if request.format == "json":
            payload = [
                {
                    "document": asdict(detail.document),
                    "version": asdict(detail.version),
                }
                for detail in details
            ]
            return ExportResult(
                file_name="knowledge-base.json",
                content=json.dumps(
                    payload, ensure_ascii=False, indent=2, default=str
                ).encode("utf-8"),
                media_type="application/json",
            )

        sections: list[str] = ["# 个人知识库导出"]
        for detail in details:
            source = detail.version.source
            metadata = [
                f"- 文档 ID：`{detail.document.id}`",
                f"- 版本：{detail.version.version}",
                f"- 来源类型：{source.source_type}",
            ]
            if source.source_url:
                metadata.append(f"- 来源地址：{source.source_url}")
            if detail.document.tags:
                metadata.append(f"- 标签：{', '.join(detail.document.tags)}")
            sections.append(
                "\n".join(
                    [
                        f"## {detail.document.title}",
                        *metadata,
                        "",
                        detail.version.content_snapshot,
                    ]
                )
            )
        return ExportResult(
            file_name="knowledge-base.md",
            content=("\n\n---\n\n".join(sections) + "\n").encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
        )
