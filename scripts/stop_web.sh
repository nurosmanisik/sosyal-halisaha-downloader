#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="${ROOT_DIR}/.launcher/web.pid"

pid_from_port() {
  lsof -tiTCP:5000 -sTCP:LISTEN 2>/dev/null || true
}

is_project_process() {
  local pid="$1"
  local command
  local cwd
  command="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
  cwd="$(lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)"
  [[ "${cwd}" == "${ROOT_DIR}" ]] && {
    [[ "${command}" == *" app.py"* ]] || [[ "${command}" == *"flask --app app"* ]]
  }
}

stop_pid() {
  local pid="$1"
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  if ! is_project_process "${pid}"; then
    return 0
  fi
  kill "${pid}" 2>/dev/null || true
  for _ in {1..20}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      return 0
    fi
    sleep 0.1
  done
  kill -9 "${pid}" 2>/dev/null || true
}

if [[ -f "${PID_FILE}" ]]; then
  stop_pid "$(cat "${PID_FILE}")"
  rm -f "${PID_FILE}"
fi

for pid in $(pid_from_port); do
  stop_pid "${pid}"
done

echo "Sosyal Hali Saha Downloader server durduruldu."
