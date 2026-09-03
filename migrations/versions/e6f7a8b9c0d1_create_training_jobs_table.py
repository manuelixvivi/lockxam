"""Create training_jobs table — Milestone A9.3

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-02 14:48:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include training_jobs table."""
    op.create_table(
        "training_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("current_run_id", sa.String(length=64), nullable=False),
        sa.Column("parent_run_id", sa.String(length=64), nullable=True),
        sa.Column(
            "experiment_id",
            sa.String(length=64),
            server_default="E2_FineTuned_Base",
            nullable=False,
        ),
        # Lineage link to frozen DatasetVersion
        sa.Column("dataset_version_id", sa.Integer(), nullable=False),
        sa.Column("dataset_version_tag", sa.String(length=64), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("base_model_name", sa.String(length=128), nullable=False),
        # Lifecycle state machine & execution mode
        sa.Column("status", sa.String(length=32), server_default="QUEUED", nullable=False),
        sa.Column(
            "execution_mode", sa.String(length=32), server_default="CPU_TEST", nullable=False
        ),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        # Immutable job configuration & artifact URI
        sa.Column("job_config_payload", sa.JSON(), nullable=False),
        sa.Column("artifact_uri", sa.String(length=255), nullable=False),
        # Progress & Loss Metrics
        sa.Column("total_epochs", sa.Integer(), server_default="3", nullable=False),
        sa.Column("current_epoch", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_steps", sa.Integer(), server_default="0", nullable=False),
        sa.Column("train_loss", sa.Float(), nullable=True),
        sa.Column("eval_loss", sa.Float(), nullable=True),
        sa.Column("eval_perplexity", sa.Float(), nullable=True),
        # Artifact paths & error
        sa.Column("best_checkpoint_path", sa.String(length=255), nullable=True),
        sa.Column("final_adapter_path", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Tenant isolation & actor lineage
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("school_id", sa.Integer(), nullable=True),
        # Heartbeat & Timestamps
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        # Foreign key constraints
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["auth_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_training_jobs_job_id"), "training_jobs", ["job_id"], unique=True)
    op.create_index(
        op.f("ix_training_jobs_current_run_id"), "training_jobs", ["current_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_training_jobs_experiment_id"), "training_jobs", ["experiment_id"], unique=False
    )
    op.create_index(op.f("ix_training_jobs_status"), "training_jobs", ["status"], unique=False)
    op.create_index(
        op.f("ix_training_jobs_school_id"), "training_jobs", ["school_id"], unique=False
    )
    op.create_index(
        op.f("ix_training_jobs_dataset_version_id"),
        "training_jobs",
        ["dataset_version_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema to remove training_jobs table."""
    op.drop_index(op.f("ix_training_jobs_dataset_version_id"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_school_id"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_status"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_experiment_id"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_current_run_id"), table_name="training_jobs")
    op.drop_index(op.f("ix_training_jobs_job_id"), table_name="training_jobs")
    op.drop_table("training_jobs")
