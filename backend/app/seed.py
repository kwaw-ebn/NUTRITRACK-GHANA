"""Idempotent versioned government geography import; never loads client data."""

import csv, json, argparse, uuid
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal
from .models import Region, District, Programme, MasterImport, Audit

DATA = Path(__file__).resolve().parent.parent / "data"
PROGRAMMES = [
    ("growth", "Child Growth Monitoring"),
    ("iycf", "IYCF"),
    ("vitamin-a", "Vitamin A"),
    ("maternal", "Maternal Nutrition"),
    ("gifts", "GIFTS / Adolescent Nutrition"),
    ("rehabilitation", "Nutrition Rehabilitation"),
    ("ncd", "NCD Nutrition"),
]


def stable(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://nutritrack.ghana/" + value))


def run(directory=DATA, operator="initial-seed"):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    regions = list(csv.DictReader((directory / "ghana_regions.csv").open()))
    districts = list(csv.DictReader((directory / "ghana_mmdas.csv").open()))
    if len(regions) != 16 or len(districts) != manifest["expected_count"]:
        raise ValueError("Directory count mismatch")
    if len({(d["region"], d["name"]) for d in districts}) != len(districts):
        raise ValueError("Duplicate MMDA names")
    if any(
        d["region"] not in {r["name"] for r in regions}
        or d["assembly_type"] not in {"METROPOLITAN", "MUNICIPAL", "DISTRICT"}
        for d in districts
    ):
        raise ValueError("Invalid region or assembly type")
    with SessionLocal() as db:
        region_ids = {}
        for r in regions:
            row = db.scalar(select(Region).where(Region.region_code == r["region_code"]))
            if not row:
                row = Region(
                    id=stable("region/" + r["region_code"]),
                    name=r["name"],
                    region_code=r["region_code"],
                )
                db.add(row)
            row.capital = r.get("capital")
            region_ids[r["name"]] = row.id
        db.flush()
        for d in districts:
            row = db.get(District, d["uuid"])
            if not row:
                row = District(id=d["uuid"], name=d["name"], region_id=region_ids[d["region"]])
                db.add(row)
            row.assembly_type = d["assembly_type"]
            row.capital = d.get("capital") or None
            row.administrative_code = d.get("administrative_code") or None
            row.active = d.get("active", "true").lower() == "true"
            row.effective_from = d.get("effective_from") or None
            row.effective_to = d.get("effective_to") or None
            row.source = d["source"]
            row.version = manifest["version"]
        for code, name in PROGRAMMES:
            if not db.scalar(select(Programme).where(Programme.code == code)):
                db.add(Programme(code=code, name=name))
        if not db.scalar(select(MasterImport).where(MasterImport.version == manifest["version"])):
            db.add(
                MasterImport(
                    source=json.dumps(manifest["sources"]),
                    source_date=manifest["retrieved_at"],
                    version=manifest["version"],
                    imported_by=operator,
                    count=len(districts),
                )
            )
            db.add(
                Audit(
                    event="master_data.imported",
                    details={
                        "operator": operator,
                        "version": manifest["version"],
                        "count": len(districts),
                    },
                )
            )
        db.commit()
    print(
        f"Imported {len(regions)} regions and {len(districts)} MMDAs; no operational or client data."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default=str(DATA))
    parser.add_argument("--operator", default="initial-seed")
    args = parser.parse_args()
    run(args.directory, args.operator)
