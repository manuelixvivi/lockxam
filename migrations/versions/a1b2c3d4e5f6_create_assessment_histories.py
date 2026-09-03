"""Create assessment_histories table — Milestone A1

Revision ID: a1b2c3d4e5f6
Revises: 0df469135420
Create Date: 2026-09-01 14:55:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "0df469135420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include assessment_histories table."""
    op.create_table(
        "assessment_histories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        # Tenant & Academic Isolation
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_name", sa.String(length=255), nullable=False),
        sa.Column("class_level", sa.String(length=50), nullable=False),
        # Lineage Tracking & Evaluator Actors
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("exam_attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("exam_teacher_id", sa.Integer(), nullable=False),
        sa.Column("finalized_by_teacher_id", sa.Integer(), nullable=False),
        # Versioning & Immutability Lifecycle
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        # Frozen Assessment Context (from Snapshot)
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=50), server_default="ES", nullable=False),
        sa.Column("answer_key", sa.Text(), nullable=False),
        sa.Column("rubrics_json", sa.JSON(), nullable=False),
        sa.Column("max_score", sa.Numeric(precision=5, scale=2), nullable=False),
        # Student Submission
        sa.Column("student_answer", sa.Text(), nullable=False),
        # AI Assessment Provenance & Draft Data
        sa.Column("ai_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("ai_model_name", sa.String(length=100), nullable=True),
        sa.Column("ai_prompt_version", sa.String(length=50), nullable=True),
        sa.Column("ai_rubric_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("ai_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        # Teacher Ground Truth & Correction Validation
        sa.Column("teacher_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column("final_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "score_delta", sa.Numeric(precision=5, scale=2), server_default="0.0", nullable=False
        ),
        # RAG & Transformer Embedding State
        sa.Column("is_rag_eligible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "embedding_status", sa.String(length=50), server_default="PENDING", nullable=False
        ),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vector_id", sa.String(length=100), nullable=True),
        # Timestamp Mixin
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # Foreign Keys with ON DELETE RESTRICT
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["exam_answer_evaluations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["exam_attempt_id"], ["exam_attempts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["exam_teacher_id"], ["auth_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["finalized_by_teacher_id"], ["auth_accounts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("evaluation_id", "version", name="uq_assessment_history_eval_version"),
    )
    op.create_index(
        "ix_ah_tenant_subject",
        "assessment_histories",
        ["school_id", "subject_id", "class_level"],
    )
    op.create_index(
        "ix_ah_rag_active_queue",
        "assessment_histories",
        ["school_id", "embedding_status", "is_rag_eligible", "is_current"],
    )
    op.create_index(
        "ix_ah_lineage_lookup",
        "assessment_histories",
        ["school_id", "question_id", "is_current"],
    )
    op.create_index(
        "ix_ah_eval_version_chain",
        "assessment_histories",
        ["evaluation_id", "version"],
    )


def downgrade() -> None:
    """Downgrade schema by dropping assessment_histories."""
    op.drop_index("ix_ah_eval_version_chain", table_name="assessment_histories")
    op.drop_index("ix_ah_lineage_lookup", table_name="assessment_histories")
    op.drop_index("ix_ah_rag_active_queue", table_name="assessment_histories")
    op.drop_index("ix_ah_tenant_subject", table_name="assessment_histories")
    op.drop_table("assessment_histories")
