#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Adds a Prospero Dungeon app to ~/Applications that starts this checkout.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/create-shortcut.sh" "$@"
