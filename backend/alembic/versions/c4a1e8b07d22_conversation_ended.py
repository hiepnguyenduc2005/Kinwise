"""conversation ended flag

Revision ID: c4a1e8b07d22
Revises: 399e4acebde2
Create Date: 2026-10-18 02:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a1e8b07d22"
down_revision: Union[str, Sequence[str], None] = "399e4acebde2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("ended", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE conversations SET ended = true WHERE restricted = true")


def downgrade() -> None:
    op.drop_column("conversations", "ended")
