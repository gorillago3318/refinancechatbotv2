"""Create Lead model

Revision ID: 74ecf55bdd74
Revises: 
Create Date: 2024-12-11 07:42:55.367931

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '74ecf55bdd74'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### Create 'bank_rates' table ###
    op.create_table('bank_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bank_name', sa.String(length=100), nullable=False),
        sa.Column('interest_rate', sa.Float(), nullable=False),
        sa.Column('min_amount', sa.Float(), nullable=False),
        sa.Column('max_amount', sa.Float(), nullable=False),
        sa.Column('tenure_options', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # ### Create 'users' table ###
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wa_id', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wa_id'),
        sa.UniqueConstraint('email')
    )

    # ### Create 'leads' table ###
    op.create_table('leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('original_loan_amount', sa.Float(), nullable=True),
        sa.Column('original_loan_tenure', sa.Integer(), nullable=True),
        sa.Column('current_repayment', sa.Float(), nullable=True),
        sa.Column('remaining_tenure', sa.Integer(), nullable=True),
        sa.Column('interest_rate', sa.Float(), nullable=True),
        sa.Column('new_repayment', sa.Float(), nullable=True),
        sa.Column('monthly_savings', sa.Float(), nullable=True),
        sa.Column('yearly_savings', sa.Float(), nullable=True),
        sa.Column('total_savings', sa.Float(), nullable=True),
        sa.Column('years_saved', sa.Float(), nullable=True),
        sa.Column('conversation_state', sa.String(length=50), nullable=False, server_default='START'),
        sa.Column('question_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='New'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], name='fk_leads_referrer_id', ondelete='CASCADE'),
        sa.UniqueConstraint('phone_number')
    )

    # If referrer_id needs to be altered, explicitly cast it
    op.alter_column('leads', 'referrer_id',
                    existing_type=sa.String(),
                    type_=sa.Integer(),
                    postgresql_using="NULLIF(referrer_id, '')::integer")


def downgrade():
    # Drop all three tables
    op.drop_table('leads')
    op.drop_table('users')
    op.drop_table('bank_rates')
