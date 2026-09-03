"""Create model registry tables (registered_models & model_versions) — Milestone A9.4

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-02 16:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include registered_models and model_versions tables."""
    # 1. Create registered_models table
    op.create_table(
        "registered_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "task_type", sa.String(length=64), server_default="essay_grading", nullable=False
        ),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("active_production_version_id", sa.Integer(), nullable=True),
        sa.Column("active_staged_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["auth_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "school_id", name="uq_registered_models_name_school"),
    )
    op.create_index(op.f("ix_registered_models_name"), "registered_models", ["name"], unique=False)
    op.create_index(
        op.f("ix_registered_models_school_id"), "registered_models", ["school_id"], unique=False
    )

    # 2. Create model_versions table
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="REGISTERED", nullable=False),
        # Lineage links
        sa.Column("training_job_id", sa.Integer(), nullable=False),
        sa.Column("training_run_id", sa.String(length=128), nullable=False),
        sa.Column("experiment_id", sa.String(length=128), nullable=False),
        sa.Column("dataset_version_tag", sa.String(length=128), nullable=False),
        sa.Column("dataset_hash", sa.String(length=128), nullable=False),
        sa.Column("base_model_name", sa.String(length=255), nullable=False),
        sa.Column("base_model_revision", sa.String(length=128), nullable=True),
        sa.Column("tokenizer_name_or_path", sa.String(length=255), nullable=False),
        sa.Column("adapter_type", sa.String(length=32), server_default="LORA", nullable=False),
        sa.Column("adapter_config_hash", sa.String(length=128), nullable=False),
        # Storage & manifest hashes
        sa.Column("artifact_uri", sa.String(length=512), nullable=False),
        sa.Column("artifact_manifest_hash", sa.String(length=128), nullable=False),
        sa.Column("model_manifest_payload", sa.JSON(), nullable=False),
        sa.Column("validation_report_payload", sa.JSON(), nullable=True),
        sa.Column("promotion_history", sa.JSON(), nullable=False),
        # Tenant & Actor
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["model_id"], ["registered_models.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["auth_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "version", name="uq_model_versions_model_version"),
        sa.UniqueConstraint(
            "model_id", "version_number", name="uq_model_versions_model_version_number"
        ),
    )
    op.create_index(
        op.f("ix_model_versions_model_id"), "model_versions", ["model_id"], unique=False
    )
    op.create_index(op.f("ix_model_versions_status"), "model_versions", ["status"], unique=False)
    op.create_index(
        op.f("ix_model_versions_training_job_id"),
        "model_versions",
        ["training_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_versions_school_id"), "model_versions", ["school_id"], unique=False
    )

    # 3. Add deferred foreign keys for production and staged version pointers on registered_models
    op.create_foreign_key(
        "fk_registered_model_production_version",
        "registered_models",
        "model_versions",
        ["active_production_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_registered_model_staged_version",
        "registered_models",
        "model_versions",
        ["active_staged_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    """Downgrade schema to remove model registry tables."""
    op.drop_constraint(
        "fk_registered_model_staged_version", "registered_models", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_registered_model_production_version", "registered_models", type_="foreignkey"
    )
    op.drop_index(op.f("ix_model_versions_school_id"), table_name="model_versions")
    op.drop_index(op.f("ix_model_versions_training_job_id"), table_name="model_versions")
    op.drop_index(op.f("ix_model_versions_status"), table_name="model_versions")
    op.drop_index(op.f("ix_model_versions_model_id"), table_name="model_versions")
    op.drop_table("model_versions")
    op.drop_index(op.f("ix_registered_models_school_id"), table_name="registered_models")
    op.drop_index(op.f("ix_registered_models_name"), table_name="registered_models")
    op.drop_table("registered_models")
