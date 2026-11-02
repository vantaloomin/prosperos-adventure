#!/bin/bash
# Starts Prospero Dungeon on http://127.0.0.1:8785 and opens it in the browser. Keep the window open;
# close it (or press Ctrl+C) to stop. Options: --port <n>, --no-browser.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DUNGEON_ROOT" || exit 1

port="$DUNGEON_PORT"
arguments=()
while [ $# -gt 0 ]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        --no-browser) arguments+=(--no-browser); shift ;;
        *) say_error "Unknown option: $1"; exit 1 ;;
    esac
done
check_port "$port"

python="$DUNGEON_ROOT/.venv/bin/python"
if [ ! -x "$python" ]; then say_error 'Launch failed: dependencies are missing. Double-click install.command first.'; exit 1; fi
if [ ! -f dist/index.html ]; then say_error 'Launch failed: the interface is not built. Double-click install.command first.'; exit 1; fi
exec "$python" -m dungeon.launch --port "$port" ${arguments[@]+"${arguments[@]}"}
