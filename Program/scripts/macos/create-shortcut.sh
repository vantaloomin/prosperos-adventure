#!/bin/bash
# Makes a small "Prospero Dungeon" app that opens this checkout's launch.command in Terminal. It goes in
# ~/Applications, where Spotlight and Launchpad find it and from where it can be dragged to the Dock.
# Option: --destination <folder>.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

destination="$HOME/Applications"
[ "$1" = '--destination' ] && destination="$2"
target="$MAC_FOLDER/launch.command"

fail() {
    say_error "Shortcut failed: $*"
    exit 1
}

mkdir -p "$destination" || fail "Could not create $destination."
app="$destination/Prospero Dungeon.app"
# Another copy (say, a later installed app) may already own that name; never repoint it at this checkout.
if [ -e "$app" ] && ! grep -qF "checkout at $CHECKOUT_ROOT in Terminal" "$app/Contents/MacOS/launch" 2>/dev/null; then
    app="$destination/Prospero Dungeon (checkout).app"
fi
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources" || fail "Could not write $app."
cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Prospero Dungeon</string>
    <key>CFBundleDisplayName</key><string>Prospero Dungeon</string>
    <key>CFBundleIdentifier</key><string>io.github.vantaloomin.prospero-dungeon.checkout</string>
    <key>CFBundleExecutable</key><string>launch</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>0.1.0</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST
# printf %q quotes the path for the shell, spaces and all.
printf '#!/bin/bash\n# Opens the Prospero Dungeon checkout at %s in Terminal.\nexec open -a Terminal %q\n' \
    "$CHECKOUT_ROOT" "$target" > "$app/Contents/MacOS/launch"
chmod +x "$app/Contents/MacOS/launch"
say_ok "Created $app"
