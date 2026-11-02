#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Starts Prospero Adventure on http://127.0.0.1:8805 and opens it in the browser. Close the window to stop it.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/launch.sh" "$@"
