#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Pulls the latest main and reinstalls. Close Prospero Adventure first.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/update.sh" "$@"
