#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Pixel Material Generator"
BUNDLE_ID="com.zane.pixel-material-generator"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MAC_DIR="$PROJECT_DIR/mac"
BUILD_DIR="$PROJECT_DIR/build/macos"
DIST_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
PYTHON_BIN="${PYTHON_BIN:-python3}"

rm -rf "$BUILD_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$DIST_DIR"

if [ ! -f "$MAC_DIR/AppIcon.icns" ]; then
  "$PYTHON_BIN" "$MAC_DIR/generate_icon.py"
fi

cp "$MAC_DIR/AppIcon.icns" "$RESOURCES_DIR/AppIcon.icns"
cp -R "$PROJECT_DIR/src" "$RESOURCES_DIR/src"
cp "$PROJECT_DIR/pyproject.toml" "$RESOURCES_DIR/pyproject.toml"
cp "$PROJECT_DIR/README.md" "$RESOURCES_DIR/README.md"

cat > "$CONTENTS_DIR/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>0.1.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

cat > "$MACOS_DIR/launcher" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$APP_DIR/Resources"
LOG_DIR="$HOME/Library/Logs/PixelMaterialGenerator"
VENV_DIR="$HOME/Library/Application Support/PixelMaterialGenerator/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
mkdir -p "$LOG_DIR" "$(dirname "$VENV_DIR")"
exec >> "$LOG_DIR/launcher.log" 2>&1

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$RESOURCES_DIR" pywebview pyobjc
export PYTHONPATH="$RESOURCES_DIR/src:${PYTHONPATH:-}"
cd "$RESOURCES_DIR"
exec "$VENV_DIR/bin/python" -m pixel_apng.gui
SH
chmod +x "$MACOS_DIR/launcher"

DMG_PATH="$DIST_DIR/$APP_NAME.dmg"
rm -f "$DMG_PATH"
hdiutil create -volname "$APP_NAME" -srcfolder "$APP_BUNDLE" -ov -format UDZO "$DMG_PATH"

echo "Built: $APP_BUNDLE"
echo "DMG: $DMG_PATH"
