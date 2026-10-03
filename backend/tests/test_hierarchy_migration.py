"""Verify existing organization records survive the health hierarchy migration."""

import json
import os
import sqlite3
import subprocess
import sys


def test_existing_assembly_link_is_preserved(tmp_path):
    path = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + str(path)}

    def run(*args):
        subprocess.run([sys.executable, "-m", *args], env=env, check=True, capture_output=True)

    run("alembic", "upgrade", "0001")
    run("app.seed")
    with sqlite3.connect(path) as db:
        district, region, name = db.execute(
            "SELECT id, region_id, name FROM districts LIMIT 1"
        ).fetchone()
        db.execute(
            "INSERT INTO organizations (id,name,organization_type,region_id,district_id,configuration,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                "historical",
                "Existing directorate",
                "District Health Directorate",
                region,
                district,
                json.dumps({"programmes": ["growth"]}),
                "2026-01-01",
                "2026-01-01",
            ),
        )
    run("alembic", "upgrade", "head")
    with sqlite3.connect(path) as db:
        result = db.execute(
            "SELECT o.district_id, h.name, h.source FROM organizations o JOIN health_districts h ON h.id=o.health_district_id WHERE o.id='historical'"
        ).fetchone()
        assert result[0] == district
        assert result[1] == name
        assert "verification required" in result[2]
    run("alembic", "downgrade", "0001")
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT district_id FROM organizations WHERE id='historical'").fetchone()[0]
            == district
        )
