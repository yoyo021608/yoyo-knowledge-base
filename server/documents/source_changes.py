"""网页来源复查归 documents 所有，版本写入复用文档编辑规则。"""

import logging
from datetime import UTC, datetime, timedelta
from difflib import unified_diff
from itertools import islice

from sqlalchemy import or_, select, update

from server.documents.documents import DocumentEditor, clean_content
from server.documents.errors import DocumentsError, InvalidDocumentInput
from server.documents.models import Document, SourceSnapshot
from server.documents.types import DocumentUpdateInput, SourceChangeView
from server.infra.content import DocumentContentError, DocumentContentLoader
from server.infra.database import Database

_LOGGER = logging.getLogger(__name__)


class SourceChangeManager:
    def __init__(
        self,
        database: Database,
        editor: DocumentEditor,
        loader: DocumentContentLoader | None,
    ) -> None:
        self._database = database
        self._editor = editor
        self._loader = loader

    def check(self, document_id: str, user_id: str) -> SourceChangeView:
        """按当前版本抓取网页；仅正文变化时原子创建新版本。"""
        detail = self._editor.get(document_id, user_id)
        source = detail.version.source
        if source.source_type != "web" or not source.source_url:
            raise InvalidDocumentInput("仅网页资料可以检查来源更新")
        if self._loader is None:
            raise InvalidDocumentInput("未配置网页内容读取服务")
        try:
            latest = self._loader.fetch_web(source.source_url)
        except DocumentContentError as exc:
            raise InvalidDocumentInput(str(exc)) from exc
        previous = detail.version.content_snapshot
        current = clean_content(latest.content)
        if current == previous:
            with self._database.transaction() as session:
                session.execute(
                    update(Document)
                    .where(
                        Document.id == document_id,
                        Document.current_version_id == detail.version.id,
                    )
                    .values(source_checked_at=datetime.now(UTC))
                )
            return SourceChangeView(False, detail.version.id, detail.version.id, "")
        diff = "".join(
            islice(
                unified_diff(
                    previous.splitlines(keepends=True),
                    current.splitlines(keepends=True),
                    fromfile=f"v{detail.version.version}",
                    tofile=f"v{detail.version.version + 1}",
                ),
                120,
            )
        )[:12000]
        updated = self._editor.update(
            document_id,
            user_id,
            DocumentUpdateInput(
                title=detail.document.title,
                content=current,
                topic_id=detail.document.topic_id,
                tags=detail.document.tags,
                source_url=source.source_url,
            ),
            expected_version_id=detail.version.id,
        )
        with self._database.transaction() as session:
            session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.current_version_id == updated.id,
                )
                .values(
                    source_checked_at=datetime.now(UTC),
                    source_changed_at=datetime.now(UTC),
                    source_change_diff=diff,
                )
            )
        return SourceChangeView(True, detail.version.id, updated.id, diff)

    def check_due(self, *, limit: int = 10, interval_hours: int = 24) -> int:
        """周期复查到期网页；一次限制数量，失败留在日志并延后重试。"""
        if self._loader is None:
            return 0
        cutoff = datetime.now(UTC) - timedelta(hours=interval_hours)
        with self._database.session() as session:
            due = session.execute(
                select(Document.id, Document.user_id, Document.current_version_id)
                .join(
                    SourceSnapshot,
                    SourceSnapshot.version_id == Document.current_version_id,
                )
                .where(
                    Document.status == "active",
                    SourceSnapshot.source_type == "web",
                    or_(
                        Document.source_checked_at.is_(None),
                        Document.source_checked_at < cutoff,
                    ),
                )
                .order_by(Document.source_checked_at, Document.created_at)
                .limit(limit)
            ).all()
        for document_id, user_id, version_id in due:
            try:
                self.check(document_id, user_id)
            except DocumentsError:
                _LOGGER.warning(
                    "documents.source_check.failed",
                    extra={"document_id": document_id},
                    exc_info=True,
                )
                with self._database.transaction() as session:
                    session.execute(
                        update(Document)
                        .where(
                            Document.id == document_id,
                            Document.current_version_id == version_id,
                        )
                        .values(source_checked_at=datetime.now(UTC))
                    )
        return len(due)
