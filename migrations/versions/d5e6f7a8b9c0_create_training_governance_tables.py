"""Create training_candidates and dataset_versions tables — Milestone A8

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-02 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include training_candidates and dataset_versions tables."""
    # 1. training_candidates table
    op.create_table(
        "training_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_history_id", sa.Integer(), nullable=False),
        sa.Column("history_version", sa.Integer(), server_default="1", nullable=False),
        # Quality Gate Classification
        sa.Column(
            "quality_status", sa.String(length=30), server_default="NEEDS_REVIEW", nullable=False
        ),
        sa.Column("quality_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        # Privacy & PII Sanitization
        sa.Column("pii_status", sa.String(length=30), server_default="CLEAN", nullable=False),
        sa.Column("pii_entities_detected", sa.JSON(), nullable=False),
        sa.Column("sanitized_student_answer", sa.Text(), nullable=False),
        sa.Column("sanitized_teacher_feedback", sa.Text(), nullable=True),
        # Partitioning & Training Payload
        sa.Column("question_group_key", sa.String(length=64), nullable=False),
        sa.Column("formatted_sft_payload", sa.JSON(), nullable=False),
        # Academic Metadata
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_name", sa.String(length=100), nullable=False),
        sa.Column("class_level", sa.String(length=50), nullable=False),
        # Timestamp Mixin
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["assessment_history_id"], ["assessment_histories.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_history_id", "history_version", name="uq_training_candidate_history_ver"
        ),
    )
    op.create_index(
        "ix_tc_quality_status",
        "training_candidates",
        ["quality_status"],
    )
    op.create_index(
        "ix_tc_pii_status",
        "training_candidates",
        ["pii_status"],
    )
    op.create_index(
        "ix_tc_question_group_key",
        "training_candidates",
        ["question_group_key"],
    )
    op.create_index(
        "ix_tc_tenant_subject",
        "training_candidates",
        ["school_id", "subject_id"],
    )
    op.create_index(
        "ix_tc_academic_year",
        "training_candidates",
        ["academic_year_id"],
    )

    # 2. dataset_versions table
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version_tag", sa.String(length=50), nullable=False),
        sa.Column(
            "task_type", sa.String(length=50), server_default="ESSAY_GRADING", nullable=False
        ),
        sa.Column(
            "split_strategy",
            sa.String(length=50),
            server_default="QUESTION_GROUP_SPLIT",
            nullable=False,
        ),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("total_samples", sa.Integer(), server_default="0", nullable=False),
        sa.Column("train_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("val_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("test_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quality_threshold_applied", sa.Float(), server_default="0.70", nullable=False),
        sa.Column("split_manifest", sa.JSON(), nullable=False),
        sa.Column("candidate_ids", sa.JSON(), nullable=False),
        sa.Column("frozen_split_payloads", sa.JSON(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_tag"),
    )
    op.create_index(
        "ix_dv_version_tag",
        "dataset_versions",
        ["version_tag"],
    )
    op.create_index(
        "ix_dv_dataset_hash",
        "dataset_versions",
        ["dataset_hash"],
    )
    op.create_index(
        "ix_dv_tenant_year",
        "dataset_versions",
        ["school_id", "academic_year_id"],
    )


def downgrade() -> None:
    """Downgrade schema removing training governance tables."""
    op.drop_table("dataset_versions")
    op.drop_table("training_candidates")
