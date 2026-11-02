#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Development mode: the backend reloads on Python changes and Vite serves http://127.0.0.1:5177.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/dev.sh" "$@"
