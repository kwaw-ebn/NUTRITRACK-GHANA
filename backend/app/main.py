import csv, io, json, secrets, smtplib, calendar
from email.message import EmailMessage
from datetime import date, datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Header
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
    allow_headers=["Authorization", "Content-Type", "X-Organization-ID", "X-Setup-Token"],
)


@app.middleware("http")
async def safe_headers(request, call_next):
    response = await call_next(request)
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
def public_config():
    return {
        "environment": settings().environment,
        "version": settings().app_version,
        "country": "Ghana",
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
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return {
        "user": serialize(user),
        "memberships": [
            dict(serialize(m), organization=serialize(org(db, m))) for m in memberships
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
                user_id=user.id, token_hash=digest(token), expires_at=utc() + timedelta(minutes=30)
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
    district = db.get(District, data.district_id)
    if not district or not district.active or district.region_id != data.region_id:
        raise HTTPException(422, "Choose an MMDA belonging to the selected region")
    codes = set(db.scalars(select(Programme.code).where(Programme.active == True)))
    if not set(data.programmes) <= codes:
        raise HTTPException(422, "Unknown programme")
    if db.scalar(select(User).where(User.email == data.admin_email.lower())):
        raise HTTPException(
            409, "Administrator email already exists. Ask an administrator to add membership."
        )
    if len({s.name.casefold() for s in data.subdistricts}) != len(data.subdistricts):
        raise HTTPException(422, "Duplicate sub-districts")
    organization = Organization(
        name=data.name,
        organization_type=data.organization_type,
        region_id=data.region_id,
        district_id=data.district_id,
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
    user = User(
        name=data.admin_name,
        email=data.admin_email.lower(),
        password_hash=passwords.hash(data.password),
    )
    db.add(user)
    db.flush()
    member = Membership(
        user_id=user.id, organization_id=organization.id, role="District Nutrition Officer"
    )
    db.add(member)
    db.flush()
    audit(
        db,
        member,
        "organization.setup",
        organization.id,
        {"subdistricts": len(data.subdistricts), "facilities": len(data.facilities)},
    )
    result = tokens(db, user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate organization structure")
    return result


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
                "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v
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
    try:
        if (file.filename or "").lower().endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        elif (file.filename or "").lower().endswith(".xlsx"):
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            if sheet.max_row and sheet.max_row > 1001:
                raise ValueError("Maximum 1000 rows")
            values = list(sheet.values)
            rows = [dict(zip(values[0], r)) for r in values[1:]]
        else:
            raise ValueError("Use CSV or XLSX")
    except Exception as e:
        raise HTTPException(422, f"Cannot read import: {str(e)[:100]}")
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
                longitude=None if r.get("longitude") in ("", None) else r.get("longitude"),
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
                "status": "Duplicate" if duplicate else ("Invalid" if errors else "Valid"),
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
    return [
        dict(
            id=u.id,
            name=u.name,
            email=u.email,
            role=membership.role,
            facility_id=membership.facility_id,
        )
        for u, membership in db.execute(
            select(User, Membership)
            .join(Membership, User.id == Membership.user_id)
            .where(Membership.organization_id == m.organization_id)
        )
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
    if data.facility_id:
        facility(db, data.facility_id, m)
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
            409, "User exists; membership must be provisioned by an authorized administrator"
        )
    user = User(
        name=data.name, email=data.email.lower(), password_hash=passwords.hash(data.password)
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            user_id=user.id,
            organization_id=m.organization_id,
            role=data.role,
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
    require(m, CLINICAL)
    client = owned(db, Client, data.client_id, m)
    enabled(db, m, data.programme)
    allowed = {
        "Midwife/ANC Staff": {"maternal"},
        "Community Health Nurse": {"growth", "iycf", "vitamin-a"},
        "Field/CHPS Worker": {"growth", "iycf", "vitamin-a"},
    }
    if m.role in allowed and data.programme not in allowed[m.role]:
        raise HTTPException(403, "Programme outside your clinical role")
    row = Encounter(**provenance(m), facility_id=client.facility_id, **data.model_dump(mode="json"))
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
    return save(db, row)


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
    return save(db, row)


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
    row = Indicator(organization_id=m.organization_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, m, "indicator.created", row.id)
    return save(db, row)


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
    if data.state not in TRANSITIONS[row.state]:
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
        {"from": row.state, "to": data.state, "reason": data.reason, "revision": row.revision},
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
        if not data.facility_id or not d.get("date") or not d.get("findings"):
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
    try:
        validate_record(kind, data)
    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid register value")
    row = OperationalRecord(**provenance(m), kind=kind, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, m, f"{kind}.created", row.id)
    if kind == "supervision" and data.details.get("corrective_action"):
        db.add(
            Action(
                **provenance(m),
                title=str(data.details["corrective_action"])[:180],
                problem=str(data.details["findings"]),
                facility_id=data.facility_id,
                due_date=str(data.details.get("followup_date") or date.today()),
                assigned_to=m.user_id,
                source=f"Supervision {row.id}",
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
        components = {"Completeness": completeness, "Timeliness": timely, "Validity": validity}
        weights = org(db, m).configuration.get(
            "quality_weights", {"Completeness": 1, "Timeliness": 1, "Validity": 1}
        )
        score = (
            round(sum(components[k] * weights[k] for k in components) / sum(weights.values()), 1)
            if recent
            else None
        )
        # Consistency/duplicates are intentionally not fabricated until linked-source checks exist.
        facility_profiles.append(
            {
                "facility_id": f.id,
                "name": f.name,
                "last_report": recent.period if recent else None,
                "report_state": recent.state if recent else None,
                "data_quality": score,
                "components": components,
                "weights": weights,
                "unmeasured": ["Consistency", "Duplicate rate"],
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
        "actions": [serialize(a) for a in operational] if m.role not in AGGREGATE else [],
        "methodology": "Indicators use approved/locked reports only; pooled numerators and denominators. No denominator means no estimate. Quality score uses configured weights across completeness, timeliness and validity only; consistency and duplicate checks are unmeasured. No causal attribution.",
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
                Audit.event == "login.failed", Audit.created_at > utc() - timedelta(days=1)
            )
        ),
        "last_successful_backup": None,
        "backup_status": "Provider-managed backups must be configured and restore-tested",
        "background_jobs": "Not configured",
        "report_queue": "Synchronous reporting",
        "synchronization": "Offline clinical synchronization is not enabled",
    }


@app.get("/api/changelog")
def changelog():
    return [
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
        }
    ]


@app.get("/api/aggregate/dashboard")
def aggregate_dashboard(user=Depends(current_user), db=Depends(get_db)):
    """Aggregate across explicit authorized memberships, never global clinical access."""
    members = list(
        db.scalars(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.role.in_(
                    ["National Nutrition Administrator", "Regional Nutrition Officer"]
                ),
            )
        )
    )
    if not members:
        raise HTTPException(403, "An assigned national or regional aggregate role is required")
    ids = [m.organization_id for m in members]
    organizations = list(db.scalars(select(Organization).where(Organization.id.in_(ids))))
    reports = list(
        db.scalars(
            select(Report).where(
                Report.organization_id.in_(ids), Report.state.in_(["Approved", "Locked"])
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
                "facilities": db.scalar(
                    select(func.count(Facility.id)).where(
                        Facility.organization_id == o.id, Facility.active == True
                    )
                ),
                "approved_reports": sum(r.organization_id == o.id for r in reports),
            }
        )
    return {
        "scope": "Explicitly assigned organizations only",
        "organizations": result,
        "regions": len({o.region_id for o in organizations}),
        "districts": len({o.district_id for o in organizations}),
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
                OperationalRecord.facility_id == id, OperationalRecord.kind == "supervision"
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
