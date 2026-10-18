"""rename stored sensitive_disclosure labels to self_harm

Revision ID: b3c8e1a94d05
Revises: a91d4e6c2b17
Create Date: 2026-10-18 04:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b3c8e1a94d05"
down_revision: Union[str, Sequence[str], None] = "a91d4e6c2b17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE safety_events
        SET category = 'self_harm'
        WHERE category = 'sensitive_disclosure'
        """
    )
    op.execute(
        """
        UPDATE safety_events
        SET notify_suppressed_reason = NULL
        WHERE notify_suppressed_reason = 'sensitive_disclosure'
        """
    )
    op.execute(
        """
        UPDATE safety_events
        SET summary_for_guardian = replace(summary_for_guardian, 'sensitive disclosure', 'self harm')
        WHERE summary_for_guardian ILIKE '%sensitive disclosure%'
        """
    )
    op.execute(
        """
        UPDATE messages
        SET safety = jsonb_set(
            safety::jsonb,
            '{categories}',
            (
                SELECT COALESCE(
                    jsonb_agg(
                        to_jsonb(CASE WHEN item = 'sensitive_disclosure' THEN 'self_harm' ELSE item END)
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements_text(COALESCE(safety::jsonb->'categories', '[]'::jsonb)) AS item
            )
        )::json
        WHERE safety IS NOT NULL
          AND safety::text LIKE '%sensitive_disclosure%'
        """
    )


def downgrade() -> None:
    pass
