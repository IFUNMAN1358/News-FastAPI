"""add_new_table

Revision ID: 75f6120146e5
Revises: 7ed8caad3497
Create Date: 2024-03-09 20:07:40.813338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75f6120146e5'
down_revision: Union[str, None] = '7ed8caad3497'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('about_me', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'about_me')
    # ### end Alembic commands ###