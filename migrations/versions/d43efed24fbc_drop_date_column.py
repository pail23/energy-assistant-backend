"""Drop date column

Revision ID: d43efed24fbc
Revises: 0bf7066b6d6c
Create Date: 2023-06-18 20:35:43.234174

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d43efed24fbc"
down_revision = "0bf7066b6d6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.drop_column("DeviceMeasurement", "grid_exported_energy")
    with op.batch_alter_table("DeviceMeasurement") as batch_op:
        batch_op.drop_column("date")


def downgrade() -> None:
    op.add_column("DeviceMeasurement", sa.Column("date", sa.DATE(), nullable=False))
