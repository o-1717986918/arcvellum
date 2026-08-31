#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:?usage: build_desktop_macos.sh <aarch64-apple-darwin|x86_64-apple-darwin>}"
case "$TARGET" in
  aarch64-apple-darwin) PI_TARGET="macos-arm64" ;;
  x86_64-apple-darwin) PI_TARGET="macos-x64" ;;
  *) echo "unsupported macOS target: $TARGET" >&2; exit 2 ;;
esac

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
TAURI_ROOT="$ROOT/desktop/src-tauri"
BINARY_DIR="$TAURI_ROOT/binaries"
RESOURCE_DIR="$TAURI_ROOT/resources"
SIDECAR_SOURCE="$ROOT/dist/literary-engineering-studio-sidecar"
SIDECAR_TARGET="$BINARY_DIR/literary-engineering-studio-sidecar-$TARGET"
PROVENANCE="$ROOT/build/sidecar-provenance-$TARGET.json"
PI_RESOURCE="$RESOURCE_DIR/pi-worker"

cd "$ROOT"
python scripts/verify_version_sync.py
npm run client:build
npm run pi-worker:check
python -m PyInstaller --noconfirm --clean packaging/studio_sidecar.spec
mkdir -p "$BINARY_DIR" "$RESOURCE_DIR"
cp -f "$SIDECAR_SOURCE" "$SIDECAR_TARGET"
chmod +x "$SIDECAR_TARGET"
python packaging/sidecar_provenance.py write \
  --root "$ROOT" --binary "$SIDECAR_TARGET" --manifest "$PROVENANCE"
python packaging/pi_worker_bundle.py stage \
  --root "$ROOT" --destination "$PI_RESOURCE" \
  --cache-root "$ROOT/build/vendor/node-v22.19.0" --target "$PI_TARGET"
python packaging/demo_project_bundle.py \
  --directory "$RESOURCE_DIR/demo-projects" \
  --require-work-id yu-hua-i-am-timid-as-a-mouse
python packaging/sidecar_provenance.py verify \
  --root "$ROOT" --binary "$SIDECAR_TARGET" --manifest "$PROVENANCE"
python packaging/pi_worker_bundle.py verify \
  --root "$ROOT" --destination "$PI_RESOURCE"

rustup target add "$TARGET"
CONFIG_OVERRIDE='{"bundle":{"createUpdaterArtifacts":false}}'
npx tauri build --target "$TARGET" --bundles app,dmg --config "$CONFIG_OVERRIDE"

mkdir -p "$ROOT/dist/release"
DMG_SOURCE="$(find "$TAURI_ROOT/target/$TARGET/release/bundle/dmg" -maxdepth 1 -type f -name '*.dmg' -print -quit)"
if [[ -z "$DMG_SOURCE" ]]; then
  echo "macOS DMG was not produced for $TARGET" >&2
  exit 1
fi
VERSION="$(PYTHONPATH=src python -c 'from literary_engineering_studio import __version__; print(__version__)')"
cp -f "$DMG_SOURCE" "$ROOT/dist/release/ArcVellum_${VERSION}_${PI_TARGET}_unsigned-preview.dmg"
