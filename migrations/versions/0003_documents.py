"""创建文档、版本、知识组织、索引和批量录入任务表。

Revision ID: 0003_documents
Revises: 0002_users_auth
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_documents"
down_revision: str | None = "0002_users_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class VectorType(sa.types.UserDefinedType[str]):
    """迁移期使用的 pgvector 列类型。"""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kwargs: object) -> str:
        return f"vector({self.dimensions})"


def upgrade() -> None:
    # Docker 开发数据库使用 pgvector 镜像；扩展启用后才能创建向量列和近邻索引。
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_topics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_document_topics_user_name"),
    )
    op.create_index("ix_document_topics_user", "document_topics", ["user_id"])

    op.create_table(
        "document_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_document_tags_user_name"),
    )
    op.create_index("ix_document_tags_user", "document_tags", ["user_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("topic_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("current_version_id", sa.String(length=36), nullable=False),
        sa.Column("index_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["document_topics.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_user_status", "documents", ["user_id", "status"])
    op.create_index("ix_documents_user_topic", "documents", ["user_id", "topic_id"])
    op.create_index("ix_documents_current_version", "documents", ["current_version_id"])

    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title_snapshot", sa.String(length=300), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("index_status", sa.String(length=20), nullable=False),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("index_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "version", name="uq_document_versions_number"
        ),
    )
    op.create_index(
        "ix_document_versions_document",
        "document_versions",
        ["document_id", "version"],
    )
    op.create_index("ix_document_versions_user", "document_versions", ["user_id"])

    op.create_table(
        "document_source_snapshots",
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("file_object_id", sa.String(length=36), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_document_sources_document",
        "document_source_snapshots",
        ["document_id"],
    )

    op.create_table(
        "document_tag_links",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["document_tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
    )
    op.create_index("ix_document_tag_links_tag", "document_tag_links", ["tag_id"])

    op.create_table(
        "document_relations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("target_document_id", sa.String(length=36), nullable=False),
        sa.Column("relation_type", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relation_type",
            name="uq_document_relations_edge",
        ),
    )
    op.create_index(
        "ix_document_relations_user_source",
        "document_relations",
        ["user_id", "source_document_id"],
    )
    op.create_index(
        "ix_document_relations_user_target",
        "document_relations",
        ["user_id", "target_document_id"],
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("embedding", VectorType(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "position", name="uq_document_chunks_position"
        ),
    )
    op.create_index(
        "ix_document_chunks_lookup",
        "document_chunks",
        ["user_id", "document_id", "version_id"],
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_full_text ON document_chunks "
        "USING GIN (to_tsvector('simple', search_text))"
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "document_knowledge_points",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id", "position", name="uq_knowledge_points_position"
        ),
    )
    op.create_index(
        "ix_knowledge_points_source",
        "document_knowledge_points",
        ["user_id", "document_id", "version_id"],
    )

    op.create_table(
        "document_knowledge_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "normalized_name", name="uq_knowledge_entities_user_name"
        ),
    )
    op.create_index(
        "ix_knowledge_entities_user", "document_knowledge_entities", ["user_id"]
    )

    op.create_table(
        "document_knowledge_point_entities",
        sa.Column("point_id", sa.String(length=36), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["point_id"], ["document_knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["document_knowledge_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("point_id", "entity_id"),
    )
    op.create_index(
        "ix_knowledge_point_entities_source",
        "document_knowledge_point_entities",
        ["user_id", "document_id", "version_id"],
    )

    op.create_table(
        "document_knowledge_relations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("point_id", sa.String(length=36), nullable=False),
        sa.Column("source_entity_id", sa.String(length=36), nullable=False),
        sa.Column("target_entity_id", sa.String(length=36), nullable=False),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["point_id"], ["document_knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["document_knowledge_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["document_knowledge_entities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "point_id",
            "source_entity_id",
            "target_entity_id",
            name="uq_knowledge_relations_evidence",
        ),
    )
    op.create_index(
        "ix_knowledge_relations_source",
        "document_knowledge_relations",
        ["user_id", "document_id", "version_id"],
    )

    op.create_table(
        "document_index_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "version_id", name="uq_document_index_tasks_version"
        ),
    )
    op.create_index(
        "ix_document_index_tasks_status",
        "document_index_tasks",
        ["status", "updated_at"],
    )

    op.create_table(
        "document_import_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_import_jobs_user", "document_import_jobs", ["user_id"])

    op.create_table(
        "document_import_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("input_index", sa.Integer(), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["document_import_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "input_index", name="uq_import_items_job_index"),
    )
    op.create_index("ix_document_import_items_job", "document_import_items", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_document_import_items_job", table_name="document_import_items")
    op.drop_table("document_import_items")
    op.drop_index("ix_document_import_jobs_user", table_name="document_import_jobs")
    op.drop_table("document_import_jobs")
    op.drop_index("ix_document_index_tasks_status", table_name="document_index_tasks")
    op.drop_table("document_index_tasks")
    # 开发阶段曾在同一未发布迁移中补充知识图谱表；IF EXISTS 也允许本地旧版
    # 0003 安全回退，正式部署的完整表结构仍按依赖顺序删除。
    op.execute("DROP TABLE IF EXISTS document_knowledge_relations")
    op.execute("DROP TABLE IF EXISTS document_knowledge_point_entities")
    op.execute("DROP TABLE IF EXISTS document_knowledge_entities")
    op.execute("DROP TABLE IF EXISTS document_knowledge_points")
    op.drop_index("ix_document_chunks_lookup", table_name="document_chunks")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_full_text")
    op.drop_table("document_chunks")
    op.drop_index("ix_document_relations_user_target", table_name="document_relations")
    op.drop_index("ix_document_relations_user_source", table_name="document_relations")
    op.drop_table("document_relations")
    op.drop_index("ix_document_tag_links_tag", table_name="document_tag_links")
    op.drop_table("document_tag_links")
    op.drop_index(
        "ix_document_sources_document", table_name="document_source_snapshots"
    )
    op.drop_table("document_source_snapshots")
    op.drop_index("ix_document_versions_user", table_name="document_versions")
    op.drop_index("ix_document_versions_document", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_current_version", table_name="documents")
    op.drop_index("ix_documents_user_topic", table_name="documents")
    op.drop_index("ix_documents_user_status", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_document_tags_user", table_name="document_tags")
    op.drop_table("document_tags")
    op.drop_index("ix_document_topics_user", table_name="document_topics")
    op.drop_table("document_topics")
