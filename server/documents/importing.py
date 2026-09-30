"""单条与批量资料录入。

单条录入原子创建 Document、首个 DocumentVersion 和来源快照；批量录入只负责
任务进度与逐条隔离，任何一条失败都不会回滚其他条目。
"""

import json
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select

from server.documents.documents import (
    clean_content,
    clean_title,
    require_topic,
    set_document_tags,
)
from server.documents.errors import ImportJobNotFound, InvalidDocumentInput
from server.documents.indexing import DocumentIndexer
from server.documents.models import Document, DocumentVersion, ImportItem, ImportJob
from server.documents.sources import SourceManager
from server.documents.types import (
    BatchImportInput,
    BatchJobResult,
    ImportItemView,
    ImportJobView,
    ImportResult,
    RefreshRequest,
    SingleImportInput,
    SourceInput,
    SourceType,
    StoredFileInput,
)
from server.infra.content import DocumentContentError, DocumentContentLoader
from server.infra.database import Database
from server.infra.files import LocalFileStorage

_SOURCE_TYPES = {"note", "markdown", "web", "file"}


def _validate_source(source_type: str, source_url: str | None) -> SourceType:
    """验证来源类型；网页来源必须提供可追溯的 HTTP(S) 地址。"""
    if source_type not in _SOURCE_TYPES:
        raise InvalidDocumentInput("来源类型必须是 note、markdown、web 或 file")
    if source_type == "web":
        parsed = urlparse(source_url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidDocumentInput("网页资料必须提供有效的 HTTP(S) 来源地址")
    return cast(SourceType, source_type)


def _job_view(job: ImportJob) -> ImportJobView:
    return ImportJobView(
        id=job.id,
        user_id=job.user_id,
        mode=job.mode,
        status=job.status,
        total_count=job.total_count,
        success_count=job.success_count,
        failure_count=job.failure_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _item_view(item: ImportItem) -> ImportItemView:
    return ImportItemView(
        id=item.id,
        job_id=item.job_id,
        input_index=item.input_index,
        status=item.status,
        document_id=item.document_id,
        error_message=item.error_message,
    )


class SingleImporter:
    """校验并保存一条资料，然后为首个版本建立索引。"""

    def __init__(
        self,
        database: Database,
        indexer: DocumentIndexer,
        file_storage: LocalFileStorage | None = None,
        content_loader: DocumentContentLoader | None = None,
    ) -> None:
        self._database = database
        self._indexer = indexer
        self._file_storage = file_storage
        self._content_loader = content_loader

    def import_web(
        self,
        *,
        user_id: str,
        source_url: str,
        title: str | None = None,
        topic_id: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> ImportResult:
        """抓取公开网页正文，再进入与普通资料相同的版本和索引流程。"""
        _validate_source("web", source_url)
        if self._content_loader is None:
            raise InvalidDocumentInput("网页内容读取能力尚未装配")
        try:
            extracted = self._content_loader.fetch_web(source_url)
        except DocumentContentError as exc:
            raise InvalidDocumentInput(str(exc)) from exc
        return self.import_one(
            SingleImportInput(
                user_id=user_id,
                title=title or extracted.title,
                content=extracted.content,
                source_type="web",
                source_url=source_url,
                source_title=extracted.title,
                topic_id=topic_id,
                tags=tags,
            )
        )

    def import_one(self, import_input: SingleImportInput) -> ImportResult:
        """创建文档、版本、来源和组织关系，随后触发幂等索引刷新。"""
        title = clean_title(import_input.title)
        content = clean_content(import_input.content)
        source_type = _validate_source(
            import_input.source_type, import_input.source_url
        )
        document_id = str(uuid4())
        version_id = str(uuid4())
        now = datetime.now(UTC)
        with self._database.transaction() as session:
            require_topic(session, import_input.topic_id, import_input.user_id)
            document = Document(
                id=document_id,
                user_id=import_input.user_id,
                topic_id=import_input.topic_id,
                title=title,
                status="active",
                is_favorite=False,
                current_version=1,
                current_version_id=version_id,
                index_status="queued",
                created_at=now,
                updated_at=now,
            )
            session.add(document)
            session.flush()
            session.add(
                DocumentVersion(
                    id=version_id,
                    document_id=document_id,
                    user_id=import_input.user_id,
                    version=1,
                    title_snapshot=title,
                    content_snapshot=content,
                    index_status="queued",
                    index_updated_at=now,
                )
            )
            # ORM 未声明跨聚合关系，先落版本以满足来源和任务的数据库外键顺序。
            session.flush()
            DocumentIndexer.queue_in_transaction(
                session, document_id, version_id, import_input.user_id
            )
            SourceManager.capture_in_transaction(
                session,
                SourceInput(
                    user_id=import_input.user_id,
                    document_id=document_id,
                    version_id=version_id,
                    content=content,
                    source_type=source_type,
                    source_url=import_input.source_url,
                    title=import_input.source_title or title,
                    file_object_id=import_input.file_object_id,
                ),
            )
            set_document_tags(
                session, document_id, import_input.user_id, import_input.tags
            )

        # 版本和 queued 状态先提交。索引失败只把该版本标记 failed，不丢失资料。
        try:
            self._indexer.refresh(
                RefreshRequest(document_id=document_id, version_id=version_id)
            )
        except Exception:
            return ImportResult(
                document_id=document_id,
                version_id=version_id,
                index_status="failed",
            )
        return ImportResult(
            document_id=document_id,
            version_id=version_id,
            index_status="ready",
        )

    def import_file(self, file_input: StoredFileInput) -> ImportResult:
        """保存上传文件并使用 infra 提取正文，再按普通版本流程录入。"""
        if self._file_storage is None:
            raise InvalidDocumentInput("文件存储能力尚未装配")
        if self._content_loader is None:
            try:
                extracted_title = file_input.title or file_input.name
                extracted_content = file_input.content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise InvalidDocumentInput("文件内容读取能力尚未装配") from exc
        else:
            try:
                extracted = self._content_loader.extract_file(
                    file_input.name, file_input.content, file_input.content_type
                )
            except DocumentContentError as exc:
                raise InvalidDocumentInput(str(exc)) from exc
            extracted_title = extracted.title
            extracted_content = extracted.content
        stored = self._file_storage.put(
            file_input.name, file_input.content, file_input.content_type
        )
        try:
            return self.import_one(
                SingleImportInput(
                    user_id=file_input.user_id,
                    title=file_input.title or extracted_title,
                    content=extracted_content,
                    source_type="file",
                    source_title=stored.name,
                    topic_id=file_input.topic_id,
                    tags=file_input.tags,
                    file_object_id=stored.id,
                )
            )
        except Exception:
            self._file_storage.delete(stored.id)
            raise


class BatchImporter:
    """保存批次和逐条结果，支持只重试失败条目。"""

    def __init__(self, database: Database, single_importer: SingleImporter) -> None:
        self._database = database
        self._single_importer = single_importer

    def create_job(self, batch_input: BatchImportInput) -> BatchJobResult:
        """先持久化整批输入，再逐条执行，保证进度可恢复和可查看。"""
        if not batch_input.items:
            raise InvalidDocumentInput("批量录入至少需要一条资料")
        if len(batch_input.items) > 100:
            raise InvalidDocumentInput("单次批量录入不能超过 100 条")
        job_id = str(uuid4())
        with self._database.transaction() as session:
            job = ImportJob(
                id=job_id,
                user_id=batch_input.user_id,
                mode="batch",
                status="queued",
                total_count=len(batch_input.items),
            )
            session.add(job)
            for index, item in enumerate(batch_input.items):
                session.add(
                    ImportItem(
                        id=str(uuid4()),
                        job_id=job_id,
                        user_id=batch_input.user_id,
                        input_index=index,
                        input_json=json.dumps(
                            {
                                "title": item.title,
                                "content": item.content,
                                "source_type": item.source_type,
                                "source_url": item.source_url,
                                "source_title": item.source_title,
                                "topic_id": item.topic_id,
                                "tags": list(item.tags),
                                "file_object_id": item.file_object_id,
                            },
                            ensure_ascii=False,
                        ),
                        status="queued",
                    )
                )
        self._run_pending(job_id, batch_input.user_id, include_failed=False)
        return self.get_job(job_id, batch_input.user_id)

    def get_job(self, job_id: str, user_id: str) -> BatchJobResult:
        """返回批次聚合进度和按输入顺序排列的逐条结果。"""
        with self._database.session() as session:
            job = session.scalar(
                select(ImportJob).where(
                    ImportJob.id == job_id, ImportJob.user_id == user_id
                )
            )
            if job is None:
                raise ImportJobNotFound("批量录入任务不存在")
            items = session.scalars(
                select(ImportItem)
                .where(ImportItem.job_id == job_id, ImportItem.user_id == user_id)
                .order_by(ImportItem.input_index)
            ).all()
            return BatchJobResult(
                job=_job_view(job), items=tuple(_item_view(item) for item in items)
            )

    def retry_failed(self, job_id: str, user_id: str) -> BatchJobResult:
        """只重新处理 failed 条目，已成功条目的文档不会重复创建。"""
        self.get_job(job_id, user_id)
        self._run_pending(job_id, user_id, include_failed=True)
        return self.get_job(job_id, user_id)

    def _run_pending(self, job_id: str, user_id: str, *, include_failed: bool) -> None:
        """逐条运行可处理条目，每条使用自己的事务和错误结果。"""
        allowed_statuses = ("queued", "failed") if include_failed else ("queued",)
        with self._database.transaction() as session:
            job = session.scalar(
                select(ImportJob).where(
                    ImportJob.id == job_id, ImportJob.user_id == user_id
                )
            )
            if job is None:
                raise ImportJobNotFound("批量录入任务不存在")
            job.status = "running"
            job.updated_at = datetime.now(UTC)
            item_ids = tuple(
                session.scalars(
                    select(ImportItem.id)
                    .where(
                        ImportItem.job_id == job_id,
                        ImportItem.status.in_(allowed_statuses),
                    )
                    .order_by(ImportItem.input_index)
                ).all()
            )

        for item_id in item_ids:
            self._run_item(item_id, user_id)
        self._recount(job_id, user_id)

    def _run_item(self, item_id: str, user_id: str) -> None:
        with self._database.session() as session:
            item = session.scalar(
                select(ImportItem).where(
                    ImportItem.id == item_id, ImportItem.user_id == user_id
                )
            )
            if item is None or item.status == "success":
                return
            raw = cast(dict[str, Any], json.loads(item.input_json))
        try:
            result = self._single_importer.import_one(
                SingleImportInput(
                    user_id=user_id,
                    title=str(raw["title"]),
                    content=str(raw["content"]),
                    source_type=cast(SourceType, raw["source_type"]),
                    source_url=cast(str | None, raw.get("source_url")),
                    source_title=cast(str | None, raw.get("source_title")),
                    topic_id=cast(str | None, raw.get("topic_id")),
                    tags=tuple(str(value) for value in raw.get("tags", [])),
                    file_object_id=cast(str | None, raw.get("file_object_id")),
                )
            )
        except Exception as exc:
            with self._database.transaction() as session:
                failed = session.get(ImportItem, item_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.document_id = None
                    failed.error_message = str(exc)[:1000]
                    failed.updated_at = datetime.now(UTC)
            return
        with self._database.transaction() as session:
            succeeded = session.get(ImportItem, item_id)
            if succeeded is not None:
                succeeded.status = "success"
                succeeded.document_id = result.document_id
                succeeded.error_message = None
                # 成功后正文只保留在版本和来源快照中，批次表不再复制敏感正文。
                succeeded.input_json = json.dumps(
                    {
                        "title": raw["title"],
                        "source_type": raw["source_type"],
                        "content_removed_after_success": True,
                    },
                    ensure_ascii=False,
                )
                succeeded.updated_at = datetime.now(UTC)

    def _recount(self, job_id: str, user_id: str) -> None:
        """从条目事实重新计算聚合状态，避免累加计数在重试后漂移。"""
        with self._database.transaction() as session:
            job = session.scalar(
                select(ImportJob).where(
                    ImportJob.id == job_id, ImportJob.user_id == user_id
                )
            )
            if job is None:
                raise ImportJobNotFound("批量录入任务不存在")
            statuses = session.scalars(
                select(ImportItem.status).where(ImportItem.job_id == job_id)
            ).all()
            success_count = sum(status == "success" for status in statuses)
            failure_count = sum(status == "failed" for status in statuses)
            job.success_count = success_count
            job.failure_count = failure_count
            if success_count == job.total_count:
                job.status = "completed"
            elif failure_count == job.total_count:
                job.status = "failed"
            else:
                job.status = "partial"
            job.updated_at = datetime.now(UTC)
