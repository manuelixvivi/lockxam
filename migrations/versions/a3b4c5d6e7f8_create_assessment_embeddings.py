"""Create assessment_embeddings table — Milestone A3

Revision ID: a3b4c5d6e7f8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01 15:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include assessment_embeddings table."""
    op.create_table(
        "assessment_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        # Lineage & Version Coupling
        sa.Column("assessment_history_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        # Tenant & Academic Metadata
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("class_level", sa.String(length=50), nullable=False),
        # Embedding Model Metadata
        sa.Column(
            "embedding_model",
            sa.String(length=100),
            server_default="intfloat/multilingual-e5-large",
            nullable=False,
        ),
        sa.Column("dimension", sa.Integer(), server_default="1024", nullable=False),
        # Dense Vector Payload
        sa.Column("vector_data", sa.JSON(), nullable=False),
        # Timestamp Mixin
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # Foreign Keys with ON DELETE RESTRICT
        sa.ForeignKeyConstraint(
            ["assessment_history_id"], ["assessment_histories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint(
            "assessment_history_id", "version", name="uq_assessment_embedding_hist_ver"
        ),
    )
    op.create_index(
        "ix_ae_tenant_subject",
        "assessment_embeddings",
        ["school_id", "subject_id", "class_level"],
    )
    op.create_index(
        "ix_ae_content_hash",
        "assessment_embeddings",
        ["content_hash"],
    )
    op.create_index(
        "ix_ae_active_lookup",
        "assessment_embeddings",
        ["school_id", "is_current"],
    )


def downgrade() -> None:
    """Downgrade schema by dropping assessment_embeddings."""
    op.drop_index("ix_ae_active_lookup", table_name="assessment_embeddings")
    op.drop_index("ix_ae_content_hash", table_name="assessment_embeddings")
    op.drop_index("ix_ae_tenant_subject", table_name="assessment_embeddings")
    op.drop_table("assessment_embeddings")
