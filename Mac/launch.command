#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Starts Prospero Dungeon on http://127.0.0.1:8785 and opens it in the browser. Close the window to stop it.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/launch.sh" "$@"
