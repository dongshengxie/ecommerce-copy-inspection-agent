"""add agent trace metadata

Revision ID: acc05d636557
Revises: cb6cebe6f8e7
Create Date: 2026-08-18 03:29:05.483064

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "acc05d636557"
down_revision: str | Sequence[str] | None = "cb6cebe6f8e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add safe, structured metadata to persisted agent traces."""
    op.add_column("agent_traces", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.execute("UPDATE agent_traces SET metadata_json = JSON_OBJECT() WHERE metadata_json IS NULL")
    op.alter_column("agent_traces", "metadata_json", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    """Remove only the Phase 4 Trace metadata column."""
    op.drop_column("agent_traces", "metadata_json")
