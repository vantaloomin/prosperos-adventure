# Shared by the macOS checkout scripts. Source it; it defines functions and fixes up PATH.
# Written for the /bin/bash that ships with macOS (3.2), so no associative arrays or ${var,,}.
# Program (the code, its .venv, node_modules and dist), the checkout above it, and the Mac folder of
# double-click scripts beside it.
DUNGEON_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CHECKOUT_ROOT="$(dirname "$DUNGEON_ROOT")"
MAC_FOLDER="$CHECKOUT_ROOT/Mac"
DUNGEON_APP_ID='prospero-dungeon'
DUNGEON_PORT=8785
# A double-clicked .command may not see the PATH a Terminal tab gets from ~/.zprofile, so add the
# usual Homebrew and installer locations (Apple Silicon Homebrew, Intel Homebrew and the python.org and
# nodejs.org installers' links in /usr/local/bin).
PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"
export PATH

say_ok() { printf '\033[32m%s\033[0m\n' "$*"; }
say_warn() { printf '\033[33m%s\033[0m\n' "$*"; }
say_error() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

dungeon_health() {
    # The health answer on the port, "other" when something else answers, or nothing when nothing does.
    # --noproxy keeps a system proxy out of a loopback check.
    local body
    body="$(curl --noproxy '*' --silent --show-error --max-time 2 "http://127.0.0.1:$1/api/health" 2>/dev/null)" || return 0
    case "$body" in
        *"\"app_id\":\"$DUNGEON_APP_ID\""*) printf '%s\n' "$body" ;;
        *) printf 'other\n' ;;
    esac
}

port_owner() {
    # The process id listening on the port, or nothing.
    lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -n 1
}

dungeon_state() {
    # Sets STATE to running (this app answers), foreign (another program holds the port) or stopped,
    # with STATE_PID and STATE_VERSION when known.
    local health
    health="$(dungeon_health "$1")"
    STATE_PID="$(port_owner "$1")"
    STATE_VERSION=''
    if [ -n "$health" ] && [ "$health" != 'other' ]; then
        STATE='running'
        STATE_VERSION="$(printf '%s' "$health" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')"
    elif [ -n "$health" ] || [ -n "$STATE_PID" ]; then
        STATE='foreign'
    else
        STATE='stopped'
    fi
}

wait_for_state() {
    # wait_for_state <state> <port> [tries]: polls every quarter second.
    local tries="${3:-120}"
    while [ "$tries" -gt 0 ]; do
        dungeon_state "$2"
        [ "$STATE" = "$1" ] && return 0
        sleep 0.25
        tries=$((tries - 1))
    done
    return 1
}

stop_tree() {
    # Ends a process and its children (a --reload backend runs its server in a child).
    local pid="$1" child
    for child in $(pgrep -P "$pid" 2>/dev/null); do stop_tree "$child"; done
    kill "$pid" 2>/dev/null
}

check_port() {
    case "$1" in
        ''|*[!0-9]*) say_error "The port must be a number from 1024 to 65535."; exit 1 ;;
    esac
    if [ "$1" -lt 1024 ] || [ "$1" -gt 65535 ]; then
        say_error "The port must be a number from 1024 to 65535."; exit 1
    fi
}
