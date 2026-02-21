"""Update import_logs.source comment after removing API pull sources.

Revision ID: 007
Revises: 006
Create Date: 2026-02-21
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "import_logs",
        "source",
        comment="csv | custom source",
    )


def downgrade() -> None:
    op.alter_column(
        "import_logs",
        "source",
        comment="flex_query | tradovate_api | csv",
    )
