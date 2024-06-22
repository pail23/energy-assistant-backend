"""remove consumed energy columns

Revision ID: fa8f65c2f997
Revises: 2558c9508fcc
Create Date: 2024-06-11 15:34:29.013567

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "fa8f65c2f997"
down_revision = "2558c9508fcc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("HomeMeasurement") as batch_op:
        batch_op.drop_column("consumed_energy")
        batch_op.drop_column("solar_consumed_energy")


def downgrade() -> None:
    op.add_column("HomeMeasurement", sa.Column("consumed_energy", sa.FLOAT(), nullable=False))
    op.add_column("HomeMeasurement", sa.Column("solar_consumed_energy", sa.FLOAT(), nullable=False))
