"""Label Zomi ctd (ISO 639-3, Tedim) instead of zom (ISO 639-3 Zou) in stored user locales.

Revision ID: 20261027_0004
Revises: 20261025_0003
Create Date: 2026-10-27
"""

from typing import Sequence

from alembic import op


revision: str = "20261027_0004"
down_revision: str | None = "20261025_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE users SET preferred_locale = 'ctd' WHERE preferred_locale = 'zom'")


def downgrade() -> None:
    op.execute("UPDATE users SET preferred_locale = 'zom' WHERE preferred_locale = 'ctd'")
