"""Add prototype_validations table for the automated prototype readiness gate."""

from alembic import op
import sqlalchemy as sa

revision = "0002_prototype_validations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prototype_validations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("prototype_version", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(16), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_prototype_validations_project_id", "prototype_validations", ["project_id"])
    op.create_index("ix_prototype_validations_version", "prototype_validations", ["prototype_version"])
    op.create_index("ix_prototype_validations_verdict", "prototype_validations", ["verdict"])


def downgrade() -> None:
    op.drop_table("prototype_validations")
