# NutriTrack Ghana

**District Nutrition Intelligence & Follow-up System**
**From Nutrition Data to Action.**

A configurable nutrition programme workspace connecting **Data → Signal → Action → Follow-up → Outcome → Data**. Built for a district pilot with organization, facility and community authorization, and an extensible multi-district architecture.

**Release status: working pilot foundation, not yet production-approved for identifiable health data.** See [implementation matrix](docs/REQUIREMENTS.md) for specific working features, limitations and release gates. No official Ghana Health Service endorsement is implied.

## What works

- Organization setup with 16 regions, typed health districts, sub-districts, facilities and communities. Assembly districts are excluded from operational setup; the historical directory is retained separately.
- Secure sign-in, refresh rotation, password reset backend, role/organization/facility/community scope and audited changes.
- Facility management and validated CSV/XLSX import/export; client registration, measurements, assessment and encounter history.
- Scheduled encounters create follow-up actions. Staff can also create programme/supervision actions, assign responsibility, track deadlines and record outcomes.
- Locally approved indicator registry; monthly report submission, correction, verification, approval, locking and authorized amendments.
- Approved-report trends, target exception signals, explainable facility quality components, facility maps without patient locations.
- Supervision, intervention, school and nutrition commodity registers; organization configuration, audit log, system status and changelog.

## Release 0.2.0

The main administrator can manage organizations, staff assignments, national/regional access, programme templates, shared indicator standards, master data and system status. Owner oversight is aggregate; clinical access requires an explicit assignment. New staff receive a single-use invitation link for secure manual delivery; existing passwords remain unchanged.

This release adds versioned programme capture, comparable approved-report intelligence, reporting completeness with explicit denominators, deterioration signals and duplicate-safe linked actions. Supervision supports scheduling, checklists, comparison and encrypted evidence. Reports export to PDF/XLSX directly or through an encrypted durable queue. Interrupted-session encounters can be encrypted on a device and synchronized with idempotent receipts.

See [requirements](docs/REQUIREMENTS.md), [deployment](docs/DEPLOYMENT.md) and [recovery](docs/RECOVERY.md). Clinical acceptance, live backup verification and production security review remain required.

## Local development

Python 3.12+ and Node.js 22+ recommended.

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SETUP_TOKEN="replace-with-a-local-onboarding-token"
python -m alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload
```

Default local database is SQLite, for development only. In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Visit `http://localhost:5173`. Vite proxies `/api` to the local API. Select **Set up your organization** and enter the configured onboarding token. No default administrator, default password or demonstration clients are seeded. Add approved indicators and facility records after setup. Only use fictional records in development/staging.

## Validation

```sh
cd backend
python -m pytest -q
cd ../frontend
npm run build
```

Tests exercise geography counts and region filtering, setup, tenant/role restrictions, follow-up creation, input validation, report locks/amendments, refresh rotation/revocation and facility import/commodity balance checks. Browser smoke tests use a separately initialized fictional test database; instructions are in [testing](docs/TESTING.md).

## Deployment and operations

- [Render and Neon setup](docs/DEPLOYMENT.md)
- [Database recovery runbook](docs/RECOVERY.md)
- [Government master-data provenance and review](docs/MASTER_DATA.md)
- [Implementation and production gates](docs/REQUIREMENTS.md)
- OpenAPI: `/docs`; health endpoint: `/health`.

Directories: `frontend/`, `backend/`, `docs/`, `scripts/`. Backend `.env.example` contains secret variable names only. Frontend environment contains only the public API origin.

The directory seed is a versioned government-source snapshot. Government pages disagree on some classifications; retrieval date is not an effective date. Verify the current gazetted names/types with a competent authority before production. No administrative code is invented. Official national directory updates use versioned imports, retaining existing historical records.

### Main administrator bootstrap
Set backend `MAIN_ADMIN_EMAIL` to the platform owner's email. On the sign-in page,
choose **Create main administrator account**, provide that email, a new password
(at least 12 characters), and the authorized `SETUP_TOKEN`. No region or district
is required. Only one platform owner can be bootstrapped; the backend enforces
the email whitelist, token and a database uniqueness constraint. The owner opens
national oversight, can optionally filter regions, and can open organization
aggregate dashboards. Confidential client records still require an explicit
clinical membership. District organization setup remains a separate workflow.
