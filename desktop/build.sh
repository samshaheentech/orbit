#!/bin/bash
# Build Orbit.app from desktop/OrbitApp.swift with the Command Line Tools. No Xcode project.
#   bash desktop/build.sh          builds, installs to ~/Applications, opens
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/build"; APP="$OUT/Orbit.app"
command -v swiftc >/dev/null 2>&1 || { echo "swiftc not found. Install the Command Line Tools: xcode-select --install"; exit 1; }
echo "==> Compiling"
rm -rf "$OUT"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -o "$APP/Contents/MacOS/Orbit" "$HERE/OrbitApp.swift" -framework AppKit -framework WebKit -framework UserNotifications
cp "$HERE/Info.plist" "$APP/Contents/Info.plist"
echo "==> Signing (ad hoc, local use)"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "    codesign skipped"
echo "==> Installing to ~/Applications"
mkdir -p "$HOME/Applications"; rm -rf "$HOME/Applications/Orbit.app"; cp -R "$APP" "$HOME/Applications/Orbit.app"
echo "==> Opening"
open "$HOME/Applications/Orbit.app"
echo "Done. Orbit is in ~/Applications; drag it to the Dock. Start at login: System Settings, General, Login Items."
