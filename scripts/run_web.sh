#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_URL="http://127.0.0.1:5000"
TOOLS_URL="${APP_URL}/api/tools"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
LOG_DIR="${ROOT_DIR}/.launcher"
LOG_FILE="${LOG_DIR}/web.log"
PID_FILE="${LOG_DIR}/web.pid"

mkdir -p "${LOG_DIR}"

fail() {
  osascript -e "display alert \"Sosyal Hali Saha Downloader\" message \"$1\" as critical" >/dev/null 2>&1 || true
  echo "Hata: $1" >&2
  exit 1
}

is_healthy() {
  curl -fsS --max-time 2 "${TOOLS_URL}" >/dev/null 2>&1
}

if is_healthy; then
  open "${APP_URL}"
  exit 0
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  fail ".venv bulunamadi. Terminalde su komutlari calistirin: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import flask
import requests
PY
then
  fail "Python paketleri eksik. Terminalde calistirin: .venv/bin/python -m pip install -r requirements.txt"
fi

cd "${ROOT_DIR}"
nohup "${PYTHON_BIN}" app.py >>"${LOG_FILE}" 2>&1 &
echo "$!" >"${PID_FILE}"

for _ in {1..40}; do
  if is_healthy; then
    open "${APP_URL}"
    exit 0
  fi
  sleep 0.25
done

fail "Lokal server baslatilamadi. 5000 portu dolu olabilir. Log dosyasi: ${LOG_FILE}"
