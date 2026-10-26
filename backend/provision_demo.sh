#!/usr/bin/env bash
# Provisions a small set of ready-to-use demo accounts against a running
# EUFAMA Connect backend — for showing someone a beta, not for real
# rollout (see README "Quick demo setup").
#
# Usage:
#   ADMIN_API_KEY=... BASE_URL=http://<lan-ip>:8765 ./provision_demo.sh
#
# Prints each account's worker_id + token — save these, they're shown
# once. Paste worker_id + token into the app's login screen (configure
# the server IP/port first via the hidden admin screen: tap the EUFAMA
# logo 5x on the login screen).

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8765}"
ADMIN_API_KEY="${ADMIN_API_KEY:?Set ADMIN_API_KEY to the value your backend was started with}"

create_account() {
  local worker_id="$1" display_name="$2" role="$3"
  echo "── ${display_name} (${role}) ──────────────────────────"
  curl -sS -X POST "${BASE_URL}/admin/users" \
    -H "X-Admin-Key: ${ADMIN_API_KEY}" -H "Content-Type: application/json" \
    -d "{\"worker_id\": \"${worker_id}\", \"display_name\": \"${display_name}\", \"role\": \"${role}\"}" \
    | python3 -m json.tool
  echo
}

create_account "valy"   "Valy (Dispecer)"     "vip"
create_account "ion1"   "Ion Popescu"         "worker"
create_account "maria1" "Maria Ionescu"       "worker"

echo "Done. Log in to the app with each worker_id + the token shown above."
