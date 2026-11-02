#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Says whether Prospero Adventure is running.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/status.sh" "$@"
