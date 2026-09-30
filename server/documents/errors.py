"""由 HTTP 边界统一转换的 documents 领域预期错误。"""


class DocumentsError(Exception):
    """文档领域预期错误的基类。"""


class InvalidDocumentInput(DocumentsError):
    """录入、编辑、检索或导出参数不符合业务规则时抛出。"""


class DocumentNotFound(DocumentsError):
    """文档不存在或不属于当前用户时抛出。"""


class VersionNotFound(DocumentsError):
    """指定历史版本不存在或不属于当前文档时抛出。"""


class TopicNotFound(DocumentsError):
    """专题不存在或不属于当前用户时抛出。"""


class TagNotFound(DocumentsError):
    """标签不存在或不属于当前用户时抛出。"""


class RelationNotFound(DocumentsError):
    """文档关联不存在或不属于当前用户时抛出。"""


class ImportJobNotFound(DocumentsError):
    """批量录入任务不存在或不属于当前用户时抛出。"""


class DuplicateName(DocumentsError):
    """同一用户创建重名专题或标签时抛出。"""


class UnsupportedExportFormat(DocumentsError):
    """请求的导出格式不受支持时抛出。"""
