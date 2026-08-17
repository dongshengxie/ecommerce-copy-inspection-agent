"""create_phase_2_core_tables

Revision ID: cb6cebe6f8e7
Revises:
Create Date: 2026-08-18 01:57:08.343399

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cb6cebe6f8e7"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the seven Phase 2 core tables."""
    op.create_table(
        "products",
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_table(
        "product_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "revision", name="uq_product_revision"),
    )
    op.create_table(
        "quality_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_at", sa.String(length=64), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "version", name="uq_rule_version"),
    )
    op.create_table(
        "inspection_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_revision_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger_source", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_revision_id"], ["product_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "inspection_results",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("automated_risk_level", sa.String(length=16), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("degradation_flags", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"]),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_table(
        "inspection_issues",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("field", sa.String(length=128), nullable=False),
        sa.Column("issue_type", sa.String(length=128), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=False),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("tool_or_skill_name", sa.String(length=128), nullable=False),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove only the tables created by this revision."""
    op.drop_table("agent_traces")
    op.drop_table("inspection_issues")
    op.drop_table("inspection_results")
    op.drop_table("inspection_tasks")
    op.drop_table("quality_rules")
    op.drop_table("product_revisions")
    op.drop_table("products")
