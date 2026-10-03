# Validation

Backend: `cd backend && python -m pytest -q`. Tests use `test.db` with fictional clients, reset schema and rate-limiter state for each independent test, and cover authorization, geography, report workflow and refresh sessions.

Frontend build: `cd frontend && npm ci && npm run build`.

UI interaction test (DOM integration with real API, not a visual browser test): run `bash scripts/test_ui.sh` from the repository root. This starts and stops a dedicated API and resets the fictional database. Alternatively run the API manually:

```sh
python scripts/init_ui_test.py
cd backend
DATABASE_URL=sqlite:////tmp/nutritrack-ui-test.db SETUP_TOKEN=ui-test-onboarding-token-1234567890 ENVIRONMENT=development python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

In another terminal, `cd frontend && npm run test`. The test onboards a fictional organization through the setup wizard, creates/edits/deactivates facilities and checks that browser localStorage contains no tokens. It uses a separate `/tmp` database; rerun the initialization to reset it.

GitHub Actions runs backend tests, frontend build and DOM integration, plus PostgreSQL 16 migration/seed/downgrade checks. Do not call a CI job successful until its remote result is observed.

Visual browser QA could not be completed in the initial execution environment: the Chromium download returned an invalid/truncated archive. Before a field pilot, verify desktop and mobile rendering, keyboard navigation, combobox interaction, modal focus management, screen-reader semantics, chart/map rendering and PWA installation in actual supported browsers. DOM checks are not visual validation.
