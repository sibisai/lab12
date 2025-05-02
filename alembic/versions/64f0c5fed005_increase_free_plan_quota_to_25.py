"""increase free plan quota to 25

Revision ID: 64f0c5fed005
Revises: 8def3d09d87d
Create Date: 2025-05-02 16:38:21.267274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64f0c5fed005'
down_revision: Union[str, None] = '8def3d09d87d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # bump free plan quota to 25
    op.execute(
        "UPDATE subscription_plans "
        "SET quota = 25 "
        "WHERE name = 'free';"
    )


def downgrade() -> None:
    # revert free plan quota back to 20
    op.execute(
        "UPDATE subscription_plans "
        "SET quota = 20 "
        "WHERE name = 'free';"
    )
