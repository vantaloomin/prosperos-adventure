#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Finds or installs Python 3.12+ and Node.js 22.13+, installs the dependencies and builds the interface.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/install.sh" "$@"
