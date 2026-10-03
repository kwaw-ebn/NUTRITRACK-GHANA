"""Separate health districts from MMDAs and add assigned area access."""

from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "health_districts",
        *identity(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("region_id", sa.String(36), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.UniqueConstraint("region_id", "name")
    )
    op.create_index("ix_health_districts_region_id", "health_districts", ["region_id"])
    op.create_table(
        "access_grants",
        *identity(),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("region_id", sa.String(36), sa.ForeignKey("regions.id")),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False)
    )
    op.create_index("ix_access_grants_user_id", "access_grants", ["user_id"])
    with op.batch_alter_table("organizations") as batch:
        batch.alter_column("district_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("health_district_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_organization_health_district",
            "health_districts",
            ["health_district_id"],
            ["id"],
        )
    with op.batch_alter_table("memberships") as batch:
        batch.add_column(sa.Column("subdistrict_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_membership_subdistrict", "subdistricts", ["subdistrict_id"], ["id"]
        )
    # Existing MMDA labels remain provisional until a directorate verifies the health district.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT o.id, o.region_id, d.name FROM organizations o JOIN districts d ON d.id=o.district_id"
        )
    )
    mapped = {}
    for row in rows:
        key = (row.region_id, row.name)
        if key not in mapped:
            mapped[key] = str(uuid.uuid4())
            connection.execute(
                sa.text(
                    "INSERT INTO health_districts (id,name,region_id,active,source,created_at,updated_at) VALUES (:id,:name,:region,:active,:source,:now,:now)"
                ),
                dict(
                    id=mapped[key],
                    name=row.name,
                    region=row.region_id,
                    active=True,
                    source="Migrated assembly label; health directorate verification required",
                    now=datetime.now(timezone.utc),
                ),
            )
        connection.execute(
            sa.text("UPDATE organizations SET health_district_id=:health WHERE id=:id"),
            dict(health=mapped[key], id=row.id),
        )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM organizations WHERE district_id IS NULL"))
        .scalar()
    ):
        raise RuntimeError(
            "Cannot downgrade: health-only organizations require an Assembly reference under the old schema. Restore a reviewed backup instead."
        )
    with op.batch_alter_table("memberships") as batch:
        batch.drop_constraint("fk_membership_subdistrict", type_="foreignkey")
        batch.drop_column("subdistrict_id")
    with op.batch_alter_table("organizations") as batch:
        batch.drop_constraint("fk_organization_health_district", type_="foreignkey")
        batch.drop_column("health_district_id")
        batch.alter_column("district_id", existing_type=sa.String(36), nullable=False)
    op.drop_table("access_grants")
    op.drop_table("health_districts")
