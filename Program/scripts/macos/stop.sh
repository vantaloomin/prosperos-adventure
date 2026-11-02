#!/bin/bash
# Stops a running Prospero Dungeon, and only that: another program on the port is never touched.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
port="$DUNGEON_PORT"
[ "$1" = '--port' ] && port="$2"
check_port "$port"
dungeon_state "$port"
case "$STATE" in
    stopped) echo 'Prospero Dungeon is not running. Nothing to stop.'; exit 0 ;;
    foreign) say_error "Stop failed: port $port belongs to another program (process $STATE_PID). Nothing was stopped."; exit 1 ;;
esac
if [ -z "$STATE_PID" ]; then
    say_error 'Stop failed: Prospero Dungeon answers, but its process could not be found. Close its window instead.'
    exit 1
fi
pid="$STATE_PID"
stop_tree "$pid"
# The server saves and exits on SIGTERM; force it only if it is still there after ten seconds.
if ! wait_for_state stopped "$port" 40; then
    kill -9 "$pid" 2>/dev/null
    wait_for_state stopped "$port" 20 || { say_error "Stop failed: process $pid did not stop."; exit 1; }
fi
say_ok 'Stopped Prospero Dungeon. Your workspace is saved; launch.command starts it again.'
