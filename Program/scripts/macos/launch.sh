#!/bin/bash
# Starts Prospero Adventure on http://127.0.0.1:8805 and opens it in the browser. Keep the window open;
# close it (or press Ctrl+C) to stop. Options: --port <n>, --no-browser.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$ADVENTURE_ROOT" || exit 1

port="$ADVENTURE_PORT"
arguments=()
while [ $# -gt 0 ]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        --no-browser) arguments+=(--no-browser); shift ;;
        *) say_error "Unknown option: $1"; exit 1 ;;
    esac
done
check_port "$port"

python="$ADVENTURE_ROOT/.venv/bin/python"
if [ ! -x "$python" ]; then say_error 'Launch failed: dependencies are missing. Double-click install.command first.'; exit 1; fi
if [ ! -f dist/index.html ]; then say_error 'Launch failed: the interface is not built. Double-click install.command first.'; exit 1; fi
exec "$python" -m adventure.launch --port "$port" ${arguments[@]+"${arguments[@]}"}
