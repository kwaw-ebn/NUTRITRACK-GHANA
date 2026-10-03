import csv, io, json, secrets, smtplib, calendar
from email.message import EmailMessage
from types import SimpleNamespace
from datetime import date, datetime, timedelta, timezone
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect
from openpyxl import load_workbook
from .config import settings
from .db import get_db
from .models import *
from .schemas import *
from .security import (
    authorized_memberships,
    current_user,
    scope,
    require,
    tokens,
    passwords,
    digest,
    utc,
    aware,
    limit,
    audit,
    ROLES,
    ADMIN,
    CLINICAL,
    AGGREGATE,
    MANAGERS,
)

app = FastAPI(title="NutriTrack Ghana", version=settings().app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().cors_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Organization-ID",
        "X-Setup-Token",
    ],
)


@app.middleware("http")
async def safe_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/sync/") and response.status_code >= 400:
        from .db import SessionLocal

        with SessionLocal() as log_db:
            log_db.add(Audit(event="sync.failed", details={"status": response.status_code}))
            log_db.commit()

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def serialize(row):
    return {
        c.key: getattr(row, c.key)
        for c in inspect(row).mapper.column_attrs
        if c.key not in {"password_hash", "token_hash"}
    }


def save(db, row):
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return serialize(row)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "A conflicting record already exists, or a parent record is invalid"
        )


def org(db, m):
    return db.get(Organization, m.organization_id)


def scoped_query(model, m):
    query = select(model).where(model.organization_id == m.organization_id)
    if m.subdistrict_id:
        facility_ids = select(Facility.id).where(
            Facility.organization_id == m.organization_id,
            Facility.subdistrict_id == m.subdistrict_id,
        )
        if model is Subdistrict:
            query = query.where(Subdistrict.id == m.subdistrict_id)
        elif model is Facility:
            query = query.where(Facility.subdistrict_id == m.subdistrict_id)
        elif hasattr(model, "facility_id"):
            query = query.where(model.facility_id.in_(facility_ids))
    if m.facility_id and model is Facility:
        query = query.where(Facility.id == m.facility_id)
    if m.facility_id and model is Subdistrict:
        query = query.where(
            Subdistrict.id.in_(select(Facility.subdistrict_id).where(Facility.id == m.facility_id))
        )
    if m.facility_id and hasattr(model, "facility_id"):
        query = query.where(model.facility_id == m.facility_id)
    if m.community_id and model is Client:
        query = query.where(Client.community_id == m.community_id)
    return query


def owned(db, model, id, m, lock=False):
    query = scoped_query(model, m).where(model.id == id)
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404, "Record not found within your authorized scope")
    if model is Facility and m.facility_id and row.id != m.facility_id:
        raise HTTPException(404, "Facility not found")
    return row


def facility(db, id, m):
    return owned(db, Facility, id, m)


def enabled(db, m, programme):
    if programme not in org(db, m).configuration.get("programmes", []):
        raise HTTPException(422, "This programme is not enabled for this organization")


def provenance(m):
    return {"organization_id": m.organization_id, "entered_by": m.user_id}


def listing(db, model, m):
    return [
        serialize(r)
        for r in db.scalars(scoped_query(model, m).order_by(model.created_at.desc())).all()
    ]


@app.exception_handler(IntegrityError)
async def conflict_handler(request: Request, error: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "A duplicate record or invalid parent relationship prevented this operation"
        },
    )


