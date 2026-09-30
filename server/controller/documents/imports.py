"""单条、文件和批量资料录入的 HTTP 边界。"""

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from server.controller.documents.schemas import (
    BatchImportRequest,
    BatchJobResponse,
    DocumentImportRequest,
    FileImportRequest,
    ImportResponse,
)
from server.controller.documents.shared import document_error, get_documents, schema_of
from server.controller.users import require_identity
from server.documents.errors import DocumentsError, InvalidDocumentInput
from server.documents.module import DocumentsModule
from server.documents.types import BatchImportInput, SingleImportInput, StoredFileInput
from server.users.types import IdentityContext

router = APIRouter(prefix="/api", tags=["document-imports"])


def _single_input(body: DocumentImportRequest, user_id: str) -> SingleImportInput:
    return SingleImportInput(
        user_id=user_id,
        title=body.title or "",
        content=body.content or "",
        source_type=body.source_type,
        source_url=body.source_url,
        source_title=body.source_title,
        topic_id=body.topic_id,
        tags=tuple(body.tags),
    )


@router.post(
    "/documents/import",
    response_model=ImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_document(
    body: DocumentImportRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> ImportResponse:
    """录入文本、Markdown，或仅凭公开网址抓取网页资料。"""
    try:
        if body.source_type == "web" and not (body.content or "").strip():
            result = documents.single_importer.import_web(
                user_id=identity.user_id,
                source_url=body.source_url or "",
                title=body.title,
                topic_id=body.topic_id,
                tags=tuple(body.tags),
            )
        else:
            result = documents.single_importer.import_one(
                _single_input(body, identity.user_id)
            )
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(ImportResponse, result)


@router.post(
    "/documents/import-file",
    response_model=ImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_file(
    body: FileImportRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> ImportResponse:
    """解码常见资料文件并交给 documents 保存原文件和创建版本。"""
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容不是有效 Base64"
        ) from exc
    try:
        result = documents.single_importer.import_file(
            StoredFileInput(
                user_id=identity.user_id,
                name=body.name,
                content=content,
                content_type=body.content_type,
                title=body.title,
                topic_id=body.topic_id,
                tags=tuple(body.tags),
            )
        )
    except (DocumentsError, ValueError) as exc:
        raise document_error(InvalidDocumentInput(str(exc))) from exc
    return schema_of(ImportResponse, result)


@router.post(
    "/document-import-jobs",
    response_model=BatchJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_import_job(
    body: BatchImportRequest,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> BatchJobResponse:
    """创建并逐条运行批量录入任务。"""
    try:
        result = documents.batch_importer.create_job(
            BatchImportInput(
                user_id=identity.user_id,
                items=tuple(
                    _single_input(item, identity.user_id) for item in body.items
                ),
            )
        )
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(BatchJobResponse, result)


@router.get("/document-import-jobs/{job_id}", response_model=BatchJobResponse)
def get_import_job(
    job_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> BatchJobResponse:
    """查看批量任务及每条输入的结果。"""
    try:
        result = documents.batch_importer.get_job(job_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(BatchJobResponse, result)


@router.post("/document-import-jobs/{job_id}/retry", response_model=BatchJobResponse)
def retry_import_job(
    job_id: str,
    documents: Annotated[DocumentsModule, Depends(get_documents)],
    identity: Annotated[IdentityContext, Depends(require_identity)],
) -> BatchJobResponse:
    """只重试批次中失败的输入。"""
    try:
        result = documents.batch_importer.retry_failed(job_id, identity.user_id)
    except DocumentsError as exc:
        raise document_error(exc) from exc
    return schema_of(BatchJobResponse, result)
