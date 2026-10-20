"""quiz editing

Revision ID: 5b7e2c9d41a3
Revises: 014112924413
Create Date: 2026-10-20 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b7e2c9d41a3"
down_revision: str | None = "014112924413"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quizzes", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("questions", sa.Column("source", sa.Text(), server_default="ai", nullable=False))
    op.create_check_constraint(
        op.f("ck_questions_source_valid"), "questions", "source IN ('ai', 'edited', 'manual')"
    )
    op.alter_column("questions", "page_ref", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE questions SET page_ref = 0 WHERE page_ref IS NULL")
    op.alter_column("questions", "page_ref", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint(op.f("ck_questions_source_valid"), "questions", type_="check")
    op.drop_column("questions", "source")
    op.drop_column("quizzes", "edited_at")
