"""Create ai_system_settings and ai_config_histories tables

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-14 09:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include ai_system_settings and ai_config_histories tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "ai_system_settings" not in existing_tables:
        op.create_table(
            "ai_system_settings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=False),
            sa.Column("encrypted_secret", sa.Text(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["updated_by_id"], ["auth_accounts.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_system_settings_key", "ai_system_settings", ["key"], unique=True)

    if "ai_config_histories" not in existing_tables:
        op.create_table(
            "ai_config_histories",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("changed_by_id", sa.Integer(), nullable=True),
            sa.Column("changed_by_name", sa.String(length=255), nullable=True),
            sa.Column("change_summary", sa.Text(), nullable=False),
            sa.Column("provider", sa.String(length=100), server_default="Groq", nullable=False),
            sa.Column("model_name", sa.String(length=255), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["changed_by_id"], ["auth_accounts.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Downgrade schema to remove ai_system_settings and ai_config_histories tables."""
    op.drop_table("ai_config_histories")
    op.drop_table("ai_system_settings")
