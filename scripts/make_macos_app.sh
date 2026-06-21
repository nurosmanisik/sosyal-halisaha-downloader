#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Sosyal Hali Saha Downloader"
APP_PATH="${ROOT_DIR}/${APP_NAME}.app"
CONTENTS_DIR="${APP_PATH}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
EXECUTABLE="${MACOS_DIR}/launcher"
RUN_SCRIPT="${ROOT_DIR}/scripts/run_web.sh"
SOURCE_FILE="${MACOS_DIR}/launcher.c"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Hata: Bu script sadece macOS uzerinde .app olusturur." >&2
  exit 1
fi

if [[ ! -f "${RUN_SCRIPT}" ]]; then
  echo "Hata: ${RUN_SCRIPT} bulunamadi." >&2
  exit 1
fi

if ! command -v clang >/dev/null 2>&1; then
  echo "Hata: clang bulunamadi. Xcode Command Line Tools kurulu olmali." >&2
  exit 1
fi

chmod +x "${ROOT_DIR}/scripts/run_web.sh" "${ROOT_DIR}/scripts/stop_web.sh"
rm -rf "${APP_PATH}"
mkdir -p "${MACOS_DIR}"

cat >"${CONTENTS_DIR}/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>tr</string>
  <key>CFBundleDisplayName</key>
  <string>Sosyal Hali Saha Downloader</string>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>com.local.sosyal-halisaha-downloader</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Sosyal Hali Saha Downloader</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.15</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

printf 'APPL????' >"${CONTENTS_DIR}/PkgInfo"

cat >"${SOURCE_FILE}" <<LAUNCHER
#include <unistd.h>

int main(void) {
  execl("/bin/bash", "bash", "${RUN_SCRIPT}", (char *)0);
  return 1;
}
LAUNCHER

clang "${SOURCE_FILE}" -o "${EXECUTABLE}"
rm -f "${SOURCE_FILE}"
chmod +x "${EXECUTABLE}"
touch "${APP_PATH}"

echo "Olusturuldu: ${APP_PATH}"
echo "Cift tiklayarak acabilirsiniz."
