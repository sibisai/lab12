"""add roles / user_roles / user_tokens tables

Revision ID: 6c87c833ad3d
Revises: 444ddf74c1f6
Create Date: 2025-05-02 17:39:13.250297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c87c833ad3d'
down_revision: Union[str, None] = '444ddf74c1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
