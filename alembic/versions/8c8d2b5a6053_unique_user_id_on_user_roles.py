"""unique user_id on user_roles

Revision ID: 8c8d2b5a6053
Revises: e79d95156d11
Create Date: 2025-05-02 17:53:32.659849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c8d2b5a6053'
down_revision: Union[str, None] = 'e79d95156d11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
