"""Programme schemas, shared indicators, revocable memberships and secure supervision evidence."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.add_column(
        "memberships", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "programmes", sa.Column("fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
    )
    op.add_column(
        "programmes", sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "programmes",
        sa.Column("approval_reference", sa.String(250), nullable=False, server_default=""),
    )
    op.add_column(
        "encounters", sa.Column("form_version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "encounters",
        sa.Column("form_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    with op.batch_alter_table("actions") as batch:
        batch.add_column(sa.Column("signal_key", sa.String(160), nullable=True))
        batch.create_unique_constraint("uq_action_signal", ["organization_id", "signal_key"])
    op.create_table(
        "standard_indicators",
        *identity(),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("programme", sa.String(60), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("numerator_definition", sa.Text(), nullable=False),
        sa.Column("denominator_definition", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("target", sa.Float()),
        sa.Column("approval_reference", sa.String(250), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", "version", name="uq_standard_code_version")
    )
    with op.batch_alter_table("indicators") as batch:
        batch.add_column(sa.Column("standard_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_indicator_standard", "standard_indicators", ["standard_id"], ["id"]
        )
        batch.create_index("ix_indicators_standard_id", ["standard_id"])
    op.create_table(
        "evidence",
        *identity(),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("entered_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="Direct Entry"),
        sa.Column("source", sa.String(200)),
        sa.Column("import_batch", sa.String(36)),
        sa.Column(
            "record_id", sa.String(36), sa.ForeignKey("operational_records.id"), nullable=False
        ),
        sa.Column("filename", sa.String(150), nullable=False),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("encrypted_content", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False)
    )
    op.create_index("ix_evidence_organization_id", "evidence", ["organization_id"])
    op.create_index("ix_evidence_record_id", "evidence", ["record_id"])
    op.create_table(
        "offline_receipts",
        *identity(),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation_id", sa.String(36), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey("encounters.id"), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "user_id", "operation_id", name="uq_offline_operation"
        )
    )
    op.create_index("ix_offline_receipts_organization_id", "offline_receipts", ["organization_id"])
    op.create_table(
        "report_jobs",
        *identity(),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("facility_id", sa.String(36), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="Queued"),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("encrypted_output", sa.Text()),
        sa.Column("error", sa.String(500))
    )
    op.create_index("ix_report_jobs_organization_id", "report_jobs", ["organization_id"])


def downgrade():
    op.drop_table("report_jobs")
    op.drop_table("offline_receipts")
    op.drop_table("evidence")
    with op.batch_alter_table("indicators") as batch:
        batch.drop_index("ix_indicators_standard_id")
        batch.drop_constraint("fk_indicator_standard", type_="foreignkey")
        batch.drop_column("standard_id")
    op.drop_table("standard_indicators")
    with op.batch_alter_table("actions") as batch:
        batch.drop_constraint("uq_action_signal", type_="unique")
        batch.drop_column("signal_key")
    op.drop_column("encounters", "form_snapshot")
    op.drop_column("encounters", "form_version")
    op.drop_column("programmes", "approval_reference")
    op.drop_column("programmes", "schema_version")
    op.drop_column("programmes", "fields")
    op.drop_column("memberships", "active")
