import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SETUP_TOKEN"] = "test-setup-token-that-is-at-least-32-long"
from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import *
from app.seed import run
from app.security import passwords


@pytest.fixture()
def client():
    from app.security import _attempts

    _attempts.clear()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    run()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def setup(c, name, email):
    r = c.get("/api/geography/regions").json()
    central = next(x for x in r if x["name"] == "Central")
    districts = c.get("/api/geography/districts", params={"region_id": central["id"]}).json()
    district = next(d for d in districts if d["name"] == "Agona East District")
    res = c.post(
        "/api/setup",
        headers={"X-Setup-Token": os.environ["SETUP_TOKEN"]},
        json={
            "name": name,
            "organization_type": "District Health Directorate",
            "region_id": central["id"],
            "district_id": district["id"],
            "subdistricts": [{"name": "Test subdistrict"}],
            "facilities": [
                {
                    "name": "Test facility",
                    "facility_type": "CHPS",
                    "subdistrict_id": "Test subdistrict",
                }
            ],
            "admin_name": "Test Administrator",
            "admin_email": email,
            "password": "StrongPassword123!",
            "programmes": ["growth", "maternal", "gifts"],
        },
    )
    assert res.status_code == 201, res.text
    h = {"Authorization": "Bearer " + res.json()["access_token"]}
    me = c.get("/api/auth/me", headers=h).json()
    h["X-Organization-ID"] = me["memberships"][0]["organization_id"]
    structure = c.get("/api/structure", headers=h).json()
    return h, structure, res.json()


def test_geography_and_setup_validation(client):
    regions = client.get("/api/geography/regions").json()
    assert len(regions) == 16
    ids = []
    for r in regions:
        districts = client.get("/api/geography/districts", params={"region_id": r["id"]}).json()
        assert all(d["region_id"] == r["id"] for d in districts)
        ids.extend(d["id"] for d in districts)
    assert len(set(ids)) == 261
    with SessionLocal() as db:
        assert (
            db.scalar(select(District).where(District.name == "Assin North District")).assembly_type
            == "DISTRICT"
        )
        assert (
            db.scalar(
                select(District).where(District.name == "West Mamprusi Municipal")
            ).assembly_type
            == "MUNICIPAL"
        )
    assert client.post("/api/setup", json={}).status_code == 422
    h, s, t = setup(client, "Test Directorate", "admin@example.org")
    assert len(s["facilities"]) == 1
    assert client.get("/api/clients", headers=h).json() == []


def test_tenant_scope_and_role_denials(client):
    h, s, _ = setup(client, "District A", "a@example.org")
    h2, s2, _ = setup(client, "District B", "b@example.org")
    facility_id = s["facilities"][0]["id"]
    row = client.post(
        "/api/clients",
        headers=h,
        json={
            "name": "Fictional Child",
            "reference": "DEMO-1",
            "date_of_birth": "2024-01-01",
            "sex": "Female",
            "facility_id": facility_id,
        },
    )
    assert row.status_code == 201
    assert client.get("/api/clients", headers=h2).json() == []
    assert (
        client.post(
            "/api/encounters",
            headers=h2,
            json={
                "client_id": row.json()["id"],
                "programme": "growth",
                "visit_date": str(date.today()),
                "assessment": "Fictional assessment",
            },
        ).status_code
        == 404
    )
    spoof = {**h, "X-Organization-ID": h2["X-Organization-ID"]}
    assert client.get("/api/clients", headers=spoof).status_code == 403
    viewer = client.post(
        "/api/users",
        headers=h,
        json={
            "name": "Viewer",
            "email": "viewer@example.org",
            "password": "StrongPassword123!",
            "role": "Viewer",
        },
    )
    assert viewer.status_code == 201
    login = client.post(
        "/api/auth/login", json={"email": "viewer@example.org", "password": "StrongPassword123!"}
    ).json()
    vh = {**h, "Authorization": "Bearer " + login["access_token"]}
    assert client.get("/api/clients", headers=vh).status_code == 403
    assert client.get("/api/actions", headers=vh).status_code == 403
    assert client.get("/api/dashboard", headers=vh).status_code == 200
    assert (
        client.post(
            "/api/facilities",
            headers=vh,
            json={
                "name": "Blocked facility",
                "facility_type": "CHPS",
                "subdistrict_id": s["subdistricts"][0]["id"],
            },
        ).status_code
        == 403
    )


