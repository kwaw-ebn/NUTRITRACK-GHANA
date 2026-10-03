"""Operator-only administration through authenticated infrastructure access.

This is deliberately not exposed as a public HTTP endpoint. Run under the
production service's restricted shell identity and retain deployment audit logs.
"""

import argparse, getpass
from sqlalchemy import select
from .db import SessionLocal
from .models import (
    User,
    Membership,
    Organization,
    Programme,
    Audit,
    AccessGrant,
    Region,
)
from .security import passwords, ROLES


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    member = sub.add_parser("grant-membership")
    member.add_argument("--email", required=True)
    member.add_argument("--name", required=True)
    member.add_argument("--organization", required=True)
    member.add_argument("--role", required=True, choices=ROLES)
    member.add_argument("--operator", required=True)
    grant = sub.add_parser("grant-area-access")
    grant.add_argument("--email", required=True)
    grant.add_argument("--name", required=True)
    grant.add_argument("--level", required=True, choices=["NATIONAL", "REGION"])
    grant.add_argument("--region")
    grant.add_argument("--operator", required=True)
    programme = sub.add_parser("add-programme")
    programme.add_argument("--code", required=True)
    programme.add_argument("--name", required=True)
    programme.add_argument("--operator", required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "grant-area-access":
            if args.level == "REGION" and (not args.region or not db.get(Region, args.region)):
                raise ValueError("Regional access requires a valid region UUID")
            if args.level == "NATIONAL" and args.region:
                raise ValueError("National access must not specify a region")
            user = db.scalar(select(User).where(User.email == args.email.lower()))
            if not user:
                password = getpass.getpass("New user secure password (min 12 characters): ")
                if len(password) < 12:
                    raise ValueError("Password is too short")
                user = User(
                    email=args.email.lower(),
                    name=args.name,
                    password_hash=passwords.hash(password),
                )
                db.add(user)
                db.flush()
            role = (
                "National Nutrition Administrator"
                if args.level == "NATIONAL"
                else "Regional Nutrition Officer"
            )
            db.add(AccessGrant(user_id=user.id, level=args.level, region_id=args.region, role=role))
            db.add(
                Audit(
                    actor_id=user.id,
                    event="operator.area_access_granted",
                    details={
                        "operator": args.operator,
                        "level": args.level,
                        "region_id": args.region,
                    },
                )
            )
        elif args.command == "grant-membership":
            if not db.get(Organization, args.organization):
                raise ValueError("Organization not found")
            user = db.scalar(select(User).where(User.email == args.email.lower()))
            if not user:
                password = getpass.getpass("New user secure password (min 12 characters): ")
                if len(password) < 12:
                    raise ValueError("Password is too short")
                user = User(
                    email=args.email.lower(),
                    name=args.name,
                    password_hash=passwords.hash(password),
                )
                db.add(user)
                db.flush()
            existing = db.scalar(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.organization_id == args.organization,
                )
            )
            if existing:
                raise ValueError(
                    "Membership already exists; review any privilege change explicitly"
                )
            if args.role in {
                "Facility In-Charge",
                "Midwife/ANC Staff",
                "Community Health Nurse",
                "School Health/GIFTS Officer",
                "Field/CHPS Worker",
            }:
                raise ValueError(
                    "Facility/community roles must use scoped district UI provisioning"
                )
            db.add(Membership(user_id=user.id, organization_id=args.organization, role=args.role))
            db.add(
                Audit(
                    organization_id=args.organization,
                    event="operator.membership_granted",
                    entity_id=user.id,
                    details={"operator": args.operator, "role": args.role},
                )
            )
        else:
            if db.scalar(select(Programme).where(Programme.code == args.code)):
                raise ValueError("Programme code already exists")
            db.add(Programme(code=args.code, name=args.name))
            db.add(
                Audit(
                    event="operator.programme_created",
                    details={"operator": args.operator, "code": args.code},
                )
            )
        db.commit()
        print("Operation completed and audited")


if __name__ == "__main__":
    main()
