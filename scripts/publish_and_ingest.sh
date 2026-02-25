#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PROD_URL="${PROD_URL:-https://trump-tracking-app-production.up.railway.app}"
WAIT_SECONDS="${WAIT_SECONDS:-10}"
MAX_WAIT_ATTEMPTS="${MAX_WAIT_ATTEMPTS:-30}"
SKIP_PUSH="${SKIP_PUSH:-0}"
DATES_INPUT="${DATES:-}"
DRY_RUN="${DRY_RUN:-0}"

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Required command not found: ${cmd}" >&2
    exit 1
  fi
}

parse_dates_input() {
  if [[ -z "${DATES_INPUT}" ]]; then
    return 0
  fi

  echo "${DATES_INPUT}" \
    | tr ',' '\n' \
    | tr ' ' '\n' \
    | sed '/^$/d'
}

collect_changed_jsonl_dates() {
  local file_list
  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    file_list="$(git diff --name-only origin/main...HEAD)"
  else
    file_list="$(git show --name-only --pretty='' HEAD)"
  fi

  echo "${file_list}" \
    | sed -nE 's#^data/inbox/current/([0-9]{4}-[0-9]{2}-[0-9]{2})\.jsonl$#\1#p'
}

validate_dates() {
  local invalid=0
  while IFS= read -r d; do
    [[ -z "${d}" ]] && continue
    if [[ ! "${d}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
      echo "Invalid date token: ${d}" >&2
      invalid=1
    fi
  done
  return "${invalid}"
}

wait_for_remote_file() {
  local day="$1"
  local remote_file="/app/data/inbox/current/${day}.jsonl"
  local attempt

  for attempt in $(seq 1 "${MAX_WAIT_ATTEMPTS}"); do
    if railway ssh sh -lc "test -f ${remote_file}" >/dev/null 2>&1; then
      return 0
    fi
    echo "Waiting for deploy to expose ${remote_file} (${attempt}/${MAX_WAIT_ATTEMPTS})..."
    sleep "${WAIT_SECONDS}"
  done

  echo "Timed out waiting for ${remote_file} in Railway container." >&2
  return 1
}

require_cmd git
require_cmd railway
require_cmd curl

if [[ "${SKIP_PUSH}" != "1" && "${DRY_RUN}" != "1" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Working tree has uncommitted changes. Commit them before running publish." >&2
    exit 1
  fi
fi

manual_dates="$(parse_dates_input || true)"
if [[ -n "${manual_dates}" ]]; then
  date_lines="${manual_dates}"
else
  date_lines="$(collect_changed_jsonl_dates || true)"
fi

if [[ -n "${date_lines}" ]] && ! validate_dates <<< "${date_lines}"; then
  exit 1
fi

changed_dates="$(echo "${date_lines}" | sed '/^$/d' | sort -u || true)"

if [[ "${SKIP_PUSH}" != "1" && "${DRY_RUN}" != "1" ]]; then
  echo "Pushing current HEAD to origin/main..."
  git push origin HEAD:main
else
  echo "Skipping git push (SKIP_PUSH=${SKIP_PUSH}, DRY_RUN=${DRY_RUN})."
fi

if [[ -z "${changed_dates}" ]]; then
  echo "No changed daily JSONL files detected for ingestion."
  echo "Publish step complete."
  exit 0
fi

echo "Dates queued for Railway ingestion:"
echo "${changed_dates}" | sed 's/^/  - /'

while IFS= read -r day; do
  [[ -z "${day}" ]] && continue

  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[DRY RUN] Would wait for /app/data/inbox/current/${day}.jsonl and ingest ${day}."
    continue
  fi

  wait_for_remote_file "${day}"
  echo "Ingesting ${day} in Railway..."
  railway ssh sh -lc "cd /app && PYTHONPATH=/app python3 -m backend.scripts.daily_pipeline --mode current --date ${day}"
done <<< "${changed_dates}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[DRY RUN] Skipping production health check."
  echo "Publish + ingest pipeline complete."
  exit 0
fi

health_body="$(mktemp)"
trap 'rm -f "${health_body}"' EXIT
status_code="$(curl -sS -o "${health_body}" -w "%{http_code}" "${PROD_URL}/health" || true)"
if [[ "${status_code}" == "200" ]]; then
  echo "Production health check OK at ${PROD_URL}/health"
else
  echo "Warning: production health check returned HTTP ${status_code} at ${PROD_URL}/health" >&2
fi

echo "Publish + ingest pipeline complete."
