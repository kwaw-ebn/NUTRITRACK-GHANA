"""Owner-only administration. Privilege checks apply to every route, independently of UI."""

from datetime import timedelta
from types import SimpleNamespace
import secrets
from fastapi import Depends, HTTPException, Request, UploadFile, File
from sqlalchemy import select
from .db import get_db
from .models import *
from .schemas import *
from .security import passwords, digest, utc, audit, ROLES
from .config import settings


def install(app):
    from . import main as core

    def context(db, organization_id, owner):
        if not db.get(Organization, organization_id):
            raise HTTPException(404, "Organization not found")
        return SimpleNamespace(
            user_id=owner.id,
            organization_id=organization_id,
            role="District Nutrition Officer",
            facility_id=None,
            subdistrict_id=None,
            community_id=None,
        )

    def invite(db, user):
        for previous in db.scalars(
            select(PasswordReset).where(
                PasswordReset.user_id == user.id, PasswordReset.used == False
            )
        ):
            previous.used = True
        token = secrets.token_urlsafe(48)
        db.add(
            PasswordReset(
                user_id=user.id, token_hash=digest(token), expires_at=utc() + timedelta(hours=24)
            )
        )
        return {
            "email": user.email,
            "url": f"{settings().frontend_url}/?reset={token}",
            "expires_in_hours": 24,
            "delivery": "Share this single-use link securely with the named staff member. Email delivery has not been attempted.",
        }

    @app.post("/api/platform/organizations", status_code=201)
    def create(
        data: OrganizationProvision,
        request: Request,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        core.limit(request, "organization-provision", 10)
        organization, user, created = core.create_organization(
            data, db, actor_id=owner.id, allow_existing=True
        )
        invitation = invite(db, user) if created else None
        db.commit()
        return {"organization": core.serialize(organization), "invitation": invitation}

    @app.get("/api/platform/organizations/{organization_id}")
    def organization_detail(
        organization_id: str, owner=Depends(core.platform_user), db=Depends(get_db)
    ):
        m = context(db, organization_id, owner)
        return {
            "organization": core.serialize(core.org(db, m)),
            "subdistricts": core.listing(db, Subdistrict, m),
            "facilities": core.listing(db, Facility, m),
            "communities": core.listing(db, Community, m),
            "users": core.users(m, db),
            "indicators": core.listing(db, Indicator, m),
        }

    @app.post("/api/platform/organizations/{organization_id}/subdistricts", status_code=201)
    def subdistrict(
        organization_id: str,
        data: SubdistrictIn,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.add_subdistrict(data, context(db, organization_id, owner), db)

    @app.post("/api/platform/organizations/{organization_id}/facilities", status_code=201)
    def facilities(
        organization_id: str,
        data: FacilityIn,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.add_facility(data, context(db, organization_id, owner), db)

    @app.put("/api/platform/organizations/{organization_id}/facilities/{id}")
    def update_facility(
        organization_id: str,
        id: str,
        data: FacilityIn,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.edit_facility(id, data, context(db, organization_id, owner), db)

    @app.post("/api/platform/organizations/{organization_id}/communities", status_code=201)
    def communities(
        organization_id: str,
        data: CommunityIn,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.add_community(data, context(db, organization_id, owner), db)

    @app.put("/api/platform/organizations/{organization_id}/configuration")
    def configuration(
        organization_id: str,
        data: ConfigurationIn,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.configuration(data, context(db, organization_id, owner), db)

    @app.post("/api/platform/organizations/{organization_id}/indicators", status_code=201)
    def indicators(
        organization_id: str,
        data: IndicatorIn,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.add_indicator(data, context(db, organization_id, owner), db)

    @app.post("/api/platform/organizations/{organization_id}/import/validate")
    async def validate_import(
        organization_id: str,
        file: UploadFile = File(...),
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return await core.validate_import(file, context(db, organization_id, owner), db)

    @app.post("/api/platform/organizations/{organization_id}/import")
    def import_facilities(
        organization_id: str,
        data: list[FacilityIn],
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        return core.import_facilities(data, context(db, organization_id, owner), db)

    @app.post("/api/platform/staff", status_code=201)
    def provision(data: StaffProvision, owner=Depends(core.platform_user), db=Depends(get_db)):
        if data.level == "NATIONAL":
            if data.role != "National Nutrition Administrator" or any(
                [
                    data.region_id,
                    data.organization_id,
                    data.facility_id,
                    data.subdistrict_id,
                    data.community_id,
                ]
            ):
                raise HTTPException(
                    422,
                    "National scope requires the national nutrition role and no local assignment",
                )
        elif data.level == "REGION":
            if (
                data.role != "Regional Nutrition Officer"
                or not data.region_id
                or any(
                    [data.organization_id, data.facility_id, data.subdistrict_id, data.community_id]
                )
            ):
                raise HTTPException(
                    422, "Regional scope requires a region and the regional nutrition role"
                )
            region = db.get(Region, data.region_id)
            if not region or not region.active:
                raise HTTPException(422, "Select an active region")
        else:
            if (
                data.role
                not in set(ROLES)
                - {
                    "System Administrator",
                    "National Nutrition Administrator",
                    "Regional Nutrition Officer",
                }
                or not data.organization_id
                or data.region_id
            ):
                raise HTTPException(422, "Select an organization and an operational or viewer role")
            m = context(db, data.organization_id, owner)
            if data.role == "District Nutrition Officer" and any(
                [data.subdistrict_id, data.facility_id, data.community_id]
            ):
                raise HTTPException(422, "District administrator scope must be district-wide")
            if data.subdistrict_id:
                core.owned(db, Subdistrict, data.subdistrict_id, m)
            if data.facility_id:
                f = core.facility(db, data.facility_id, m)
                if data.subdistrict_id and f.subdistrict_id != data.subdistrict_id:
                    raise HTTPException(422, "Facility belongs to another sub-district")
            if (
                data.role
                in {
                    "Facility In-Charge",
                    "Midwife/ANC Staff",
                    "Community Health Nurse",
                    "School Health/GIFTS Officer",
                    "Field/CHPS Worker",
                }
                and not data.facility_id
            ):
                raise HTTPException(422, "This role requires a facility")
            if data.community_id:
                c = core.owned(db, Community, data.community_id, m)
                if c.facility_id != data.facility_id:
                    raise HTTPException(422, "Community belongs to another facility")
            if data.role == "Field/CHPS Worker" and not data.community_id:
                raise HTTPException(422, "Field workers require a community")
        user = db.scalar(select(User).where(User.email == data.email.lower()))
        created = user is None
        if not user:
            user = User(
                name=data.name,
                email=data.email.lower(),
                password_hash=passwords.hash(secrets.token_urlsafe(40)),
            )
            db.add(user)
            db.flush()
        if not user.active:
            raise HTTPException(422, "Reactivate the staff account before assigning access")
        if data.level == "ORGANIZATION":
            member = db.scalar(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.organization_id == data.organization_id,
                )
            )
            if not member:
                member = Membership(
                    user_id=user.id, organization_id=data.organization_id, role=data.role
                )
                db.add(member)
            member.active = True
            for key in ["role", "facility_id", "subdistrict_id", "community_id"]:
                setattr(member, key, getattr(data, key))
        else:
            grant = db.scalar(
                select(AccessGrant).where(
                    AccessGrant.user_id == user.id,
                    AccessGrant.level == data.level,
                    AccessGrant.region_id == data.region_id,
                )
            )
            if not grant:
                grant = AccessGrant(
                    user_id=user.id, level=data.level, region_id=data.region_id, role=data.role
                )
                db.add(grant)
            grant.active = True
        db.add(
            Audit(
                actor_id=owner.id,
                organization_id=data.organization_id,
                event="staff.scope_assigned",
                entity_id=user.id,
                details={
                    "role": data.role,
                    "level": data.level,
                    "region_id": data.region_id,
                    "facility_id": data.facility_id,
                    "subdistrict_id": data.subdistrict_id,
                    "community_id": data.community_id,
                },
            )
        )
        invitation = invite(db, user) if created else None
        db.commit()
        return {"user": core.serialize(user), "invitation": invitation}

    @app.patch("/api/platform/users/{id}/status")
    def user_status(
        id: str, data: UserStatus, owner=Depends(core.platform_user), db=Depends(get_db)
    ):
        user = db.get(User, id)
        if not user:
            raise HTTPException(404, "User not found")
        if core.is_platform_admin(db, id):
            raise HTTPException(409, "The platform owner cannot be deactivated here")
        user.active = data.active
        if not data.active:
            for session in db.scalars(select(Session).where(Session.user_id == id)):
                session.revoked = True
        db.add(
            Audit(
                actor_id=owner.id,
                event="user.status_changed",
                entity_id=id,
                details={"active": data.active},
            )
        )
        db.commit()
        return {"active": user.active}

    @app.post("/api/platform/users/{id}/invitation")
    def invitation(id: str, owner=Depends(core.platform_user), db=Depends(get_db)):
        user = db.get(User, id)
        if not user or not user.active:
            raise HTTPException(404, "Active user not found")
        if core.is_platform_admin(db, id):
            raise HTTPException(409, "Use password reset for the platform owner")
        result = invite(db, user)
        db.add(Audit(actor_id=owner.id, event="user.invitation_created", entity_id=id))
        db.commit()
        return result

    @app.get("/api/platform/staff")
    def staff(owner=Depends(core.platform_user), db=Depends(get_db)):
        return {
            "users": [core.serialize(u) for u in db.scalars(select(User).order_by(User.name))],
            "memberships": [core.serialize(m) for m in db.scalars(select(Membership))],
            "grants": [core.serialize(g) for g in db.scalars(select(AccessGrant))],
        }

    @app.patch("/api/platform/assignments/{kind}/{id}")
    def assignment_status(
        kind: str, id: str, data: LocalStatus, owner=Depends(core.platform_user), db=Depends(get_db)
    ):
        model = Membership if kind == "membership" else AccessGrant if kind == "grant" else None
        row = db.get(model, id) if model else None
        if not row:
            raise HTTPException(404, "Assignment not found")
        if core.is_platform_admin(db, row.user_id):
            raise HTTPException(409, "Owner assignments require a reviewed ownership transfer")
        row.active = data.active
        db.add(
            Audit(
                actor_id=owner.id,
                event="staff.assignment_status",
                entity_id=id,
                details={"kind": kind, "active": data.active},
            )
        )
        db.commit()
        return {"active": row.active}

    @app.post("/api/platform/programmes", status_code=201)
    def create_programme(data: ProgrammeIn, owner=Depends(core.national_admin), db=Depends(get_db)):
        from .forms import validate_schema

        validate_schema(data.fields)
        row = Programme(**data.model_dump())
        db.add(row)
        db.flush()
        db.add(
            Audit(
                actor_id=owner.id,
                event="programme.created",
                entity_id=row.id,
                details={"code": row.code, "version": 1},
            )
        )
        return core.save(db, row)

    @app.put("/api/platform/programmes/{id}")
    def edit_programme(
        id: str, data: ProgrammeIn, owner=Depends(core.national_admin), db=Depends(get_db)
    ):
        from .forms import validate_schema

        row = db.get(Programme, id)
        if not row:
            raise HTTPException(404, "Programme not found")
        if row.code != data.code:
            raise HTTPException(
                422, "Programme codes cannot change; create a new code to preserve history"
            )
        validate_schema(data.fields)
        if row.fields != data.fields and not data.approval_reference.strip():
            raise HTTPException(422, "Record the approval reference for changed capture fields")
        db.add(
            Audit(
                actor_id=owner.id,
                event="programme.updated",
                entity_id=id,
                details={
                    "previous_fields": row.fields,
                    "previous_version": row.schema_version,
                    "approval_reference": data.approval_reference,
                },
            )
        )
        if row.fields != data.fields:
            row.schema_version += 1
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        return core.save(db, row)

    @app.get("/api/indicator-standards")
    def standard_directory(user=Depends(core.current_user), db=Depends(get_db)):
        return [
            core.serialize(r)
            for r in db.scalars(
                select(StandardIndicator)
                .where(StandardIndicator.active == True)
                .order_by(StandardIndicator.code)
            )
        ]

    @app.post("/api/platform/indicator-standards", status_code=201)
    def standard_create(
        data: StandardIndicatorIn, owner=Depends(core.national_admin), db=Depends(get_db)
    ):
        if not db.scalar(select(Programme.id).where(Programme.code == data.programme)):
            raise HTTPException(422, "Unknown programme")
        if not data.source_url.startswith("https://"):
            raise HTTPException(422, "Use an HTTPS source reference")
        row = StandardIndicator(**data.model_dump(exclude={"standard_id"}))
        db.add(row)
        db.flush()
        db.add(
            Audit(
                actor_id=owner.id,
                event="indicator_standard.created",
                entity_id=row.id,
                details={"code": row.code, "version": row.version},
            )
        )
        return core.save(db, row)

    @app.patch("/api/platform/indicator-standards/{id}/status")
    def standard_status(
        id: str, data: LocalStatus, owner=Depends(core.national_admin), db=Depends(get_db)
    ):
        row = db.get(StandardIndicator, id)
        if not row:
            raise HTTPException(404, "Standard not found")
        row.active = data.active
        db.add(
            Audit(
                actor_id=owner.id,
                event="indicator_standard.status",
                entity_id=id,
                details={"active": data.active},
            )
        )
        return core.save(db, row)

    @app.get("/api/platform/programmes")
    def programme_directory(owner=Depends(core.national_admin), db=Depends(get_db)):
        return [core.serialize(p) for p in db.scalars(select(Programme).order_by(Programme.name))]

    @app.get("/api/platform/master-data")
    def masters(owner=Depends(core.national_admin), db=Depends(get_db)):
        return {
            "regions": [
                core.serialize(r) for r in db.scalars(select(Region).order_by(Region.name))
            ],
            "health_districts": [
                core.serialize(r)
                for r in db.scalars(select(HealthDistrict).order_by(HealthDistrict.name))
            ],
            "imports": [
                core.serialize(r)
                for r in db.scalars(select(MasterImport).order_by(MasterImport.created_at.desc()))
            ],
        }

    @app.put("/api/platform/master-data/regions/{id}")
    def region_change(
        id: str, data: RegionChange, owner=Depends(core.national_admin), db=Depends(get_db)
    ):
        row = db.get(Region, id)
        if not row:
            raise HTTPException(404, "Region not found")
        db.add(
            Audit(
                actor_id=owner.id,
                event="region.versioned_update",
                entity_id=id,
                details={
                    "previous": core.serialize(row),
                    "source": data.source,
                    "source_date": str(data.source_date),
                    "version": data.version,
                },
            )
        )
        for key in ["name", "region_code", "capital", "active"]:
            setattr(row, key, getattr(data, key))
        db.add(
            MasterImport(
                source=data.source,
                source_date=str(data.source_date),
                version=data.version,
                imported_by=owner.id,
                count=1,
            )
        )
        return core.save(db, row)

    @app.patch("/api/platform/master-data/health-districts/{id}/status")
    def district_status(
        id: str, data: LocalStatus, owner=Depends(core.national_admin), db=Depends(get_db)
    ):
        row = db.get(HealthDistrict, id)
        if not row:
            raise HTTPException(404, "Health district not found")
        row.active = data.active
        db.add(
            Audit(
                actor_id=owner.id,
                event="health_district.status",
                entity_id=id,
                details={"active": data.active},
            )
        )
        return core.save(db, row)

    @app.patch("/api/platform/organizations/{organization_id}/structure/{kind}/{id}/status")
    def local_status(
        organization_id: str,
        kind: str,
        id: str,
        data: LocalStatus,
        owner=Depends(core.platform_user),
        db=Depends(get_db),
    ):
        m = context(db, organization_id, owner)
        model = {"subdistricts": Subdistrict, "communities": Community}.get(kind)
        if not model:
            raise HTTPException(404, "Structure type not found")
        row = core.owned(db, model, id, m)
        row.active = data.active
        audit(db, m, "structure.status", id, {"kind": kind, "active": data.active})
        return core.save(db, row)

    @app.get("/api/platform/system")
    def system(owner=Depends(core.platform_user), db=Depends(get_db)):
        technical = SimpleNamespace(
            role="System Administrator", organization_id=None, user_id=owner.id
        )
        return {
            "health": core.admin_health(technical, db),
            "jobs": [
                dict(
                    id=j.id,
                    state=j.state,
                    format=j.format,
                    organization_id=j.organization_id,
                    created_at=j.created_at,
                    error=j.error,
                )
                for j in db.scalars(
                    select(ReportJob).order_by(ReportJob.created_at.desc()).limit(100)
                )
            ],
            "releases": core.changelog(),
        }
