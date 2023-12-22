"""create device table

Revision ID: efac279d8401
Revises: d43efed24fbc
Create Date: 2023-06-30 15:17:19.222337

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "efac279d8401"
down_revision = "d43efed24fbc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.CHAR(32), nullable=False),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("icon", sa.VARCHAR(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("DeviceMeasurement") as batch_op:
        batch_op.add_column(sa.Column("device_id", sa.CHAR(32), sa.ForeignKey("devices.id")))


def downgrade() -> None:
    with op.batch_alter_table("DeviceMeasurement") as batch_op:
        batch_op.drop_column("device_id")
    op.drop_table("devices")
