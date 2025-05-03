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
    # 1) roles  (static lookup table)
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, unique=True, nullable=False),
    )

    # 2) user_roles  (many‑to‑many join)
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id",  ondelete="CASCADE"), primary_key=True),
    )

    # 3) user_tokens  (OAuth refresh‑tokens etc.)
    op.create_table(
        "user_tokens",
        sa.Column("id",         sa.Integer, primary_key=True),
        sa.Column("user_id",    sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider",   sa.String,  nullable=False),
        sa.Column("refresh_token", sa.String, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_tokens")
    op.drop_table("user_roles")
    op.drop_table("roles")
# ----------------------------------------------------------------------