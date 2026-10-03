# Government geography provenance

The seed contains exactly 16 regions and 261 unique MMDA identifiers. All regional totals reconcile to the government IMCC directory: Ahafo 6, Ashanti 43, Bono 12, Bono East 11, Central 22, Eastern 33, Greater Accra 29, North East 6, Northern 16, Oti 9, Savannah 7, Upper East 15, Upper West 11, Volta 18, Western 14, Western North 9.

Primary source: Inter-Ministerial Coordinating Committee on Decentralisation government classification tables:

- https://imccod.gov.gh/districts/
- https://imccod.gov.gh/municipalities/
- https://imccod.gov.gh/metropolitans/

`source_*.txt` retains retrieved factual classification-table extracts. `scripts/build_geography.py` reproduces the CSVs from the explicit assembly-type columns, checks the 261 unique source serials and 16 regions, and produces `manifest.json`. It does not infer assembly type from the display name. UUIDs are stable internal UUIDv5 identifiers. Source serial numbers are not administrative codes; code fields remain empty when unavailable.

Retrieval: 3 October 2026. The pages do not supply publication/effective dates. This is a **source snapshot**, not a guarantee of the latest gazetted structures. Government sources differ. Two directly verified corrections are recorded in `geography_corrections.json`, preserving the original input:

- Assin North is a District, verified by its 2026 Ministry of Finance composite budget, LGS Central directory and the district assembly website. IMCC incorrectly includes it in the municipality table.
- West Mamprusi is Municipal, verified by the Ministry of Finance North East directory. IMCC's spelling/type differs.

Other potential older classifications/spellings require reconciliation before production, including district-to-municipal upgrades. A 261-row count alone does not verify names or assembly types. Do not advertise this snapshot as a fully certified current national MMDA master registry. Do not use the education-sector contact/director placeholders as operational master data; none have been imported.

Each `District` retains source/version, active status and nullable effective dates. The import table records source list, retrieval date, version, timestamp and operator. Administrative names are not repeated as free text in programme tables; the organization stores the relevant foreign keys. Sub-districts, facilities and communities are entered by authorized local administrators, not invented nationwide.

Updates: obtain an authorized directory, assign a new manifest version and record real source/effective dates. Use the existing UUID for the same continuing entity, retain older records and mark inactive/effective_to rather than deleting them. Run `python -m app.seed --directory /approved/directory --operator CHANGE_REFERENCE` through restricted operator access. An import omitted from a new file does not delete old records. When an entity changes parent/identity, introduce a versioned historical relationship migration before changing existing foreign keys. Full historical relationship reconstruction is a remaining production requirement.

## Health-service districts

The MMDA directory describes Assemblies, not an authoritative health-service hierarchy. `health_districts` is separate, with region/name/active/source fields. Organizations reference a health district; `district_id` remains an optional Assembly reference. Registration accepts locally approved health district, sub-district and facility names. No national health district list is fabricated or derived automatically from Assembly boundaries. Migration-only provisional labels need directorate verification.
