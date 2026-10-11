"""Record the embedding model identity for safe incremental indexing."""

import sqlalchemy as sa
from alembic import op

revision = "0006_embedding_cache_key"
down_revision = "0005_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_versions", sa.Column("embedding_key", sa.String(500), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("source_checked_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "documents", sa.Column("source_changed_at", sa.DateTime(timezone=True))
    )
    op.add_column("documents", sa.Column("source_change_diff", sa.Text()))


def downgrade() -> None:
    op.drop_column("documents", "source_change_diff")
    op.drop_column("documents", "source_changed_at")
    op.drop_column("documents", "source_checked_at")
    op.drop_column("document_versions", "embedding_key")
