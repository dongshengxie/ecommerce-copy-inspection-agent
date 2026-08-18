"""add phase 5 audit tables

Revision ID: e1f5c0d2a4b7
Revises: acc05d636557
Create Date: 2026-08-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f5c0d2a4b7"
down_revision: str | Sequence[str] | None = "acc05d636557"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist exact task rule versions and explicit optimization attempts."""
    op.create_table(
        "inspection_task_rules",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"]),
        sa.PrimaryKeyConstraint("task_id", "rule_id", "rule_version"),
    )
    op.create_table(
        "optimization_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_task_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_fields", sa.JSON(), nullable=False),
        sa.Column("optimized_fields_json", sa.JSON(), nullable=False),
        sa.Column("referenced_issues_json", sa.JSON(), nullable=False),
        sa.Column("referenced_rule_ids", sa.JSON(), nullable=False),
        sa.Column("verification_report_json", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_task_id"], ["inspection_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_optimization_attempts_source_task_id",
        "optimization_attempts",
        ["source_task_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only the Phase 5 audit persistence tables."""
    op.drop_table("optimization_attempts")
    op.drop_table("inspection_task_rules")
