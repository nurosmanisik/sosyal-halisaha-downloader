#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
SPEC_FILE="${ROOT_DIR}/packaging/macos/sosyal-halisaha-downloader.spec"
APP_PATH="${ROOT_DIR}/dist/Sosyal Hali Saha Downloader.app"
PYINSTALLER_CONFIG_DIR="${ROOT_DIR}/.pyinstaller"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Hata: macOS .app sadece macOS uzerinde paketlenebilir." >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Hata: .venv bulunamadi. Once python3 -m venv .venv calistirin." >&2
  exit 1
fi

if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import PyInstaller
import webview
PY
then
  echo "Desktop paketleme bagimlilikleri eksik. Calistirin:" >&2
  echo ".venv/bin/python -m pip install -r requirements-desktop.txt" >&2
  exit 1
fi

cd "${ROOT_DIR}"
export PYINSTALLER_CONFIG_DIR
mkdir -p "${PYINSTALLER_CONFIG_DIR}"

"${PYTHON_BIN}" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "${ROOT_DIR}/dist" \
  --workpath "${ROOT_DIR}/build" \
  "${SPEC_FILE}"

if command -v xattr >/dev/null 2>&1; then
  xattr -cr "${APP_PATH}" || true
  while IFS= read -r item; do
    xattr -d com.apple.FinderInfo "${item}" 2>/dev/null || true
    xattr -d com.apple.ResourceFork "${item}" 2>/dev/null || true
  done < <(find "${APP_PATH}" -print)
fi

if command -v dot_clean >/dev/null 2>&1; then
  dot_clean -m "${APP_PATH}" || true
fi

if command -v codesign >/dev/null 2>&1; then
  if ! codesign --force --deep --sign - "${APP_PATH}" >/dev/null 2>&1; then
    echo "Uyari: macOS imzasi tamamlanamadi; uygulama yine de local calisabilir." >&2
    echo "Sebep genelde Desktop/iCloud file-provider metadata'sidir." >&2
  fi
fi

echo "Olusturuldu: ${APP_PATH}"
echo "Cift tiklayarak native Mac uygulamasi gibi acabilirsiniz."
