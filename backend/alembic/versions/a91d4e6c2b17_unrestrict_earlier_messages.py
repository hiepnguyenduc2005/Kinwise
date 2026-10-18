"""only the closing turn stays restricted

Revision ID: a91d4e6c2b17
Revises: e7b2c91a4f08
Create Date: 2026-10-18 03:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a91d4e6c2b17"
down_revision: Union[str, Sequence[str], None] = "e7b2c91a4f08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE messages SET restricted = false")
    op.execute(
        """
        UPDATE messages
        SET restricted = true
        WHERE safety->>'risk_level' IN ('high', 'critical')
        """
    )
    op.execute(
        """
        UPDATE messages AS child
        SET restricted = true
        FROM messages AS assistant
        WHERE assistant.restricted = true
          AND assistant.sender_role = 'assistant'
          AND child.sender_role = 'child'
          AND child.conversation_id = assistant.conversation_id
          AND child.created_at <= assistant.created_at
          AND NOT EXISTS (
                SELECT 1 FROM messages AS newer
                WHERE newer.conversation_id = child.conversation_id
                  AND newer.sender_role = 'child'
                  AND newer.created_at <= assistant.created_at
                  AND newer.created_at > child.created_at
          )
        """
    )


def downgrade() -> None:
    pass
