#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Says whether Prospero Dungeon is running.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/status.sh" "$@"
