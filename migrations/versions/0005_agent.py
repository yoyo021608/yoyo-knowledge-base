"""创建 Agent Run、快照和事件表。

Revision ID: 0005_agent
Revises: 0004_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_agent"
down_revision: str | None = "0004_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("request_id", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("question_digest", sa.String(64), nullable=False),
        sa.Column("last_event_seq", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "session_id", "request_id", name="uq_agent_run_request"
        ),
    )
    op.create_index("ix_agent_runs_recoverable", "agent_runs", ["status", "updated_at"])
    op.create_index("ix_agent_runs_session", "agent_runs", ["session_id", "created_at"])
    op.create_table(
        "agent_run_snapshots",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("input_message_id", sa.String(36)),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("step", sa.String(30), nullable=False),
        sa.Column("queries_json", sa.Text(), nullable=False),
        sa.Column("selected_sources_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text()),
        sa.Column("mode_result_json", sa.Text()),
        sa.Column("chat_model", sa.String(120), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "event_seq", name="uq_agent_run_event_seq"),
    )
    op.create_index(
        "ix_agent_run_events_replay", "agent_run_events", ["run_id", "event_seq"]
    )


def downgrade() -> None:
    op.drop_table("agent_run_events")
    op.drop_table("agent_run_snapshots")
    op.drop_table("agent_runs")
