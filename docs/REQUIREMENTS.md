# Release 0.2.0 implementation and acceptance

This is a staging platform for district pilots and expansion. It is not clinically approved for identifiable health data or a claim of completed national deployment.

| Area | Implemented | Acceptance or remaining work |
|---|---|---|
| Hierarchy | Ghana, 16 database regions, entered health districts, sub-districts, facilities, communities; wizard imports and targets; Assembly excluded | Directorate verification of local health structures |
| Main administrator | Organization management, national overview, staff assignments, secure invitations, revocation, account status, master data and system status | Formal duties matrix and ownership transfer procedure |
| Access | API-authorized national/regional aggregates, district/sub-district/facility/community scopes, clinical least privilege | Approved small-cell disclosure policy and independent security assessment |
| Programmes | Enabled registry, versioned configurable forms, starter programme fields, historical snapshots, school-linked GIFTS | Ghana-approved clinical rules, WHO growth standards, schedules and eligibility |
| Intelligence | Comparable standard versions pooled by numerator/denominator; local indicators separate; approved-only trends, reporting completeness, target and deterioration signals, linked actions | Authoritative definitions and reporting reconciliation |
| Quality | Explainable completeness, timeliness, validity, programme consistency and normalized-reference duplicate rate; configurable weights | Cross-register validation and approved identity matching |
| Reports | Draft/submitted/returned/verified/approved/locked, optional verification policy, audited amendments, encounter period locks, PDF/XLSX, encrypted durable jobs | Official templates, external immutable audit retention, supervised job recovery |
| Supervision/registers | Scheduled visits, checklists, comparison, encrypted evidence, corrective actions; linked interventions, commodity balances, school registry | Evidence scanning/retention policy and approved commodity catalogue |
| PWA/offline | Installable shell, encrypted interrupted-session encounter queue, idempotent sync and visible failures | Full offline clinical workspace and conflict-correction interface; restart requires online sign-in/client loading |
| Security | Argon2, expiring sessions, refresh rotation, tenant validation, audit, bounded imports, encryption | Distributed rate limiting, MFA/SSO, SMTP verification, load testing |
| Hosting/recovery | Render, managed PostgreSQL, Docker, migration startup, no client seeds; encrypted dump/restore and disposable PostgreSQL CI exercise | Live automated backup setup, retention, key custody and measured live recovery; no backup guarantee |

Before identifiable data: obtain clinical and data-custodian acceptance, test reporting and mobile usability, validate consent/retention, independently assess security and exercise live recovery. No official Ghana Health Service endorsement is implied.