def test_encounter_followup_and_validation(client):
    h, s, _ = setup(client, "District A", "a@example.org")
    c = client.post(
        "/api/clients",
        headers=h,
        json={
            "name": "Fictional Child",
            "reference": "DEMO-1",
            "date_of_birth": "2024-01-01",
            "sex": "Female",
            "facility_id": s["facilities"][0]["id"],
        },
    ).json()
    data = {
        "client_id": c["id"],
        "programme": "growth",
        "visit_date": str(date.today()),
        "assessment": "Follow-up required",
        "followup_date": str(date.today()),
        "risk": "High",
        "measurements": {"weight_kg": 10.2},
    }
    res = client.post("/api/encounters", headers=h, json=data)
    assert res.status_code == 201, res.text
    actions = client.get("/api/actions", headers=h).json()
    assert len(actions) == 1
    assert actions[0]["client_id"] == c["id"]
    assert (
        client.patch(
            "/api/actions/" + actions[0]["id"], headers=h, json={"status": "Completed"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/actions/" + actions[0]["id"],
            headers=h,
            json={"status": "Completed", "outcome": "Review completed"},
        ).status_code
        == 200
    )
    data["measurements"] = {"weight_kg": -5}
    assert client.post("/api/encounters", headers=h, json=data).status_code == 422


def test_report_lock_amendment_and_denominator(client):
    h, s, _ = setup(client, "District A", "a@example.org")
    i = client.post(
        "/api/indicators",
        headers=h,
        json={
            "name": "Test service coverage",
            "programme": "growth",
            "definition": "Fictional test indicator",
            "numerator_definition": "Clients served",
            "denominator_definition": "Eligible clients",
            "target": 90,
            "approval_reference": "TEST ONLY",
        },
    ).json()
    data = {
        "facility_id": s["facilities"][0]["id"],
        "period": "2026-09",
        "values": [{"indicator_id": i["id"], "numerator": 60, "denominator": 100}],
    }
    report = client.post("/api/reports", headers=h, json=data)
    assert report.status_code == 201, report.text
    id = report.json()["id"]
    assert client.get("/api/dashboard", headers=h).json()["indicators"] == []
    assert (
        client.post(
            f"/api/reports/{id}/transition", headers=h, json={"state": "Locked"}
        ).status_code
        == 409
    )
    for state in ["Submitted", "Verified", "Approved", "Locked"]:
        assert (
            client.post(
                f"/api/reports/{id}/transition", headers=h, json={"state": state}
            ).status_code
            == 200
        )
    assert client.put(f"/api/reports/{id}", headers=h, json=data).status_code == 409
    dashboard = client.get("/api/dashboard", headers=h).json()
    assert dashboard["indicators"][0]["value"] == 60
    assert len(dashboard["signals"]) == 1
    amendment = client.post(
        f"/api/reports/{id}/amend", headers=h, json={"reason": "Correct a documented entry error"}
    )
    assert amendment.status_code == 200
    assert amendment.json()["revision"] == 2
    audit = client.get("/api/admin/audit", headers=h).json()
    assert any(
        a["event"] == "report.amended" and a["details"]["previous_values"][0]["numerator"] == 60
        for a in audit
    )
    data["values"][0]["numerator"] = 101
    assert client.put(f"/api/reports/{id}", headers=h, json=data).status_code == 422


def test_refresh_rotation_logout_and_setup_token(client):
    h, s, t = setup(client, "District A", "a@example.org")
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert refreshed.status_code == 200
    assert (
        client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code
        == 401
    )
    assert client.get("/api/auth/me", headers=h).status_code == 401
    h["Authorization"] = "Bearer " + refreshed.json()["access_token"]
    assert (
        client.post(
            "/api/auth/logout", headers=h, json={"refresh_token": refreshed.json()["refresh_token"]}
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_import_atomic_and_commodity_balance(client):
    h, s, _ = setup(client, "District A", "a@example.org")
    payload = b"facility_name,facility_type,subdistrict\nNew clinic,CHPS,Test subdistrict\nInvalid,CHPS,Missing\n"
    res = client.post(
        "/api/facilities/import/validate",
        headers=h,
        files={"file": ("test.csv", payload, "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["valid"] == 1
    assert res.json()["invalid"] == 1
    facility = s["facilities"][0]["id"]
    res = client.post(
        "/api/registers/commodities",
        headers=h,
        json={
            "title": "Test commodity",
            "facility_id": facility,
            "details": {"period": "2026-09", "opening": 10, "received": 5, "used": 20},
        },
    )
    assert res.status_code == 422
    res = client.post(
        "/api/registers/commodities",
        headers=h,
        json={
            "title": "Test commodity",
            "facility_id": facility,
            "details": {"period": "2026-09", "opening": 10, "received": 5, "used": 7},
        },
    )
    assert res.status_code == 201
    assert res.json()["details"]["closing"] == 8


def test_facility_scope_programme_reads_and_technical_role(client):
    h, s, _ = setup(client, "District A", "a@example.org")
    first = s["facilities"][0]["id"]
    second = client.post(
        "/api/facilities",
        headers=h,
        json={
            "name": "Second test clinic",
            "facility_type": "CHPS",
            "subdistrict_id": s["subdistricts"][0]["id"],
        },
    ).json()["id"]
    client1 = client.post(
        "/api/clients",
        headers=h,
        json={
            "name": "Fictional First",
            "reference": "DEMO-1",
            "date_of_birth": "2024-01-01",
            "sex": "Female",
            "facility_id": first,
        },
    ).json()
    client2 = client.post(
        "/api/clients",
        headers=h,
        json={
            "name": "Fictional Second",
            "reference": "DEMO-2",
            "date_of_birth": "2024-01-01",
            "sex": "Female",
            "facility_id": second,
        },
    ).json()
    for programme in ["growth", "maternal"]:
        assert (
            client.post(
                "/api/encounters",
                headers=h,
                json={
                    "client_id": client1["id"],
                    "programme": programme,
                    "visit_date": str(date.today()),
                    "assessment": "Fictional service",
                },
            ).status_code
            == 201
        )
    assert (
        client.post(
            "/api/users",
            headers=h,
            json={
                "name": "Test nurse",
                "email": "nurse@example.org",
                "password": "StrongPassword123!",
                "role": "Community Health Nurse",
                "facility_id": first,
            },
        ).status_code
        == 201
    )
    t = client.post(
        "/api/auth/login", json={"email": "nurse@example.org", "password": "StrongPassword123!"}
    ).json()
    nh = {**h, "Authorization": "Bearer " + t["access_token"]}
    assert len(client.get("/api/clients", headers=nh).json()) == 1
    assert (
        client.get("/api/encounters", headers=nh, params={"client_id": client2["id"]}).status_code
        == 404
    )
    assert {r["programme"] for r in client.get("/api/encounters", headers=nh).json()} == {"growth"}
    with SessionLocal() as db:
        user = User(
            name="Technical operator",
            email="operator@example.org",
            password_hash=passwords.hash("StrongPassword123!"),
        )
        db.add(user)
        db.flush()
        db.add(
            Membership(
                user_id=user.id, organization_id=h["X-Organization-ID"], role="System Administrator"
            )
        )
        db.commit()
    t = client.post(
        "/api/auth/login", json={"email": "operator@example.org", "password": "StrongPassword123!"}
    ).json()
    sh = {**h, "Authorization": "Bearer " + t["access_token"]}
    assert client.get("/api/admin/health", headers=sh).status_code == 200
    assert client.get("/api/clients", headers=sh).status_code == 403
    assert client.get("/api/dashboard", headers=sh).status_code == 403


def test_aggregate_memberships_and_configurable_quality(client):
    h, s, _ = setup(client, "District A", "a@example.org")
    h2, s2, _ = setup(client, "District B", "b@example.org")
    with SessionLocal() as db:
        user = User(
            name="Regional reader",
            email="regional@example.org",
            password_hash=passwords.hash("StrongPassword123!"),
        )
        db.add(user)
        db.flush()
        db.add(
            Membership(
                user_id=user.id,
                organization_id=h["X-Organization-ID"],
                role="Regional Nutrition Officer",
            )
        )
        db.commit()
    t = client.post(
        "/api/auth/login", json={"email": "regional@example.org", "password": "StrongPassword123!"}
    ).json()
    rh = {**h, "Authorization": "Bearer " + t["access_token"]}
    aggregate = client.get("/api/aggregate/dashboard", headers=rh).json()
    assert len(aggregate["organizations"]) == 1
    assert aggregate["organizations"][0]["organization_id"] == h["X-Organization-ID"]
    assert client.get("/api/clients", headers=rh).status_code == 403
    assert client.get("/api/dashboard", headers=rh).json()["actions"] == []
    config = {
        "programmes": ["growth"],
        "facility_types": ["CHPS"],
        "report_header": "Test",
        "contact": "",
        "quality_weights": {"Completeness": 2, "Timeliness": 4, "Validity": 1},
        "report_deadline_day": 10,
    }
    assert client.put("/api/configuration", headers=h, json=config).status_code == 200
    config["quality_weights"] = {"Completeness": 0, "Timeliness": 0, "Validity": 0}
    assert client.put("/api/configuration", headers=h, json=config).status_code == 422


def test_reset_revokes_sessions_and_auth_limiter(client):
    from app.security import digest, utc
    from datetime import timedelta

    h, s, _ = setup(client, "District A", "a@example.org")
    user_id = client.get("/api/auth/me", headers=h).json()["user"]["id"]
    with SessionLocal() as db:
        db.add(
            PasswordReset(
                user_id=user_id,
                token_hash=digest("fictional-reset-token-long-enough"),
                expires_at=utc() + timedelta(minutes=30),
            )
        )
        db.commit()
    assert (
        client.post(
            "/api/auth/password-reset/complete",
            json={"token": "fictional-reset-token-long-enough", "password": "ChangedPassword123!"},
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert (
        client.post(
            "/api/auth/password-reset/complete",
            json={"token": "fictional-reset-token-long-enough", "password": "ChangedPassword123!"},
        ).status_code
        == 400
    )
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login", json={"email": "missing@example.org", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"email": "missing@example.org", "password": "wrong"}
        ).status_code
        == 429
    )
