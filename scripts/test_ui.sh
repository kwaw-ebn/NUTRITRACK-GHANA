#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "$0")/.." && pwd)
python "$project_root/scripts/init_ui_test.py"
cd "$project_root/backend"
DATABASE_URL=sqlite:////tmp/nutritrack-ui-test.db SETUP_TOKEN=ui-test-onboarding-token-1234567890 ENVIRONMENT=development python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 > /tmp/nutritrack-ui-api.log 2>&1 &
ui_api_pid=$!
trap 'kill "$ui_api_pid" 2>/dev/null || true' EXIT
for attempt in $(seq 1 20); do
  if curl --fail --silent http://127.0.0.1:8001/health >/dev/null; then break; fi
  sleep 0.5
done
cd "$project_root/frontend"
npm run test
