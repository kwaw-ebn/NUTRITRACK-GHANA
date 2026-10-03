# Implementation and validation matrix

Release 0.1.0 is a working pilot foundation. It is not a completed national health information system and is not approved for real patient data. Status descriptions below distinguish working functions from extensible foundations and operational dependencies.

| Area | Implemented | Remaining validation / extension |
|---|---|---|
| Core stack | React 19, TypeScript, Tailwind, Recharts, Leaflet; FastAPI, Pydantic, SQLAlchemy, Alembic; PostgreSQL compatible; Docker | PostgreSQL/Neon integration and live Render smoke test |
| Geography | 16 regions and 261 source-derived government directory rows; region-scoped searchable MMDA selector; UUIDs, explicit assembly type, version/import/source fields | Government-source snapshot contains conflicting/older classifications; verify gazetted current official names, types and dates. See MASTER_DATA.md |
| Organization wizard | Organization, selected region, typed health district, optional Assembly reference, manually entered sub-districts/facilities, first administrator, programmes, target guidance, review and audited completion | In-wizard bulk import and target entry; both available after setup; phone-based invitations |
| Data isolation | Explicit organization memberships on every tenant record; API scope enforcement; sub-district/facility/community clinical scope; independent technical role; organization switcher | External security assessment, PostgreSQL RLS as defense in depth, large-volume pagination |
| Authentication | Argon2 passwords, short-lived JWTs, server session validation, refresh rotation, logout revocation, reset-token workflow; memory-only frontend tokens | Verify SMTP delivery; distributed rate limiting at gateway; organizational MFA/SSO; account deactivation UI |
| Roles | Twelve roles defined; clinical, district, facility, community and aggregate authorization; higher-scope provisioning via restricted operator CLI | Formal duties/access matrix approval; programme-specific clinical read and write test expansion; operator account management UI |
| National/regional | Aggregate reporting counts across assigned national or regional areas, including future organizations; explicit organization membership also supported; no cross-district client records | Standard national indicator IDs, reporting completeness denominator, small-cell suppression, comparable pooled national trends and priority ranking |
| Nutrition services | Client registration, structured measurements, staff assessment, encounter history; enabled programme registry; child/maternal/IYCF/Vitamin A/GIFTS/NCD foundation | Validated programme-specific forms/registers, WHO growth standards, service schedules, age-based eligibility and agreed Ghana clinical rules |
| Action engine | Encounter follow-up creates actions; indicator target exceptions; responsible officer, priority, due date, status and mandatory completion outcome; supervision links to action | Background deadline notifications, duplicate signal suppression, approved clinical decision rules, action reassignment UI |
| Indicators/analytics | Explicit definition, numerator/denominator, target, direction, approval reference; approved-only weighted coverage trends; missing denominators remain missing | National standardized definitions and validated denominators; longitudinal indicator deterioration rules |
| Data quality | Explainable completeness, timeliness and range/ratio validity components; unmeasured consistency/duplicate rate explicitly labeled | Detailed cross-register consistency/duplicates and cross-register validation rules |
| Facilities | Add/edit/deactivate, searchable directory, CSV/XLSX validation before atomic import, export, profile, facility coordinates on map | Full report schedule tracking and supervision history comparison |
| Master data | Local sub-districts, communities, facilities, schools, indicators, users; programme/type organization configuration; national versioned import CLI; no destructive delete endpoints | National master-data web administration, automated historical relationship snapshots, approved migration authoring for subsequent versions |
| Monthly reports | Draft/submitted/returned/verified/approved/locked state machine; editable drafts/corrections; API blocks immutable edits; authorized amendment saves previous values and revision in audit | Period locks across underlying encounter records, configurable approval chains, immutable externally retained audit sink, report PDF/XLSX output |
| Supervision | Visit date, findings/checklist text, corrective action/deadline and automatic linked action | Configurable checklist templates, evidence upload permission handling, comparison across visits and visit scheduling calendar |
| Interventions | Problem, target population, reached, responsible team, date, cost, outcome, follow-up | Registry-linked indicator/community IDs, validated costs and permissions; no unsupported causal inference |
| Commodities | Facility/item monthly opening/received/used/loss/closing/stock-out/expiry records; validated balance | Batch stock ledger, reconciliations, expiry alerts, commodity/programme catalogue; no pharmacy dispensing |
| GIFTS/schools | School register with type, community, assigned facility, eligible population and programme status | Enrollment source verification, student-level privacy and GIFTS service-specific forms |
| PWA | HTTPS-installable manifest, responsive mobile layout, static-asset-only service worker; offline connection banner | Full offline app-shell fallback, encrypted clinical offline sync and conflict resolution; no health records cached offline in this release |
| Administration | Application/database/version/migration/master-data status, sessions, failed logins, changelog, organization audit | Actual backup provider telemetry, queue/workers, sync telemetry, tenant-specific monitoring and log retention |
| Backup/recovery | Proposed owner, retention, RPO/RTO targets, encryption and restore validation runbook | Provider setup and measured restoration exercise; no backup guarantee is claimed |
| Environments | Development/staging banner; production configuration validation; seed never adds fictional or real clients | Separate managed infrastructure and production governance acceptance |

## Release gates before identifiable health data

- Clinical and data-custodian approval of programme definitions, staff role scopes, consent processes, required datasets, retention and legal/privacy obligations.
- Reconcile geography with a current authorized master directory and obtain any official codes/effective dates.
- PostgreSQL migration and tenant isolation tests against the intended managed database.
- Independent authorization/security review, distributed rate limiting, secure transport/CSP and monitoring, SMTP verification, account lifecycle controls.
- Provider backups and an actual isolated restoration exercise with measured recovery objectives.
- Field usability/UAT with fictional data, load/performance testing and reporting reconciliation against approved records.
- Add missing national standardization, reporting output and programme-specific clinical functions before claiming national deployment readiness.
