"""Reproduce the seed from retrieved government classification tables.

Input text contains public-government table extracts, not a hand-authored MMDA list.
Only the first matching source document is parsed. Assembly types come from the
explicit classification column. Source serial numbers are NOT official codes.
"""

import csv, json, re, uuid
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend/data"


def parse(path, assembly_type):
    text = path.read_text().split(
        "\n--------------------------------------------------------------------------------"
    )[0]
    rows = []
    for line in text.splitlines():
        if not re.match(r"^\d+\s+\|", line):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 5 and cells[4] == assembly_type:
            rows.append(
                {
                    "source_serial": cells[0],
                    "region": cells[1].title(),
                    "source_name": cells[2],
                    "capital": cells[3],
                    "assembly_type": assembly_type,
                }
            )
    return rows


rows = (
    parse(DATA / "source_districts_retrieved.txt", "DISTRICT")
    + parse(DATA / "source_municipalities.txt", "MUNICIPAL")
    + parse(DATA / "source_metropolitans.txt", "METROPOLITAN")
)
assert len(rows) == 261, len(rows)
assert len({r["source_serial"] for r in rows}) == 261
sourceurls = {
    "DISTRICT": "https://imccod.gov.gh/districts/",
    "MUNICIPAL": "https://imccod.gov.gh/municipalities/",
    "METROPOLITAN": "https://imccod.gov.gh/metropolitans/",
}
corrections = {
    r["source_serial"]: r for r in json.loads((DATA / "geography_corrections.json").read_text())
}
fields = [
    "uuid",
    "name",
    "region",
    "assembly_type",
    "administrative_code",
    "capital",
    "active",
    "effective_from",
    "effective_to",
    "source",
    "version",
    "source_serial",
    "source_name",
]
with (DATA / "ghana_mmdas.csv").open("w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for r in sorted(rows, key=lambda r: int(r["source_serial"])):
        name = (
            re.sub(r"\s+(DISTRICT|MUNICIPAL|MUNICPAL|METROPOLITAN)$", "", r["source_name"]).title()
            + " "
            + r["assembly_type"].title()
        )
        correction = corrections.get(r["source_serial"], {})
        writer.writerow(
            {
                **r,
                **{k: v for k, v in correction.items() if k in {"name", "assembly_type"}},
                "uuid": str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL, "https://imccod.gov.gh/mmdas/" + r["source_serial"]
                    )
                ),
                "name": correction.get("name", name),
                "administrative_code": "",
                "active": "true",
                "effective_from": "",
                "effective_to": "",
                "source": correction.get("source", sourceurls[r["assembly_type"]]),
                "version": "government-snapshot-2026-10-03-v1",
            }
        )
region_names = sorted({r["region"] for r in rows})
assert len(region_names) == 16
with (DATA / "ghana_regions.csv").open("w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=["region_code", "name", "capital", "source", "version"],
        lineterminator="\n",
    )
    writer.writeheader()
    for region in region_names:
        writer.writerow(
            {
                "region_code": "GH-" + region.upper().replace(" ", "-"),
                "name": region,
                "capital": "",
                "source": "https://imccod.gov.gh/mmdas/",
                "version": "government-snapshot-2026-10-03-v1",
            }
        )
manifest = {
    "version": "government-snapshot-2026-10-03-v1",
    "retrieved_at": "2026-10-03",
    "source_publication_date": None,
    "expected_count": 261,
    "sources": list(sourceurls.values()) + [c["source"] for c in corrections.values()],
    "counts_by_region": dict(sorted(Counter(r["region"] for r in rows).items())),
    "assembly_types": dict(
        Counter(
            corrections.get(r["source_serial"], {}).get("assembly_type", r["assembly_type"])
            for r in rows
        )
    ),
    "status": "Government source snapshot; requires competent-authority review before production. Source publication/effective dates are not supplied. Some classifications conflict with other government pages. See docs/MASTER_DATA.md.",
    "administrative_codes": "Unavailable; source serial numbers and internal region codes are not official administrative codes.",
}
(DATA / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
