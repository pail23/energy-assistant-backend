"""create session log table

Revision ID: b6020d5b13fc
Revises: efac279d8401
Create Date: 2023-07-24 12:58:37.970137

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b6020d5b13fc'
down_revision = 'efac279d8401'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('session_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('device_id', sa.CHAR(32), nullable=False),
    sa.Column('start', sa.DateTime(), nullable=False),
    sa.Column('end', sa.DateTime(), nullable=False),
    sa.Column('start_consumed_energy', sa.Float(), nullable=False),
    sa.Column('start_solar_consumed_energy', sa.Float(), nullable=False),
    sa.Column('end_consumed_energy', sa.Float(), nullable=False),
    sa.Column('end_solar_consumed_energy', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], name=op.f('fk_session_log_device_id_devices')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_session_log'))
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('session_log')
    # ### end Alembic commands ###