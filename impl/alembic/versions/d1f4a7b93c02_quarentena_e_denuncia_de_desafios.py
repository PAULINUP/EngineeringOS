"""quarentena e denúncia de desafios

Revision ID: d1f4a7b93c02
Revises: cb32b402af5a
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1f4a7b93c02"
down_revision: Union[str, None] = "cb32b402af5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "challenges",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "challenge_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id", "learner_id",
                            name="uq_report_challenge_learner"),
    )
    op.create_index("ix_challenge_reports_challenge_id", "challenge_reports",
                    ["challenge_id"])
    op.create_index("ix_challenge_reports_learner_id", "challenge_reports",
                    ["learner_id"])


def downgrade() -> None:
    op.drop_index("ix_challenge_reports_learner_id", table_name="challenge_reports")
    op.drop_index("ix_challenge_reports_challenge_id", table_name="challenge_reports")
    op.drop_table("challenge_reports")
    op.drop_column("challenges", "active")
