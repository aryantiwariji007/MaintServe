"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('team', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('daily_request_limit', sa.Integer(), nullable=True),
        sa.Column('monthly_token_limit', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_api_keys_key', 'api_keys', ['key'], unique=True)

    # Usage Logs table
    op.create_table(
        'usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(64), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('model', sa.String(255), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), default=0),
        sa.Column('completion_tokens', sa.Integer(), default=0),
        sa.Column('total_tokens', sa.Integer(), default=0),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('client_ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_usage_logs_request_id', 'usage_logs', ['request_id'], unique=True)
    op.create_index('ix_usage_logs_created_at', 'usage_logs', ['created_at'])

    # Create default admin user
    op.execute("""
        INSERT INTO users (name, email, is_active, is_admin, created_at, updated_at)
        VALUES ('Admin', 'admin@localhost', true, true, NOW(), NOW())
    """)

    # Create default admin API key
    op.execute("""
        INSERT INTO api_keys (user_id, key, name, description, is_active, created_at)
        VALUES (1, 'ms_admin_default_key_change_me', 'Default Admin Key', 'Default admin key - change in production', true, NOW())
    """)


def downgrade() -> None:
    op.drop_table('usage_logs')
    op.drop_table('api_keys')
    op.drop_table('users')
