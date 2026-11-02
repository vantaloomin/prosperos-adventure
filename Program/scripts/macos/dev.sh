#!/bin/bash
# Development mode: the backend (reloading on Python changes) in the background, and Vite on 5177 in front.
# Ctrl+C stops both. Option: --no-browser.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DUNGEON_ROOT" || exit 1

fail() {
    say_error "Dev mode failed: $*"
    exit 1
}

python="$DUNGEON_ROOT/.venv/bin/python"
[ -x "$python" ] || fail 'Dependencies are missing. Double-click install.command first.'
[ -d node_modules ] || fail 'Interface packages are missing. Double-click install.command first.'
command -v npm >/dev/null 2>&1 || fail 'npm was not found. Double-click install.command first.'
[ -z "$(port_owner 5177)" ] || fail 'Port 5177 is in use, probably by another dev window. Close it and retry.'

backend=''
vite=''
cleanup() {
    [ -n "$vite" ] && stop_tree "$vite" 2>/dev/null
    if [ -n "$backend" ] && kill -0 "$backend" 2>/dev/null; then
        stop_tree "$backend"
        echo 'Stopped the development backend.'
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

dungeon_state "$DUNGEON_PORT"
if [ "$STATE" = foreign ]; then
    fail "Port $DUNGEON_PORT belongs to another program (process $STATE_PID). Nothing was stopped."
elif [ "$STATE" = running ]; then
    echo "Using the Prospero Dungeon backend that is already running on $DUNGEON_PORT (it will not reload on changes)."
else
    "$python" -m uvicorn dungeon.main:create_app --factory --host 127.0.0.1 --port "$DUNGEON_PORT" \
        --reload --reload-dir dungeon &
    backend=$!
    tries=120
    while [ "$tries" -gt 0 ]; do
        dungeon_state "$DUNGEON_PORT"
        [ "$STATE" = running ] && break
        kill -0 "$backend" 2>/dev/null || fail 'The backend stopped while starting; see above.'
        sleep 0.25
        tries=$((tries - 1))
    done
    [ "$STATE" = running ] || fail "The backend did not answer on $DUNGEON_PORT."
    echo "Backend running on http://127.0.0.1:$DUNGEON_PORT (process $backend); its log is in this window."
fi
echo 'Interface: http://127.0.0.1:5177 (reloads as you edit src/). Press Ctrl+C to stop.'
say_warn 'Dev mode uses your real workspace. Set DUNGEON_DATA_DIR to a scratch folder to keep it apart.'
# Vite runs in the background so a signal reaches this script's trap at once (a background job ignores
# Ctrl+C itself, so the trap is what stops it).
if [ "$1" = '--no-browser' ]; then npm run dev & else npm run dev -- --open & fi
vite=$!
wait "$vite"
