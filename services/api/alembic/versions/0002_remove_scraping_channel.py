"""remove scraping channel

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21 00:40:00

El canal `scraping` (web scraping de redes y medios) se retira del prototipo.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WITHOUT_SCRAPING = "'pwa', 'sms', 'whatsapp', 'call_123', 'entity', 'lora'"
WITH_SCRAPING = "'pwa', 'sms', 'whatsapp', 'call_123', 'scraping', 'entity', 'lora'"


def upgrade() -> None:
    op.drop_constraint("channel", "reports", type_="check")
    op.create_check_constraint("channel", "reports", f"channel IN ({WITHOUT_SCRAPING})")


def downgrade() -> None:
    op.drop_constraint("channel", "reports", type_="check")
    op.create_check_constraint("channel", "reports", f"channel IN ({WITH_SCRAPING})")
