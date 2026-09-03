"""Create grading_runs table for post-exam batch grading lineage

Revision ID: c4d5e6f7a8b9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-02 10:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include grading_runs table."""
    op.create_table(
        "grading_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("exam_schedule_id", sa.Integer(), nullable=False),
        sa.Column("exam_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="QUEUED", nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_submissions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_batches", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_batches", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_batches", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "model_used",
            sa.String(length=100),
            server_default="openai/gpt-oss-120b",
            nullable=False,
        ),
        sa.Column(
            "prompt_version",
            sa.String(length=50),
            server_default="batch_grading_v2.0",
            nullable=False,
        ),
        sa.Column("rag_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["exam_schedule_id"], ["exam_schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_runs_exam_schedule_id",
        "grading_runs",
        ["exam_schedule_id"],
    )
    op.create_index(
        "ix_grading_runs_status",
        "grading_runs",
        ["status"],
    )


def downgrade() -> None:
    """Downgrade schema by dropping grading_runs table."""
    op.drop_index("ix_grading_runs_status", table_name="grading_runs")
    op.drop_index("ix_grading_runs_exam_schedule_id", table_name="grading_runs")
    op.drop_table("grading_runs")
