"""keep restricted on messages and ended on conversations

Revision ID: e7b2c91a4f08
Revises: c4a1e8b07d22
Create Date: 2026-10-18 03:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7b2c91a4f08"
down_revision: Union[str, Sequence[str], None] = "c4a1e8b07d22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE conversations
        SET ended = true
        WHERE restricted = true
           OR id IN (
                SELECT conversation_id FROM messages
                WHERE safety->>'risk_level' IN ('high', 'critical')
           )
        """
    )
    op.execute(
        """
        UPDATE messages
        SET restricted = true
        WHERE conversation_id IN (SELECT id FROM conversations WHERE ended = true)
        """
    )
    op.drop_column("conversations", "restricted")


def downgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE conversations SET restricted = true WHERE ended = true")
