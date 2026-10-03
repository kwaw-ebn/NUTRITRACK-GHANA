"""Protect singleton platform-owner provisioning."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_single_platform_owner",
        "access_grants",
        ["level"],
        unique=True,
        postgresql_where=sa.text("level = 'PLATFORM'"),
        sqlite_where=sa.text("level = 'PLATFORM'"),
    )


def downgrade():
    op.drop_index("uq_single_platform_owner", table_name="access_grants")
