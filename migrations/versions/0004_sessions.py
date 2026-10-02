"""创建会话、消息、引用及交互结果表。

Revision ID: 0004_sessions
Revises: 0003_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_sessions"
down_revision: str | None = "0003_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "sessions",
        *_identity_columns(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("active_run_id", sa.String(36), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_updated", "sessions", ["user_id", "updated_at"])
    op.create_table(
        "session_messages",
        *_identity_columns(),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "run_id", "role", name="uq_session_messages_run_role"
        ),
    )
    op.create_index(
        "ix_session_messages_order", "session_messages", ["session_id", "created_at"]
    )
    op.create_table(
        "session_citations",
        *_identity_columns(),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("session_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("document_version_id", sa.String(36), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("title_snapshot", sa.String(300), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "message_id", "position", name="uq_session_citations_position"
        ),
    )
    op.create_index("ix_session_citations_message", "session_citations", ["message_id"])
    op.create_table(
        "session_interaction_results",
        *_identity_columns(),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_json", sa.Text()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "run_id", "kind", name="uq_session_results_run_kind"
        ),
    )
    op.create_index(
        "ix_session_results_session",
        "session_interaction_results",
        ["session_id", "created_at"],
    )
    op.create_table(
        "session_practice_records",
        *_identity_columns(),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("mastery_snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "run_id", name="uq_session_practice_run"),
    )
    op.create_index(
        "ix_session_practice_session",
        "session_practice_records",
        ["session_id", "created_at"],
    )
    op.create_table(
        "session_feedback",
        *_identity_columns(),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_session_feedback_target"
        ),
    )
    op.create_index("ix_session_feedback_session", "session_feedback", ["session_id"])


def downgrade() -> None:
    for table in (
        "session_feedback",
        "session_practice_records",
        "session_interaction_results",
        "session_citations",
        "session_messages",
        "sessions",
    ):
        op.drop_table(table)
