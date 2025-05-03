"""seed default subscription plans

Revision ID: 444ddf74c1f6
Revises: 64f0c5fed005
Create Date: 2025-05-02 17:00:14.455621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '444ddf74c1f6'
down_revision: Union[str, None] = '64f0c5fed005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.execute("""
        INSERT INTO subscription_plans (name, quota, price) VALUES
        ('free', 25, 0.00),
        ('pro',  100, 4.99)
        ON CONFLICT (name) DO NOTHING;
    """)

def downgrade() -> None:
    op.execute("""
        DELETE FROM subscription_plans
        WHERE name IN ('free','pro');
    """)