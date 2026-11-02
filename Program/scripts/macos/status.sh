#!/bin/bash
# Says whether Prospero Adventure is running on this checkout's port. Exit 0 running, 1 stopped, 2 port taken.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
port="$ADVENTURE_PORT"
[ "$1" = '--port' ] && port="$2"
check_port "$port"
adventure_state "$port"
case "$STATE" in
    running) say_ok "Prospero Adventure $STATE_VERSION is running at http://127.0.0.1:$port/ (process $STATE_PID)."; exit 0 ;;
    foreign) say_warn "Prospero Adventure is not running, but another program (process $STATE_PID) is using port $port."; exit 2 ;;
    *) echo 'Prospero Adventure is not running. Double-click launch.command to start it.'; exit 1 ;;
esac
