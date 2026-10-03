import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
    Boolean,
    JSON,
    DateTime,
    Float,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Region(Identity, Base):
    __tablename__ = "regions"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    region_code: Mapped[str] = mapped_column(String(40), unique=True)
    capital: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class District(Identity, Base):
    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("region_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"), index=True)
    assembly_type: Mapped[str] = mapped_column(String(20))
    administrative_code: Mapped[str | None] = mapped_column(String(40))
    capital: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[str | None] = mapped_column(String(10))
    effective_to: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(40))


class HealthDistrict(Identity, Base):
    __tablename__ = "health_districts"
    __table_args__ = (UniqueConstraint("region_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(200), default="Authorized local entry")


class AccessGrant(Identity, Base):
    __tablename__ = "access_grants"
    __table_args__ = (
        Index(
            "uq_single_platform_owner",
            "level",
            unique=True,
            postgresql_where=text("level = 'PLATFORM'"),
            sqlite_where=text("level = 'PLATFORM'"),
        ),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    level: Mapped[str] = mapped_column(String(20))
    region_id: Mapped[str | None] = mapped_column(ForeignKey("regions.id"))
    role: Mapped[str] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Organization(Identity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(180))
    organization_type: Mapped[str] = mapped_column(String(80))
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"))
    district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"))
    health_district_id: Mapped[str | None] = mapped_column(ForeignKey("health_districts.id"))
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Identity, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(50))
    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"))
    subdistrict_id: Mapped[str | None] = mapped_column(ForeignKey("subdistricts.id"))
    community_id: Mapped[str | None] = mapped_column(ForeignKey("communities.id"))


class Session(Identity, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class PasswordReset(Identity, Base):
    __tablename__ = "password_resets"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Tenant:
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Subdistrict(Identity, Tenant, Base):
    __tablename__ = "subdistricts"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(50))
    responsible_officer: Mapped[str | None] = mapped_column(String(120))
    contact: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Facility(Identity, Tenant, Base):
    __tablename__ = "facilities"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str | None] = mapped_column(String(50))
    facility_type: Mapped[str] = mapped_column(String(60))
    subdistrict_id: Mapped[str] = mapped_column(ForeignKey("subdistricts.id"), index=True)
    community: Mapped[str | None] = mapped_column(String(120))
    ownership: Mapped[str] = mapped_column(String(60), default="Public")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(254))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    programmes: Mapped[list] = mapped_column(JSON, default=list)


class Community(Identity, Tenant, Base):
    __tablename__ = "communities"
    name: Mapped[str] = mapped_column(String(120))
    chps_zone: Mapped[str | None] = mapped_column(String(100))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Programme(Identity, Base):
    __tablename__ = "programmes"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    approval_reference: Mapped[str] = mapped_column(String(250), default="")
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Indicator(Identity, Tenant, Base):
    __tablename__ = "indicators"
    standard_id: Mapped[str | None] = mapped_column(
        ForeignKey("standard_indicators.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    programme: Mapped[str] = mapped_column(String(60))
    definition: Mapped[str] = mapped_column(Text)
    numerator_definition: Mapped[str] = mapped_column(Text)
    denominator_definition: Mapped[str] = mapped_column(Text)
    target: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(10), default="higher")
    approval_reference: Mapped[str] = mapped_column(String(250))


class Provenance:
    entered_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    modified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[str] = mapped_column(String(30), default="Direct Entry")
    source: Mapped[str | None] = mapped_column(String(200))
    import_batch: Mapped[str | None] = mapped_column(String(36))


class Client(Identity, Tenant, Provenance, Base):
    __tablename__ = "clients"
    name: Mapped[str] = mapped_column(String(120))
    reference: Mapped[str] = mapped_column(String(80))
    date_of_birth: Mapped[str] = mapped_column(String(10))
    sex: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(40))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), index=True)
    community_id: Mapped[str | None] = mapped_column(ForeignKey("communities.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Encounter(Identity, Tenant, Provenance, Base):
    __tablename__ = "encounters"
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), index=True)
    programme: Mapped[str] = mapped_column(String(60))
    visit_date: Mapped[str] = mapped_column(String(10))
    measurements: Mapped[dict] = mapped_column(JSON, default=dict)
    form_version: Mapped[int] = mapped_column(Integer, default=1)
    form_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    assessment: Mapped[str] = mapped_column(Text)
    followup_date: Mapped[str | None] = mapped_column(String(10))
    outcome: Mapped[str | None] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(30), default="Routine")


class Action(Identity, Tenant, Provenance, Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("organization_id", "signal_key"),)
    signal_key: Mapped[str | None] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(180))
    problem: Mapped[str] = mapped_column(Text)
    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"))
    indicator_id: Mapped[str | None] = mapped_column(ForeignKey("indicators.id"))
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[str] = mapped_column(String(10))
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    status: Mapped[str] = mapped_column(String(30), default="Open")
    outcome: Mapped[str | None] = mapped_column(Text)


class Report(Identity, Tenant, Provenance, Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("organization_id", "facility_id", "period"),)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), index=True)
    period: Mapped[str] = mapped_column(String(7))
    state: Mapped[str] = mapped_column(String(30), default="Draft")
    values: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    amendment_reason: Mapped[str | None] = mapped_column(Text)


class OperationalRecord(Identity, Tenant, Provenance, Base):
    __tablename__ = "operational_records"
    kind: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(180))
    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Audit(Identity, Base):
    __tablename__ = "audit_logs"
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    event: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class MasterImport(Identity, Base):
    __tablename__ = "master_imports"
    source: Mapped[str] = mapped_column(Text)
    source_date: Mapped[str] = mapped_column(String(10))
    version: Mapped[str] = mapped_column(String(60), unique=True)
    imported_by: Mapped[str] = mapped_column(String(120))
    count: Mapped[int] = mapped_column(Integer)


class StandardIndicator(Identity, Base):
    __tablename__ = "standard_indicators"
    __table_args__ = (UniqueConstraint("code", "version"),)
    code: Mapped[str] = mapped_column(String(60))
    version: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(160))
    programme: Mapped[str] = mapped_column(String(60))
    definition: Mapped[str] = mapped_column(Text)
    numerator_definition: Mapped[str] = mapped_column(Text)
    denominator_definition: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(10))
    target: Mapped[float | None] = mapped_column(Float)
    approval_reference: Mapped[str] = mapped_column(String(250))
    source_url: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Evidence(Identity, Tenant, Provenance, Base):
    __tablename__ = "evidence"
    record_id: Mapped[str] = mapped_column(ForeignKey("operational_records.id"), index=True)
    filename: Mapped[str] = mapped_column(String(150))
    content_type: Mapped[str] = mapped_column(String(60))
    encrypted_content: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))


class OfflineReceipt(Identity, Tenant, Base):
    __tablename__ = "offline_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "operation_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    operation_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"))


class ReportJob(Identity, Tenant, Base):
    __tablename__ = "report_jobs"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"))
    format: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(20), default="Queued")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encrypted_output: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(500))
