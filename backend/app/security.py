import hashlib, secrets, threading, time
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, Request, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from .config import settings
from .db import get_db
from .models import User, Membership, Session, Audit, AccessGrant, Organization
from types import SimpleNamespace

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
ROLES = [
    "System Administrator",
    "National Nutrition Administrator",
    "Regional Nutrition Officer",
    "District Nutrition Officer",
    "Nutritionist/Dietitian",
    "Facility In-Charge",
    "Midwife/ANC Staff",
    "Community Health Nurse",
    "School Health/GIFTS Officer",
    "Field/CHPS Worker",
    "Data Officer",
    "Viewer",
]
ADMIN = {"District Nutrition Officer"}
CLINICAL = {
    "District Nutrition Officer",
    "Nutritionist/Dietitian",
    "Midwife/ANC Staff",
    "Community Health Nurse",
    "Field/CHPS Worker",
}
AGGREGATE = {
    "National Nutrition Administrator",
    "Regional Nutrition Officer",
    "Viewer",
    "System Administrator",
}
MANAGERS = {"District Nutrition Officer", "Facility In-Charge", "Data Officer"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def utc():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def tokens(db, user):
    refresh = secrets.token_urlsafe(48)
    session = Session(
        user_id=user.id,
        token_hash=digest(refresh),
        expires_at=utc() + timedelta(days=settings().refresh_days),
    )
    db.add(session)
    db.flush()
    access = jwt.encode(
        {
            "sub": user.id,
            "sid": session.id,
            "exp": utc() + timedelta(minutes=settings().access_minutes),
            "iat": utc(),
            "iss": "nutritrack",
            "aud": "nutritrack-api",
        },
        settings().jwt_secret,
        algorithm="HS256",
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings().access_minutes * 60,
    }


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
):
    try:
        if not credentials:
            raise ValueError()
        payload = jwt.decode(
            credentials.credentials,
            settings().jwt_secret,
            algorithms=["HS256"],
            audience="nutritrack-api",
            issuer="nutritrack",
        )
        user = db.get(User, payload["sub"])
        session = db.get(Session, payload["sid"])
        if (
            not user
            or not user.active
            or not session
            or session.user_id != user.id
            or session.revoked
            or aware(session.expires_at) < utc()
        ):
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Your session has expired. Please sign in again.")


def scope(
    organization_id: str = Header(alias="X-Organization-ID"),
    user=Depends(current_user),
    db=Depends(get_db),
):
    members = authorized_memberships(db, user.id)
    member = next((m for m in members if m.organization_id == organization_id), None)
    if not member:
        raise HTTPException(403, "You do not have access to this organization")
    return member


def authorized_memberships(db, user_id, aggregate_only=False):
    """Resolve explicit assignments; rank never grants clinical access."""
    members = list(db.scalars(select(Membership).where(Membership.user_id == user_id)))
    if aggregate_only:
        members = [
            m
            for m in members
            if m.role in {"National Nutrition Administrator", "Regional Nutrition Officer"}
        ]
    existing = {m.organization_id for m in members}
    grants = db.scalars(
        select(AccessGrant).where(AccessGrant.user_id == user_id, AccessGrant.active == True)
    )
    for grant in grants:
        if (
            grant.level == "NATIONAL"
            and grant.role == "National Nutrition Administrator"
            and grant.region_id is None
        ):
            query = select(Organization)
        elif (
            grant.level == "REGION"
            and grant.role == "Regional Nutrition Officer"
            and grant.region_id
        ):
            query = select(Organization).where(Organization.region_id == grant.region_id)
        else:
            continue  # Invalid assignments fail closed.
        for organization in db.scalars(query):
            if organization.id in existing:
                continue
            members.append(
                SimpleNamespace(
                    id=grant.id,
                    user_id=user_id,
                    organization_id=organization.id,
                    role=grant.role,
                    facility_id=None,
                    community_id=None,
                    subdistrict_id=None,
                    access_level=grant.level,
                )
            )
            existing.add(organization.id)
    return members


def require(member, roles):
    if member.role not in roles:
        raise HTTPException(403, "Your role does not permit this operation")


def audit(db, member, event, entity_id=None, details=None):
    db.add(
        Audit(
            organization_id=member.organization_id,
            actor_id=member.user_id,
            event=event,
            entity_id=entity_id,
            details=details or {},
        )
    )


# Local limiter for development. Production gateway must enforce distributed limits.
_attempts = {}
_lock = threading.Lock()


def limit(request: Request, bucket="auth", maximum=10):
    key = (request.client.host if request.client else "unknown", bucket)
    with _lock:
        cutoff = time.monotonic() - 60
        attempts = [t for t in _attempts.get(key, []) if t > cutoff]
        if len(attempts) >= maximum:
            raise HTTPException(429, "Too many attempts. Try again in a minute.")
        attempts.append(time.monotonic())
        _attempts[key] = attempts
        if len(_attempts) > 10000:
            for old in list(_attempts):
                if not _attempts[old] or _attempts[old][-1] < cutoff:
                    _attempts.pop(old, None)
