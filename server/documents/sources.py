"""来源快照管理。

来源随版本冻结，录入和编辑只能在 documents 模块内部写入；外部只能按文档读取
当前来源，避免把请求携带的地址或正文误当成可信引用。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.documents.errors import DocumentNotFound
from server.documents.models import Document, SourceSnapshot
from server.documents.types import SourceInput, SourceSnapshotView
from server.infra.database import Database


def source_view(source: SourceSnapshot) -> SourceSnapshotView:
    """把内部 ORM 来源转成不可变公开值。"""
    return SourceSnapshotView(
        version_id=source.version_id,
        content=source.content,
        source_type=source.source_type,  # type: ignore[arg-type]
        source_url=source.source_url,
        title=source.title,
        captured_at=source.captured_at,
    )


class SourceManager:
    """幂等保存版本来源，并校验归属后读取当前来源。"""

    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def capture_in_transaction(
        session: Session, source_input: SourceInput
    ) -> SourceSnapshot:
        """在录入或编辑事务中保存来源，保证版本和来源不会只成功一半。"""
        source = session.get(SourceSnapshot, source_input.version_id)
        if source is None:
            source = SourceSnapshot(
                version_id=source_input.version_id,
                document_id=source_input.document_id,
                user_id=source_input.user_id,
                content=source_input.content,
                source_type=source_input.source_type,
                source_url=source_input.source_url,
                title=source_input.title,
                file_object_id=source_input.file_object_id,
            )
            session.add(source)
        return source

    def capture(self, source_input: SourceInput) -> SourceSnapshotView:
        """供模块内需要独立补写来源时使用，同一版本重复调用不会复制数据。"""
        with self._database.transaction() as session:
            source = self.capture_in_transaction(session, source_input)
            session.flush()
            return source_view(source)

    def get(self, document_id: str, user_id: str) -> SourceSnapshotView:
        """返回当前版本的来源；跨用户请求表现为不存在。"""
        with self._database.session() as session:
            row = session.execute(
                select(SourceSnapshot)
                .join(
                    Document, Document.current_version_id == SourceSnapshot.version_id
                )
                .where(Document.id == document_id, Document.user_id == user_id)
            ).scalar_one_or_none()
            if row is None:
                raise DocumentNotFound("文档不存在")
            return source_view(row)
