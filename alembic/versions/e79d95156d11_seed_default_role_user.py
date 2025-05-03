"""seed default role user

Revision ID: e79d95156d11
Revises: 6c87c833ad3d
Create Date: 2025-05-02 17:45:50.492915

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e79d95156d11'
down_revision: Union[str, None] = '6c87c833ad3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # SQLAlchemy helper is nicer than raw SQL
    op.create_unique_constraint(
        "user_only_one_role",         # constraint name
        "user_roles",                 # table
        ["user_id"],                  # column(s)
    )

def downgrade() -> None:
    op.drop_constraint(
        "user_only_one_role",
        "user_roles",
        type_="unique",
    )