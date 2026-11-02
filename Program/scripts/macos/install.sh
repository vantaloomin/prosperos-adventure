#!/bin/bash
# Finds or installs Python 3.12+ and Node.js 22.13+, installs the locked dependencies into .venv and
# builds the interface. The macOS counterpart of install.ps1. --check-only verifies an existing install.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DUNGEON_ROOT" || exit 1

CHECK_ONLY=0
for argument in "$@"; do
    case "$argument" in
        --check-only) CHECK_ONLY=1 ;;
        *) say_error "Unknown option: $argument"; exit 1 ;;
    esac
done

fail() {
    say_error "Setup failed: $*"
    exit 1
}

run() {
    "$@" || fail "$1 failed with exit code $?. Fix the error above and run install.command again."
}

python_ok() {
    # Prints the interpreter's path when it is Python 3.12 or newer. The python3 that comes with
    # Apple's command line tools is 3.9, so it is passed over.
    [ -n "$1" ] && [ -x "$1" ] || return 1
    "$1" -c 'import sys; sys.exit(1) if sys.version_info < (3, 12) else print(sys.executable)' 2>/dev/null
}

find_python() {
    local candidate found
    for candidate in "$DUNGEON_ROOT/.venv/bin/python" \
        "$(command -v python3.13)" "$(command -v python3.12)" "$(command -v python3.14)" \
        /Library/Frameworks/Python.framework/Versions/3.1[2-9]/bin/python3 \
        /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python3)"; do
        found="$(python_ok "$candidate")" && { printf '%s\n' "$found"; return 0; }
    done
    return 1
}

find_node() {
    local node version major minor
    node="$(command -v node)" || return 1
    version="$("$node" -p 'process.versions.node' 2>/dev/null)" || return 1
    major="${version%%.*}"; minor="${version#*.}"; minor="${minor%%.*}"
    if [ "$major" -gt 22 ] || { [ "$major" -eq 22 ] && [ "$minor" -ge 13 ]; }; then
        printf '%s\n' "$node"
        return 0
    fi
    return 1
}

install_with_homebrew() {
    # Homebrew installs without administrator rights once it is set up. Without it, point at the
    # official installers instead of installing Homebrew behind the user's back.
    if ! command -v brew >/dev/null 2>&1; then
        open "$2" 2>/dev/null
        fail "$1 was not found. Install it from $2 (the page is opening), then run install.command again."
    fi
    echo "Installing missing prerequisite with Homebrew: $3"
    run brew install "$3"
}

python="$(find_python)"
if [ -z "$python" ] && [ "$CHECK_ONLY" = 0 ]; then
    install_with_homebrew 'Python 3.12 or newer' 'https://www.python.org/downloads/macos/' 'python@3.12'
    python="$(find_python)"
fi
[ -n "$python" ] || fail 'Python 3.12 or newer was not found. Install it from https://www.python.org/downloads/macos/ and run install.command again.'

node="$(find_node)"
if [ -z "$node" ] && [ "$CHECK_ONLY" = 0 ]; then
    if command -v node >/dev/null 2>&1; then
        # Too old. Upgrade a Homebrew Node; leave any other install to its owner.
        if command -v brew >/dev/null 2>&1 && brew list node >/dev/null 2>&1; then
            echo 'Upgrading Node.js with Homebrew; the interface needs 22.13 or newer.'
            run brew upgrade node
        else
            fail "Node.js $(node -v) is too old; the interface needs 22.13 or newer. Update it from https://nodejs.org and run install.command again."
        fi
    else
        install_with_homebrew 'Node.js 22.13 or newer' 'https://nodejs.org/en/download' 'node'
    fi
    node="$(find_node)"
fi
[ -n "$node" ] || fail 'Node.js 22.13 or newer was not found. Install it from https://nodejs.org and run install.command again.'
npm="$(dirname "$node")/npm"
[ -x "$npm" ] || fail 'npm is missing beside Node.js. Reinstall Node.js and try again.'

venv_python="$DUNGEON_ROOT/.venv/bin/python"

verify() {
    [ -x "$venv_python" ] || fail 'The project environment is missing. Run install.command first.'
    run "$venv_python" -m pip check
    run "$venv_python" -c 'import fastapi, uvicorn, httpx, pydantic, keyring'
    run "$npm" ls --depth=0
    [ -f dist/index.html ] || fail 'The interface has not been built. Run install.command.'
}

echo 'Prospero Dungeon - dependency setup'
# A downloaded ZIP marks every script as quarantined, so each would need its own trip through
# Privacy & Security. Opening this one was the user's choice; clear the mark on its siblings.
xattr -d com.apple.quarantine "$MAC_FOLDER"/*.command "$DUNGEON_ROOT"/scripts/macos/*.sh 2>/dev/null
if [ "$CHECK_ONLY" = 0 ]; then
    # .venv only holds installed packages, so a broken one is rebuilt. It breaks when the Python it was
    # made from is upgraded or removed (Homebrew moving python3 from 3.12 to 3.13 leaves it without pip
    # or its packages).
    if [ -d .venv ] && ! { python_ok "$venv_python" >/dev/null && "$venv_python" -m pip --version >/dev/null 2>&1; }; then
        say_warn 'The project environment (.venv) is broken or was made by a Python that has since changed. Rebuilding it.'
        rm -rf .venv || fail "Could not remove $DUNGEON_ROOT/.venv. Delete that folder and run install.command again."
        python="$(find_python)"
        [ -n "$python" ] || fail 'Python 3.12 or newer was not found. Install it from https://www.python.org/downloads/macos/ and run install.command again.'
    fi
    [ -d .venv ] || run "$python" -m venv .venv
    run "$venv_python" -m pip install --disable-pip-version-check --no-input -r requirements.lock.txt
    run "$npm" ci --no-audit --no-fund
    run "$npm" run build
fi
verify
say_ok 'Ready. Double-click launch.command in the Mac folder to open Prospero Dungeon.'
echo 'Connect a model in Settings inside the app. Nothing is downloaded until you choose to.'
# What this computer can run locally (dungeon/hardware.py). Advice only: it never fails setup.
echo
"$venv_python" -m dungeon.hardware || true