@app.get("/health")
def health(db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {
        "status": "ok",
        "version": settings().app_version,
        "environment": settings().environment,
    }


@app.get("/api/public/config")
def public_config(db=Depends(get_db)):
    return {
        "environment": settings().environment,
        "version": settings().app_version,
        "country": "Ghana",
        "main_admin_setup_available": bool(settings().main_admin_email)
        and not db.scalar(select(AccessGrant.id).where(AccessGrant.level == "PLATFORM")),
    }


@app.get("/api/geography/regions")
def regions(db=Depends(get_db)):
    return [
        serialize(r)
        for r in db.scalars(select(Region).where(Region.active == True).order_by(Region.name))
    ]


@app.get("/api/geography/districts")
def districts(region_id: str, q: str = "", db=Depends(get_db)):
    return [
        serialize(r)
        for r in db.scalars(
            select(District)
            .where(
                District.region_id == region_id,
                District.active == True,
                District.name.ilike(f"%{q[:100]}%"),
            )
            .order_by(District.name)
        )
    ]


@app.get("/api/programmes")
def programmes(db=Depends(get_db)):
    return [
        serialize(r)
        for r in db.scalars(
            select(Programme).where(Programme.active == True).order_by(Programme.name)
        )
    ]


@app.post("/api/auth/login")
def login(data: Login, request: Request, db=Depends(get_db)):
    limit(request)
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not user.active or not passwords.verify(data.password, user.password_hash):
        db.add(
            Audit(
                event="login.failed",
                details={"ip": request.client.host if request.client else None},
            )
        )
        db.commit()
        raise HTTPException(401, "Email or password is incorrect")
    result = tokens(db, user)
    db.add(Audit(actor_id=user.id, event="login.success"))
    db.commit()
    return result


@app.post("/api/auth/refresh")
def refresh(data: Refresh, request: Request, db=Depends(get_db)):
    limit(request, "refresh", 30)
    session = db.scalar(
        select(Session).where(Session.token_hash == digest(data.refresh_token)).with_for_update()
    )
    if not session or session.revoked or aware(session.expires_at) < utc():
        raise HTTPException(401, "Refresh session expired")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account unavailable")
    session.revoked = True
    result = tokens(db, user)
    db.commit()
    return result


@app.post("/api/auth/logout")
def logout(data: Refresh, user=Depends(current_user), db=Depends(get_db)):
    # Revoke all sessions on sign-out; access JWTs check session state on every request.
    for session in db.scalars(select(Session).where(Session.user_id == user.id)):
        session.revoked = True
    db.commit()
    return {"message": "Signed out"}


@app.get("/api/auth/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    memberships = authorized_memberships(db, user.id)
    return {
        "user": serialize(user),
        "platform_admin": is_platform_admin(db, user.id),
        "grants": [
            serialize(g)
            for g in db.scalars(
                select(AccessGrant).where(
                    AccessGrant.user_id == user.id, AccessGrant.active == True
                )
            )
        ],
        "memberships": [
            dict(
                id=m.id,
                organization_id=m.organization_id,
                role=m.role,
                facility_id=m.facility_id,
                community_id=m.community_id,
                subdistrict_id=m.subdistrict_id,
                access_level=getattr(
                    m,
                    "access_level",
                    (
                        "FACILITY"
                        if m.facility_id
                        else "SUBDISTRICT" if m.subdistrict_id else "HEALTH_DISTRICT"
                    ),
                ),
                organization=serialize(org(db, m)),
            )
            for m in memberships
        ],
    }


@app.post("/api/auth/password-reset/request")
def request_reset(data: ResetRequest, request: Request, db=Depends(get_db)):
    limit(request, "reset", 3)
    user = db.scalar(select(User).where(User.email == data.email.lower(), User.active == True))
    if user and settings().smtp_host:
        token = secrets.token_urlsafe(48)
        db.add(
            PasswordReset(
                user_id=user.id,
                token_hash=digest(token),
                expires_at=utc() + timedelta(minutes=30),
            )
        )
        message = EmailMessage()
        message["Subject"] = "Reset your NutriTrack password"
        message["From"] = settings().smtp_from
        message["To"] = user.email
        message.set_content(
            f"Reset your password within 30 minutes: {settings().frontend_url}/?reset={token}"
        )
        try:
            with smtplib.SMTP(settings().smtp_host, settings().smtp_port, timeout=10) as smtp:
                smtp.starttls()
                if settings().smtp_user:
                    smtp.login(settings().smtp_user, settings().smtp_password)
                smtp.send_message(message)
            db.commit()
        except Exception:
            db.rollback()
            db.add(Audit(event="password_reset.delivery_failed"))
            db.commit()
    return {
        "message": "If this account exists and email delivery is configured, a reset link will be sent."
    }


@app.post("/api/auth/password-reset/complete")
def complete_reset(data: ResetComplete, request: Request, db=Depends(get_db)):
    limit(request, "reset-complete", 5)
    reset = db.scalar(
        select(PasswordReset)
        .where(PasswordReset.token_hash == digest(data.token))
        .with_for_update()
    )
    if not reset or reset.used or aware(reset.expires_at) < utc():
        raise HTTPException(400, "Invalid or expired reset link")
    user = db.get(User, reset.user_id)
    user.password_hash = passwords.hash(data.password)
    reset.used = True
    for s in db.scalars(select(Session).where(Session.user_id == user.id)):
        s.revoked = True
    db.add(Audit(actor_id=user.id, event="password.changed"))
    db.commit()
    return {"message": "Password updated. Please sign in."}


@app.post("/api/setup", status_code=201)
def setup(
    data: Setup,
    request: Request,
    setup_token: str = Header(default="", alias="X-Setup-Token"),
    db=Depends(get_db),
):
    limit(request, "setup", 5)
    if not settings().setup_token or not secrets.compare_digest(
        setup_token, settings().setup_token
    ):
        raise HTTPException(403, "An authorized onboarding token is required")
    organization, user, _ = create_organization(data, db)
    result = tokens(db, user)
    db.commit()
    return result


def create_organization(data, db, actor_id=None, allow_existing=False):
    if db.scalar(
        select(Organization.id).where(func.lower(Organization.name) == data.name.strip().lower())
    ):
        raise HTTPException(409, "An organization with this name already exists")
    region = db.get(Region, data.region_id)
    if not region or not region.active:
        raise HTTPException(422, "Choose an active region")
    health_name = data.health_district_name.strip()
    if len(health_name) < 2:
        raise HTTPException(422, "Enter the health district name")
    health_district = db.scalar(
        select(HealthDistrict).where(
            HealthDistrict.region_id == data.region_id,
            func.lower(HealthDistrict.name) == health_name.lower(),
        )
    )
    if not health_district:
        health_district = HealthDistrict(name=health_name, region_id=data.region_id)
        db.add(health_district)
        db.flush()
    elif not health_district.active:
        raise HTTPException(422, "This health district is inactive")
    codes = set(db.scalars(select(Programme.code).where(Programme.active == True)))
    if not set(data.programmes) <= codes:
        raise HTTPException(422, "Unknown programme")
    existing_user = db.scalar(select(User).where(User.email == data.admin_email.lower()))
    if existing_user and not allow_existing:
        raise HTTPException(
            409,
            "Administrator email already exists. Ask an administrator to add membership.",
        )
    if len({s.name.casefold() for s in data.subdistricts}) != len(data.subdistricts):
        raise HTTPException(422, "Duplicate sub-districts")
    organization = Organization(
        name=data.name,
        organization_type=data.organization_type,
        region_id=data.region_id,
        district_id=None,
        health_district_id=health_district.id,
        configuration={
            "programmes": data.programmes,
            "facility_types": [
                "Hospital",
                "Polyclinic",
                "Health Centre",
                "CHPS",
                "Clinic",
                "Maternity Home",
                "Other",
            ],
            "report_header": data.name,
            "contact": data.contact,
        },
    )
    db.add(organization)
    db.flush()
    subids = {}
    for sub in data.subdistricts:
        row = Subdistrict(organization_id=organization.id, **sub.model_dump())
        db.add(row)
        db.flush()
        subids[sub.name] = row.id
    for f in data.facilities:
        values = f.model_dump()
        if f.subdistrict_id not in subids:
            raise HTTPException(422, "Setup facility parent must match a sub-district name")
        values["subdistrict_id"] = subids[f.subdistrict_id]
        db.add(Facility(organization_id=organization.id, **values))
    user = existing_user or User(
        name=data.admin_name,
        email=data.admin_email.lower(),
        password_hash=passwords.hash(data.password or secrets.token_urlsafe(40)),
    )
    if existing_user and not user.active:
        raise HTTPException(422, "Administrator account is inactive")
    db.add(user)
    db.flush()
    member = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role="District Nutrition Officer",
    )
    db.add(member)
    db.flush()
    audit(
        db,
        SimpleNamespace(organization_id=organization.id, user_id=actor_id) if actor_id else member,
        "organization.setup",
        organization.id,
        {"subdistricts": len(data.subdistricts), "facilities": len(data.facilities)},
    )
    for definition in data.indicators:
        if definition.programme not in data.programmes:
            raise HTTPException(422, "Setup indicator programme is not enabled")
        db.add(Indicator(organization_id=organization.id, **indicator_values(definition, db)))
    return organization, user, existing_user is None


@app.get("/api/structure")
def structure(m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - {"System Administrator"})
    fs = listing(db, Facility, m)
    if m.facility_id:
        fs = [f for f in fs if f["id"] == m.facility_id]
    cs = listing(db, Community, m)
    if m.community_id:
        cs = [c for c in cs if c["id"] == m.community_id]
    return {
        "organization": serialize(org(db, m)),
        "subdistricts": listing(db, Subdistrict, m),
        "facilities": fs,
        "communities": cs,
    }


@app.post("/api/subdistricts", status_code=201)
def add_subdistrict(data: SubdistrictIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    row = Subdistrict(organization_id=m.organization_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, m, "subdistrict.created", row.id)
    return save(db, row)


@app.post("/api/communities", status_code=201)
def add_community(data: CommunityIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    facility(db, data.facility_id, m)
    row = Community(organization_id=m.organization_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, m, "community.created", row.id)
    return save(db, row)


def validate_facility(data, m, db):
    owned(db, Subdistrict, data.subdistrict_id, m)
    if data.facility_type not in org(db, m).configuration.get("facility_types", []):
        raise HTTPException(422, "Facility type is not configured")
    if not set(data.programmes) <= set(org(db, m).configuration.get("programmes", [])):
        raise HTTPException(422, "Invalid facility programme")


@app.post("/api/facilities", status_code=201)
def add_facility(data: FacilityIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    validate_facility(data, m, db)
    row = Facility(organization_id=m.organization_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, m, "facility.created", row.id)
    return save(db, row)


@app.put("/api/facilities/{id}")
def edit_facility(id: str, data: FacilityIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    row = facility(db, id, m)
    validate_facility(data, m, db)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    audit(db, m, "facility.updated", id, {"active": data.active})
    return save(db, row)


@app.get("/api/facilities/export")
def export_facilities(m=Depends(scope), db=Depends(get_db)):
    require(m, MANAGERS)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "facility_name",
            "facility_code",
            "facility_type",
            "subdistrict",
            "community",
            "ownership",
            "latitude",
            "longitude",
            "status",
        ]
    )
    for f in db.scalars(scoped_query(Facility, m)):
        if m.facility_id and f.id != m.facility_id:
            continue
        row = [
            f.name,
            f.code,
            f.facility_type,
            db.get(Subdistrict, f.subdistrict_id).name,
            f.community,
            f.ownership,
            f.latitude,
            f.longitude,
            "active" if f.active else "inactive",
        ]
        writer.writerow(
            [
                ("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v)
                for v in row
            ]
        )
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=facilities.csv"},
    )


@app.post("/api/facilities/import/validate")
async def validate_import(file: UploadFile = File(), m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(413, "Maximum upload is 2 MB")
    from .onboarding import read_rows
    try:
        rows = read_rows(content, file.filename or "")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Cannot read import: use a valid CSV or XLSX workbook")
    if not rows or len(rows) > 1000:
        raise HTTPException(422, "Provide 1–1000 rows")
    subids = {s.name: s.id for s in db.scalars(scoped_query(Subdistrict, m))}
    existing = {f.name.casefold() for f in db.scalars(scoped_query(Facility, m))}
    seen = set()
    result = []
    for i, r in enumerate(rows, 2):
        errors = []
        value = None
        name = str(r.get("facility_name") or "").strip()
        duplicate = name.casefold() in existing | seen
        if duplicate:
            errors.append("Duplicate facility name")
        try:
            if str(r.get("subdistrict") or "").strip() not in subids:
                raise ValueError("Unknown sub-district")
            value = FacilityIn(
                name=name,
                code=r.get("facility_code") or None,
                facility_type=str(r.get("facility_type") or ""),
                subdistrict_id=subids[str(r.get("subdistrict")).strip()],
                community=r.get("community") or None,
                ownership=r.get("ownership") or "Public",
                latitude=None if r.get("latitude") in ("", None) else r.get("latitude"),
                longitude=(None if r.get("longitude") in ("", None) else r.get("longitude")),
                active=str(r.get("status") or "active").lower() == "active",
            )
            validate_facility(value, m, db)
        except Exception as e:
            errors.append(str(getattr(e, "detail", e))[:250])
        seen.add(name.casefold())
        result.append(
            {
                "row": i,
                "name": name,
                "status": ("Duplicate" if duplicate else ("Invalid" if errors else "Valid")),
                "errors": errors,
                "data": value.model_dump() if value else None,
            }
        )
    return {
        "rows": result,
        "valid": sum(r["status"] == "Valid" for r in result),
        "invalid": sum(r["status"] == "Invalid" for r in result),
        "duplicates": sum(r["status"] == "Duplicate" for r in result),
    }


@app.post("/api/facilities/import")
def import_facilities(data: list[FacilityIn], m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    if not data or len(data) > 1000:
        raise HTTPException(422, "Provide 1–1000 facilities")
    batch = uid()
    for item in data:
        validate_facility(item, m, db)
        db.add(Facility(organization_id=m.organization_id, **item.model_dump()))
    audit(db, m, "facilities.imported", details={"batch": batch, "count": len(data)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Import cancelled: duplicate facility")
    return {"imported": len(data), "batch": batch}


@app.get("/api/users")
def users(m=Depends(scope), db=Depends(get_db)):
    require(m, MANAGERS)
    query = (
        select(User, Membership)
        .join(Membership, User.id == Membership.user_id)
        .where(Membership.organization_id == m.organization_id)
    )
    if m.facility_id:
        query = query.where(Membership.facility_id == m.facility_id)
    elif m.subdistrict_id:
        query = query.where(
            (Membership.subdistrict_id == m.subdistrict_id)
            | Membership.facility_id.in_(
                select(Facility.id).where(
                    Facility.organization_id == m.organization_id,
                    Facility.subdistrict_id == m.subdistrict_id,
                )
            )
        )
    return [
        dict(
            id=u.id,
            name=u.name,
            email=u.email,
            role=membership.role,
            subdistrict_id=membership.subdistrict_id,
            facility_id=membership.facility_id,
        )
        for u, membership in db.execute(query)
    ]


@app.post("/api/users", status_code=201)
def add_user(data: UserIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    if data.role not in ROLES or data.role in {
        "System Administrator",
        "National Nutrition Administrator",
        "Regional Nutrition Officer",
    }:
        raise HTTPException(422, "Higher-scope roles require technical provisioning")
    if data.role == "District Nutrition Officer" and (data.subdistrict_id or data.facility_id):
        raise HTTPException(422, "Use an operational role for sub-district or facility staff")
    if data.subdistrict_id:
        owned(db, Subdistrict, data.subdistrict_id, m)
    if data.facility_id:
        selected_facility = facility(db, data.facility_id, m)
        if data.subdistrict_id and selected_facility.subdistrict_id != data.subdistrict_id:
            raise HTTPException(422, "Facility does not belong to selected sub-district")
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
        raise HTTPException(422, "This role requires facility scope")
    if data.role == "Field/CHPS Worker" and not data.community_id:
        raise HTTPException(422, "Field workers require community scope")
    if data.community_id:
        community = owned(db, Community, data.community_id, m)
        if community.facility_id != data.facility_id:
            raise HTTPException(422, "Community does not belong to facility")
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(
            409,
            "User exists; membership must be provisioned by an authorized administrator",
        )
    user = User(
        name=data.name,
        email=data.email.lower(),
        password_hash=passwords.hash(data.password),
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            user_id=user.id,
            organization_id=m.organization_id,
            role=data.role,
            subdistrict_id=data.subdistrict_id,
            facility_id=data.facility_id,
            community_id=data.community_id,
        )
    )
    audit(db, m, "user.created", user.id, {"role": data.role})
    return save(db, user)


@app.put("/api/configuration")
def configuration(data: ConfigurationIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    if not set(data.programmes) <= set(db.scalars(select(Programme.code))):
        raise HTTPException(422, "Unknown programme")
    row = org(db, m)
    row.configuration = {**row.configuration, **data.model_dump()}
    audit(db, m, "organization.configured", row.id)
    return save(db, row)


@app.get("/api/clients")
def clients(q: str = "", m=Depends(scope), db=Depends(get_db)):
    require(m, CLINICAL)
    rows = db.scalars(
        scoped_query(Client, m).where(Client.name.ilike(f"%{q[:100]}%")).order_by(Client.name)
    ).all()
    audit(db, m, "clients.viewed", details={"count": len(rows)})
    db.commit()
    return [serialize(r) for r in rows]


@app.post("/api/clients", status_code=201)
def add_client(data: ClientIn, m=Depends(scope), db=Depends(get_db)):
    require(m, CLINICAL)
    facility(db, data.facility_id, m)
    if data.community_id:
        c = owned(db, Community, data.community_id, m)
        if c.facility_id != data.facility_id:
            raise HTTPException(422, "Community does not belong to facility")
    if m.community_id and data.community_id != m.community_id:
        raise HTTPException(403, "Client must belong to assigned community")
    if db.scalar(scoped_query(Client, m).where(Client.reference == data.reference)):
        raise HTTPException(409, "Client reference already exists")
    row = Client(**provenance(m), **data.model_dump(mode="json"))
    db.add(row)
    db.flush()
    audit(db, m, "client.created", row.id)
    return save(db, row)


@app.get("/api/encounters")
def encounters(client_id: str | None = None, m=Depends(scope), db=Depends(get_db)):
    require(m, CLINICAL)
    query = scoped_query(Encounter, m)
    if client_id:
        owned(db, Client, client_id, m)
        query = query.where(Encounter.client_id == client_id)
    programme_roles = {
        "School Health/GIFTS Officer": ["gifts"],
        "Midwife/ANC Staff": ["maternal"],
        "Community Health Nurse": ["growth", "iycf", "vitamin-a"],
        "Field/CHPS Worker": ["growth", "iycf", "vitamin-a"],
    }
    if m.role in programme_roles:
        query = query.where(Encounter.programme.in_(programme_roles[m.role]))
    if m.community_id:
        query = query.where(
            Encounter.client_id.in_(
                select(Client.id).where(
                    Client.community_id == m.community_id,
                    Client.organization_id == m.organization_id,
                )
            )
        )
    return [serialize(r) for r in db.scalars(query.order_by(Encounter.visit_date.desc()))]


@app.post("/api/encounters", status_code=201)
def add_encounter(data: EncounterIn, m=Depends(scope), db=Depends(get_db)):
    return save(db, create_encounter(data, m, db))


def create_encounter(data, m, db):
    require(m, CLINICAL)
    client = owned(db, Client, data.client_id, m)
    enabled(db, m, data.programme)
    programme = db.scalar(
        select(Programme).where(Programme.code == data.programme, Programme.active == True)
    )
    if not programme:
        raise HTTPException(422, "This programme is inactive")
    allowed = {
        "Midwife/ANC Staff": {"maternal"},
        "Community Health Nurse": {"growth", "iycf", "vitamin-a"},
        "Field/CHPS Worker": {"growth", "iycf", "vitamin-a"},
        "School Health/GIFTS Officer": {"gifts"},
    }
    if m.role in allowed and data.programme not in allowed[m.role]:
        raise HTTPException(403, "Programme outside your clinical role")
    from .forms import validate_capture

    validate_capture(programme, data.measurements)
    if data.measurements.get("school_id"):
        school = owned(db, OperationalRecord, data.measurements["school_id"], m)
        if school.kind != "schools" or school.facility_id != client.facility_id:
            raise HTTPException(422, "School must belong to the client's facility")
    if db.scalar(
        select(Report.id).where(
            Report.organization_id == m.organization_id,
            Report.facility_id == client.facility_id,
            Report.period == str(data.visit_date)[:7],
            Report.state.in_(["Approved", "Locked"]),
        )
    ):
        raise HTTPException(
            409,
            "This facility reporting period is approved or locked; request an authorized amendment before adding records",
        )
    row = Encounter(
        **provenance(m),
        facility_id=client.facility_id,
        form_version=programme.schema_version,
        form_snapshot=programme.fields,
        **data.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()
    if data.followup_date or data.risk in {"High", "Immediate"}:
        db.add(
            Action(
                **provenance(m),
                title=f"{data.programme} follow-up",
                problem="Recorded assessment requires follow-up",
                facility_id=client.facility_id,
                client_id=client.id,
                assigned_to=m.user_id,
                due_date=str(data.followup_date or date.today()),
                priority=(
                    "Urgent"
                    if data.risk == "Immediate"
                    else "High" if data.risk == "High" else "Medium"
                ),
            )
        )
    audit(db, m, "encounter.created", row.id)
    return row


@app.get("/api/actions")
def actions(m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - AGGREGATE)
    query = scoped_query(Action, m)
    if m.role not in CLINICAL:
        query = query.where(Action.client_id == None)
    if m.community_id:
        query = query.where(
            (Action.assigned_to == m.user_id)
            & (
                (Action.client_id == None)
                | (
                    Action.client_id.in_(
                        select(Client.id).where(Client.community_id == m.community_id)
                    )
                )
            )
        )
    return [serialize(r) for r in db.scalars(query.order_by(Action.due_date))]


@app.post("/api/actions", status_code=201)
def add_action(data: ActionIn, m=Depends(scope), db=Depends(get_db)):
    return save(db, create_action(data, m, db))


def create_action(data, m, db):
    require(m, set(ROLES) - AGGREGATE)
    if data.facility_id:
        facility(db, data.facility_id, m)
    if m.facility_id and data.facility_id != m.facility_id:
        raise HTTPException(403, "Action must belong to assigned facility")
    if data.client_id:
        require(m, CLINICAL)
        c = owned(db, Client, data.client_id, m)
        if c.facility_id != data.facility_id:
            raise HTTPException(422, "Action client and facility must match")
    if data.indicator_id:
        owned(db, Indicator, data.indicator_id, m)
    if data.assigned_to:
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == data.assigned_to,
                Membership.organization_id == m.organization_id,
                Membership.active == True,
            )
        )
        if not membership or membership.role in AGGREGATE:
            raise HTTPException(422, "Choose an operational user in this organization")
        if membership.facility_id and membership.facility_id != data.facility_id:
            raise HTTPException(422, "Assignee facility does not match")
        if data.client_id and membership.role not in CLINICAL:
            raise HTTPException(422, "Client follow-up needs a clinical assignee")
    row = Action(**provenance(m), **data.model_dump(mode="json"))
    db.add(row)
    db.flush()
    audit(db, m, "action.created", row.id)
    return row


@app.patch("/api/actions/{id}")
def update_action(id: str, data: ActionUpdate, m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - AGGREGATE)
    row = owned(db, Action, id, m)
    if row.client_id:
        require(m, CLINICAL)
        owned(db, Client, row.client_id, m)
    if m.role not in MANAGERS and row.assigned_to != m.user_id:
        raise HTTPException(403, "Only the assignee or a manager can update this action")
    row.status = data.status
    row.outcome = data.outcome
    row.modified_by = m.user_id
    audit(db, m, "action.updated", id, {"status": data.status})
    return save(db, row)


@app.get("/api/indicators")
def indicators(m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - {"System Administrator"})
    return listing(db, Indicator, m)


@app.post("/api/indicators", status_code=201)
def add_indicator(data: IndicatorIn, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    enabled(db, m, data.programme)
    values = indicator_values(data, db)
    row = Indicator(organization_id=m.organization_id, **values)
    db.add(row)
    db.flush()
    audit(db, m, "indicator.created", row.id)
    return save(db, row)


def indicator_values(data, db):
    values = data.model_dump()
    if data.standard_id:
        standard = db.get(StandardIndicator, data.standard_id)
        if not standard or not standard.active or standard.programme != data.programme:
            raise HTTPException(422, "Choose an active standard for the enabled programme")
        for key in [
            "name",
            "definition",
            "numerator_definition",
            "denominator_definition",
            "direction",
        ]:
            values[key] = getattr(standard, key)
    return values


@app.get("/api/reports")
def reports(m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - {"System Administrator"})
    return listing(db, Report, m)


def report_values(values, m, db):
    if len({v.indicator_id for v in values}) != len(values):
        raise HTTPException(422, "Duplicate indicator")
    for value in values:
        owned(db, Indicator, value.indicator_id, m)


@app.post("/api/reports", status_code=201)
def add_report(data: ReportIn, m=Depends(scope), db=Depends(get_db)):
    require(m, MANAGERS | CLINICAL | {"School Health/GIFTS Officer"})
    facility(db, data.facility_id, m)
    report_values(data.values, m, db)
    row = Report(**provenance(m), **data.model_dump(mode="json"))
    db.add(row)
    db.flush()
    audit(db, m, "report.created", row.id)
    return save(db, row)


@app.put("/api/reports/{id}")
def edit_report(id: str, data: ReportIn, m=Depends(scope), db=Depends(get_db)):
    require(m, MANAGERS | CLINICAL | {"School Health/GIFTS Officer"})
    row = owned(db, Report, id, m, lock=True)
    if row.state not in {"Draft", "Returned"}:
        raise HTTPException(409, "This report is immutable; request an authorized amendment")
    if data.facility_id != row.facility_id or data.period != row.period:
        raise HTTPException(422, "Report identity cannot change")
    report_values(data.values, m, db)
    row.values = [v.model_dump() for v in data.values]
    row.modified_by = m.user_id
    audit(db, m, "report.updated", id, {"revision": row.revision})
    return save(db, row)


TRANSITIONS = {
    "Draft": {"Submitted"},
    "Returned": {"Submitted"},
    "Submitted": {"Returned", "Verified"},
    "Verified": {"Returned", "Approved"},
    "Approved": {"Locked"},
    "Locked": set(),
}


@app.post("/api/reports/{id}/transition")
def transition(id: str, data: Transition, m=Depends(scope), db=Depends(get_db)):
    require(m, MANAGERS | CLINICAL | {"School Health/GIFTS Officer"})
    row = owned(db, Report, id, m, lock=True)
    workflow = db.get(Organization, m.organization_id).configuration.get(
        "approval_workflow", ["Draft", "Submitted", "Verified", "Approved", "Locked"]
    )
    permitted = set(TRANSITIONS[row.state])
    if row.state == "Submitted" and "Verified" not in workflow:
        permitted = {"Returned", "Approved"}
    if data.state not in permitted:
        raise HTTPException(409, "Invalid reporting workflow transition")
    if data.state in {"Verified", "Returned"}:
        require(m, MANAGERS)
    if data.state in {"Approved", "Locked"}:
        require(m, ADMIN)
    if data.state == "Returned" and len(data.reason.strip()) < 5:
        raise HTTPException(422, "Explain the required correction")
    audit(
        db,
        m,
        "report.transition",
        id,
        {
            "from": row.state,
            "to": data.state,
            "reason": data.reason,
            "revision": row.revision,
        },
    )
    row.state = data.state
    row.modified_by = m.user_id
    return save(db, row)


@app.post("/api/reports/{id}/amend")
def amend(id: str, data: Amendment, m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN)
    row = owned(db, Report, id, m, lock=True)
    if row.state not in {"Approved", "Locked"}:
        raise HTTPException(409, "Only approved or locked reports require amendment")
    audit(
        db,
        m,
        "report.amended",
        id,
        {
            "previous_values": row.values,
            "previous_state": row.state,
            "revision": row.revision,
            "reason": data.reason,
        },
    )
    row.state = "Draft"
    row.revision += 1
    row.amendment_reason = data.reason
    row.modified_by = m.user_id
    return save(db, row)


KINDS = {"supervision", "interventions", "schools", "commodities"}


def validate_record(kind, data):
    d = data.details
    if kind == "supervision":
        if (
            not data.facility_id
            or not d.get("date")
            or (d.get("status", "Completed") == "Completed" and not d.get("findings"))
        ):
            raise HTTPException(422, "Facility, date and findings are required")
        date.fromisoformat(d["date"])
    if kind == "interventions":
        if not d.get("date") or not d.get("problem") or not d.get("responsible_team"):
            raise HTTPException(422, "Date, problem and responsible team are required")
        if int(d.get("number_reached", 0)) < 0:
            raise HTTPException(422, "Number reached must not be negative")
    if kind == "schools":
        if not data.facility_id or not d.get("school_type"):
            raise HTTPException(422, "Assigned facility and school type are required")
        if int(d.get("eligible_population", 0)) < 0:
            raise HTTPException(422, "Population cannot be negative")
    if kind == "commodities":
        if not data.facility_id or not d.get("period"):
            raise HTTPException(422, "Facility and reporting period are required")
        for key in ["opening", "received", "used", "loss", "stockout_days"]:
            if float(d.get(key, 0)) < 0:
                raise HTTPException(422, f"{key} cannot be negative")
        closing = (
            float(d.get("opening", 0))
            + float(d.get("received", 0))
            - float(d.get("used", 0))
            - float(d.get("loss", 0))
        )
        if closing < 0:
            raise HTTPException(422, "Closing balance cannot be negative")
        d["closing"] = closing
        try:
            year, month = map(int, d["period"].split("-"))
            days = calendar.monthrange(year, month)[1]
            if int(d.get("stockout_days", 0)) > days:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "Invalid reporting period or stock-out days")


@app.get("/api/registers/{kind}")
def registers(kind: str, m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - AGGREGATE)
    if kind not in KINDS:
        raise HTTPException(404, "Register not found")
    return [
        serialize(r)
        for r in db.scalars(
            scoped_query(OperationalRecord, m)
            .where(OperationalRecord.kind == kind)
            .order_by(OperationalRecord.created_at.desc())
        )
    ]


@app.post("/api/registers/{kind}", status_code=201)
def add_register(kind: str, data: RecordIn, m=Depends(scope), db=Depends(get_db)):
    require(m, MANAGERS | CLINICAL | {"School Health/GIFTS Officer"})
    if kind not in KINDS:
        raise HTTPException(404, "Register not found")
    if data.facility_id:
        facility(db, data.facility_id, m)
    if m.facility_id and data.facility_id != m.facility_id:
        raise HTTPException(403, "Select your assigned facility")
    if kind == "schools":
        enabled(db, m, "gifts")
    if data.details.get("indicator_id"):
        owned(db, Indicator, data.details["indicator_id"], m)
    if data.details.get("community_id"):
        community = owned(db, Community, data.details["community_id"], m)
        if data.facility_id and community.facility_id != data.facility_id:
            raise HTTPException(422, "Community and facility must match")
    if data.details.get("cost") and m.role not in {
        "District Nutrition Officer",
        "Facility In-Charge",
    }:
        raise HTTPException(
            403, "Cost entry requires district or facility management authorization"
        )
    try:
        validate_record(kind, data)
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid register value")
    row = OperationalRecord(**provenance(m), kind=kind, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, m, f"{kind}.created", row.id)
    if (
        kind == "supervision"
        and data.details.get("corrective_action")
        and data.details.get("status", "Completed") == "Completed"
    ):
        db.add(
            Action(
                **provenance(m),
                title=str(data.details["corrective_action"])[:180],
                problem=str(data.details["findings"]),
                facility_id=data.facility_id,
                due_date=str(data.details.get("followup_date") or date.today()),
                assigned_to=m.user_id,
                source=f"Supervision {row.id}",
                signal_key=f"supervision:{row.id}",
            )
        )
    return save(db, row)


@app.get("/api/dashboard")
def dashboard(m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - {"System Administrator"})
    facilities = list(db.scalars(scoped_query(Facility, m)))
    if m.facility_id:
        facilities = [f for f in facilities if f.id == m.facility_id]
    reports = list(db.scalars(scoped_query(Report, m)))
    approved = [r for r in reports if r.state in {"Approved", "Locked"}]
    indicators = list(db.scalars(scoped_query(Indicator, m)))
    periods = sorted({r.period for r in approved})
    trends = []
    signals = []
    latest = []
    for period in periods:
        period_rows = {"period": period}
        for indicator in indicators:
            values = [
                v
                for r in approved
                if r.period == period
                for v in r.values
                if v["indicator_id"] == indicator.id
            ]
            n = sum(v["numerator"] for v in values)
            d = sum(v["denominator"] for v in values)
            value = round(100 * n / d, 1) if d else None
            period_rows[indicator.name] = value
            if period == periods[-1]:
                latest.append(
                    {
                        "id": indicator.id,
                        "name": indicator.name,
                        "value": value,
                        "target": indicator.target,
                        "numerator": n,
                        "denominator": d,
                        "direction": indicator.direction,
                    }
                )
                if value is not None and (
                    (indicator.direction == "higher" and value < indicator.target)
                    or (indicator.direction == "lower" and value > indicator.target)
                ):
                    signals.append(
                        {
                            "title": indicator.name,
                            "problem": f"{value}% against the approved target of {indicator.target}%. Review service and data gaps.",
                            "priority": "High",
                            "indicator_id": indicator.id,
                            "period": period,
                        }
                    )
        trends.append(period_rows)
    action_query = scoped_query(Action, m)
    if m.community_id:
        action_query = action_query.where(Action.assigned_to == m.user_id)
    action_rows = list(db.scalars(action_query))
    operational = [a for a in action_rows if a.client_id is None or m.role in CLINICAL]
    facility_profiles = []
    current_period = date.today().strftime("%Y-%m")
    for f in facilities:
        fr = [r for r in reports if r.facility_id == f.id]
        recent = max(fr, key=lambda r: r.period) if fr else None
        expected = len(indicators)
        completeness = (
            round(min(100, 100 * len(recent.values) / expected), 1) if recent and expected else 0
        )
        validity = (
            100
            if recent
            and all(
                v["numerator"] <= v["denominator"] and v["denominator"] >= 0 for v in recent.values
            )
            else 0
        )
        # Timeliness is based on actual creation date against next-month 5th; configurable policy is documented.
        timely = 0
        if recent:
            yr, mo = map(int, recent.period.split("-"))
            day = org(db, m).configuration.get("report_deadline_day", 5)
            deadline = date(yr + 1, 1, day) if mo == 12 else date(yr, mo + 1, day)
            submissions = list(
                db.scalars(
                    select(Audit)
                    .where(
                        Audit.entity_id == recent.id,
                        Audit.organization_id == m.organization_id,
                        Audit.event == "report.transition",
                    )
                    .order_by(Audit.created_at.desc())
                )
            )
            submitted = next(
                (
                    a
                    for a in submissions
                    if a.details.get("to") == "Submitted"
                    and a.details.get("revision") == recent.revision
                ),
                None,
            )
            timely = 100 if submitted and submitted.created_at.date() <= deadline else 0
        references = [
            c.reference.strip().casefold()
            for c in db.scalars(
                select(Client).where(
                    Client.organization_id == m.organization_id,
                    Client.facility_id == f.id,
                    Client.active == True,
                )
            )
        ]
        duplicate_rate = (
            round(100 * (len(references) - len(set(references))) / len(references), 1)
            if references
            else None
        )
        configured_programmes = set(f.programmes or org(db, m).configuration.get("programmes", []))
        consistent = (
            100
            if recent
            and all(
                next((i.programme for i in indicators if i.id == v["indicator_id"]), None)
                in configured_programmes
                for v in recent.values
            )
            else 0
        )
        components = {
            "Completeness": completeness,
            "Timeliness": timely,
            "Validity": validity,
            "Consistency": consistent,
            "Duplicate rate": duplicate_rate,
        }
        weights = org(db, m).configuration.get(
            "quality_weights", {"Completeness": 1, "Timeliness": 1, "Validity": 1}
        )
        measured_weights = {k: w for k, w in weights.items() if components.get(k) is not None}
        score = (
            round(
                sum(
                    (100 - components[k] if k == "Duplicate rate" else components[k]) * w
                    for k, w in measured_weights.items()
                )
                / sum(measured_weights.values()),
                1,
            )
            if recent and sum(measured_weights.values())
            else None
        )
        facility_profiles.append(
            {
                "facility_id": f.id,
                "name": f.name,
                "last_report": recent.period if recent else None,
                "report_state": recent.state if recent else None,
                "data_quality": score,
                "components": components,
                "weights": weights,
                "unmeasured": ["Duplicate rate"] if duplicate_rate is None else [],
                "open_actions": sum(
                    a.facility_id == f.id and a.status in {"Open", "In progress"}
                    for a in operational
                ),
                "latitude": f.latitude,
                "longitude": f.longitude,
            }
        )
    return {
        "organization": serialize(org(db, m)),
        "role": m.role,
        "facilities": len(facilities),
        "reporting_period": current_period,
        "approved_reports": len(approved),
        "open_actions": sum(a.status in {"Open", "In progress"} for a in operational),
        "overdue_actions": sum(
            a.status in {"Open", "In progress"} and a.due_date < str(date.today())
            for a in operational
        ),
        "completed_actions": sum(a.status == "Completed" for a in operational),
        "indicators": latest,
        "trends": trends,
        "signals": signals,
        "facility_profiles": facility_profiles,
        "actions": ([serialize(a) for a in operational] if m.role not in AGGREGATE else []),
        "methodology": "Indicators use approved/locked reports only; pooled numerators and denominators. No denominator means no estimate. Quality components measure completeness, timeliness, validity, enabled-programme consistency, and repeated normalized client references within a facility. Duplicate rate is lower-is-better; quality scoring uses 100 minus duplicate rate. Unmeasured components are excluded and shown explicitly. No causal attribution.",
    }


@app.get("/api/admin/audit")
def audit_log(m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN | {"System Administrator"})
    return [
        serialize(a)
        for a in db.scalars(
            select(Audit)
            .where(Audit.organization_id == m.organization_id)
            .order_by(Audit.created_at.desc())
            .limit(200)
        )
    ]


@app.get("/api/admin/health")
def admin_health(m=Depends(scope), db=Depends(get_db)):
    require(m, ADMIN | {"System Administrator"})
    try:
        migration = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        db.rollback()
        migration = "not migrated"
    latest = db.scalar(select(MasterImport).order_by(MasterImport.created_at.desc()))
    return {
        "application": "ok",
        "database": "connected",
        "version": settings().app_version,
        "migration": migration,
        "master_data_version": latest.version if latest else "not seeded",
        "active_sessions": db.scalar(
            select(func.count(Session.id)).where(
                Session.revoked == False, Session.expires_at > utc()
            )
        ),
        "failed_logins_24h": db.scalar(
            select(func.count(Audit.id)).where(
                Audit.event == "login.failed",
                Audit.created_at > utc() - timedelta(days=1),
            )
        ),
        "last_successful_backup": None,
        "backup_status": "Provider-managed backups must be configured and restore-tested",
        "failed_background_jobs": db.scalar(
            select(func.count(ReportJob.id)).where(ReportJob.state == "Failed")
        ),
        "report_queue_pending": db.scalar(
            select(func.count(ReportJob.id)).where(ReportJob.state.in_(["Queued", "Running"]))
        ),
        "completed_report_jobs": db.scalar(
            select(func.count(ReportJob.id)).where(ReportJob.state == "Completed")
        ),
        "synchronization": "Encrypted deferred encounter capture with server permission checks and idempotent replay",
        "sync_errors_24h": db.scalar(
            select(func.count(Audit.id)).where(
                Audit.event == "sync.failed", Audit.created_at > utc() - timedelta(days=1)
            )
        ),
        "secure_evidence_storage": (
            "Configured" if settings().evidence_encryption_key else "Not configured"
        ),
    }


@app.get("/api/changelog")
def changelog():
    return [
        {
            "version": "0.2.0",
            "date": "2026-10-03",
            "features": [
                "Owner organization administration and staff invitations",
                "National/regional overview and versioned indicator comparisons",
                "Configurable programme templates and encrypted deferred capture",
                "Supervision scheduling, encrypted evidence and report outputs",
                "Durable report generation jobs and auditable role revocation",
            ],
            "migration": "0004",
            "status": "Staging; operational acceptance and live backup verification are required",
        },
        {
            "version": "0.1.0",
            "date": "2026-10-03",
            "features": [
                "Organization setup and scoped access",
                "Nutrition encounters and follow-ups",
                "Indicators, monthly approvals and amendments",
                "Facilities, supervision, interventions, schools and commodity registers",
            ],
            "migration": "0001",
            "status": "Pilot foundation; see requirements matrix for production gates",
        },
    ]


@app.get("/api/aggregate/dashboard")
def aggregate_dashboard(user=Depends(current_user), db=Depends(get_db)):
    """Aggregate across explicit authorized memberships, never global clinical access."""
    members = [
        m
        for m in authorized_memberships(db, user.id, aggregate_only=True)
        if m.role in {"National Nutrition Administrator", "Regional Nutrition Officer"}
    ]
    if not members:
        raise HTTPException(403, "An assigned national or regional aggregate role is required")
    ids = [m.organization_id for m in members]
    organizations = list(db.scalars(select(Organization).where(Organization.id.in_(ids))))
    reports = list(
        db.scalars(
            select(Report).where(
                Report.organization_id.in_(ids),
                Report.state.in_(["Approved", "Locked"]),
            )
        )
    )
    regions = {r.id: r.name for r in db.scalars(select(Region))}
    result = []
    for o in organizations:
        result.append(
            {
                "organization_id": o.id,
                "organization_name": o.name,
                "region": regions[o.region_id],
                "region_id": o.region_id,
                "district_id": o.district_id,
                "health_district_id": o.health_district_id,
                "facilities": db.scalar(
                    select(func.count(Facility.id)).where(
                        Facility.organization_id == o.id, Facility.active == True
                    )
                ),
                "approved_reports": sum(r.organization_id == o.id for r in reports),
            }
        )
    return {
        "scope": "Assigned national / regional health-service scope",
        "organizations": result,
        "regions": len({o.region_id for o in organizations}),
        "districts": len({o.health_district_id or o.id for o in organizations}),
        "approved_reports": len(reports),
        "note": "Cross-district clinical records are never included. Comparable national indicator pooling requires standardized indicator identifiers before rollout.",
    }


@app.get("/api/facilities/{id}/profile")
def facility_profile(id: str, m=Depends(scope), db=Depends(get_db)):
    require(m, set(ROLES) - {"System Administrator"})
    f = facility(db, id, m)
    reports = list(
        db.scalars(scoped_query(Report, m).where(Report.facility_id == id).order_by(Report.period))
    )
    approved = [r for r in reports if r.state in {"Approved", "Locked"}]
    registry = list(db.scalars(scoped_query(Indicator, m)))
    trends = []
    for r in approved:
        trend = {"period": r.period}
        for value in r.values:
            indicator = next((i for i in registry if i.id == value["indicator_id"]), None)
            if indicator:
                trend[indicator.name] = (
                    round(100 * value["numerator"] / value["denominator"], 1)
                    if value["denominator"]
                    else None
                )
        trends.append(trend)
    actions = list(db.scalars(scoped_query(Action, m).where(Action.facility_id == id)))
    supervision = list(
        db.scalars(
            scoped_query(OperationalRecord, m).where(
                OperationalRecord.facility_id == id,
                OperationalRecord.kind == "supervision",
            )
        )
    )
    return {
        "facility": serialize(f),
        "reports": len(reports),
        "approved_reports": len(approved),
        "last_report": reports[-1].period if reports else None,
        "trends": trends,
        "indicators": [
            {
                "id": i.id,
                "name": i.name,
                "target": i.target,
                "direction": i.direction,
                "value": trends[-1].get(i.name) if trends else None,
            }
            for i in registry
        ],
        "followup_completed": sum(
            a.client_id is not None and a.status == "Completed" for a in actions
        ),
        "open_actions": sum(a.status in {"Open", "In progress"} for a in actions),
        "supervision_visits": len(supervision),
        "last_supervision": max([r.details.get("date", "") for r in supervision], default=None),
        "programme_coverage": f.programmes or org(db, m).configuration.get("programmes", []),
    }


def is_platform_admin(db, user_id):
    return bool(
        db.scalar(
            select(AccessGrant.id).where(
                AccessGrant.user_id == user_id,
                AccessGrant.level == "PLATFORM",
                AccessGrant.role == "System Administrator",
                AccessGrant.active == True,
            )
        )
    )


def national_admin(user=Depends(current_user), db=Depends(get_db)):
    if not is_platform_admin(db, user.id) and not db.scalar(
        select(AccessGrant.id).where(
            AccessGrant.user_id == user.id,
            AccessGrant.level == "NATIONAL",
            AccessGrant.role == "National Nutrition Administrator",
            AccessGrant.region_id == None,
            AccessGrant.active == True,
        )
    ):
        raise HTTPException(403, "Authorized national master-data administrator required")
    return user


def platform_user(user=Depends(current_user), db=Depends(get_db)):
    if not is_platform_admin(db, user.id):
        raise HTTPException(403, "Main administrator access is required")
    return user


@app.post("/api/platform/setup", status_code=201)
def setup_platform(
    data: MainAdminSetup,
    request: Request,
    setup_token: str = Header(default="", alias="X-Setup-Token"),
    db=Depends(get_db),
):
    limit(request, "platform-setup", 5)
    if (
        not settings().main_admin_email
        or not settings().setup_token
        or not secrets.compare_digest(setup_token, settings().setup_token)
        or data.email.lower() != settings().main_admin_email.lower()
    ):
        raise HTTPException(
            403, "The configured owner email and authorized setup token are required"
        )
    if db.scalar(select(AccessGrant.id).where(AccessGrant.level == "PLATFORM")):
        raise HTTPException(409, "Main administrator setup is already complete")
    if db.scalar(select(User.id).where(User.email == data.email.lower())):
        raise HTTPException(
            409, "An account already uses this email; use reviewed operator provisioning"
        )
    user = User(
        name=data.name, email=data.email.lower(), password_hash=passwords.hash(data.password)
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            AccessGrant(user_id=user.id, level="PLATFORM", role="System Administrator"),
            AccessGrant(user_id=user.id, level="NATIONAL", role="National Nutrition Administrator"),
            Audit(
                actor_id=user.id,
                event="platform.owner_created",
                entity_id=user.id,
                details={"scope": "Platform administration and national aggregate oversight"},
            ),
        ]
    )
    result = tokens(db, user)
    db.commit()
    return result


@app.get("/api/platform/dashboard")
def platform_dashboard(user=Depends(platform_user), db=Depends(get_db)):
    regions = {r.id: r.name for r in db.scalars(select(Region))}
    health_districts = {d.id: d.name for d in db.scalars(select(HealthDistrict))}
    organizations = []
    for o in db.scalars(select(Organization).order_by(Organization.name)):
        organizations.append(
            dict(
                id=o.id,
                name=o.name,
                region_id=o.region_id,
                region=regions.get(o.region_id),
                health_district=health_districts.get(o.health_district_id),
                facilities=db.scalar(
                    select(func.count(Facility.id)).where(Facility.organization_id == o.id)
                ),
                approved_reports=db.scalar(
                    select(func.count(Report.id)).where(
                        Report.organization_id == o.id, Report.state.in_(["Approved", "Locked"])
                    )
                ),
            )
        )
    return dict(
        regions=[dict(id=k, name=v) for k, v in regions.items()],
        organizations=organizations,
        users=[
            dict(id=u.id, name=u.name, email=u.email, active=u.active)
            for u in db.scalars(select(User).order_by(User.name))
        ],
        audit=[
            dict(id=a.id, event=a.event, organization_id=a.organization_id, created_at=a.created_at)
            for a in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100))
        ],
        health=dict(
            database="connected",
            version=settings().app_version,
            migration=(
                db.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if db.bind.dialect.name != "sqlite"
                else "test/development schema"
            ),
        ),
        scope="National platform oversight",
        clinical_access=False,
    )


from .platform import install as install_platform

install_platform(app)

from .intelligence import install as install_intelligence

install_intelligence(app)

from .operations import install as install_operations

install_operations(app)

from .onboarding import install as install_onboarding

install_onboarding(app)


@app.post("/api/sync/encounters", status_code=201)
def sync_encounter(
    data: OfflineEncounterIn, request: Request, m=Depends(scope), db=Depends(get_db)
):
    require(m, CLINICAL)
    limit(request, "offline-sync", 30)
    value = data.encounter.model_dump(mode="json")
    fingerprint = digest(json.dumps(value, sort_keys=True, separators=(",", ":")))
    receipt = db.scalar(
        select(OfflineReceipt).where(
            OfflineReceipt.organization_id == m.organization_id,
            OfflineReceipt.user_id == m.user_id,
            OfflineReceipt.operation_id == data.operation_id,
        )
    )
    if receipt:
        if receipt.payload_hash != fingerprint:
            raise HTTPException(
                409, "This operation identifier was already used for different data"
            )
        return {"record": serialize(owned(db, Encounter, receipt.resource_id, m)), "replayed": True}
    row = create_encounter(data.encounter, m, db)
    row.source_type = "Offline Sync"
    row.source = "User-approved encrypted deferred capture"
    db.add(
        OfflineReceipt(
            organization_id=m.organization_id,
            user_id=m.user_id,
            operation_id=data.operation_id,
            payload_hash=fingerprint,
            resource_id=row.id,
        )
    )
    audit(db, m, "offline.encounter_synced", row.id, {"operation_id": data.operation_id})
    db.commit()
    return {"record": serialize(row), "replayed": False}


from .jobs import install as install_jobs

install_jobs(app)
