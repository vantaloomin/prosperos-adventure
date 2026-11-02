#!/bin/bash
# Exercises the macOS checkout scripts (status, stop, launch, create-shortcut, dev, update) through their
# .command files after install.command. Used by CI. Expects DUNGEON_DATA_DIR to point at a scratch
# workspace. The update check rewires this checkout's origin to a local repository, so run it on a
# throwaway checkout only.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DUNGEON_ROOT" || exit 1
temp="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
python="$DUNGEON_ROOT/.venv/bin/python"

check() {
    # check <description> <command...>: the command must succeed.
    local description="$1"; shift
    if "$@"; then echo "ok  $description"; else say_error "FAILED  $description"; exit 1; fi
}

exits() {
    # exits <code> <script> [args]: runs a .command and compares its exit code.
    local expected="$1" script="$2"; shift 2
    "$MAC_FOLDER/$script" "$@" >"$temp/helper-out.txt" 2>&1
    local code=$?
    cat "$temp/helper-out.txt"
    [ "$code" -eq "$expected" ]
}

background=''
cleanup() { [ -n "$background" ] && stop_tree "$background" 2>/dev/null; }
trap cleanup EXIT

# status, stop and launch
check 'status.command reports a stopped Dungeon with exit code 1' exits 1 status.command
check 'stop.command with nothing running succeeds and stops nothing' exits 0 stop.command
"$MAC_FOLDER/launch.command" --no-browser >"$temp/launch-out.txt" 2>&1 &
background=$!
check 'launch.command answers on 8785' wait_for_state running 8785
check 'status.command reports the running Dungeon with exit code 0' exits 0 status.command
check 'stop.command stops the running Dungeon' exits 0 stop.command
check 'port 8785 is free after stop.command' wait_for_state stopped 8785 4
check 'launch.command reports a missing option' exits 1 launch.command --nonsense

# Another program on the port is reported and never stopped.
"$python" -m http.server 8790 --bind 127.0.0.1 >/dev/null 2>&1 &
background=$!
check 'a foreign server holds 8790' wait_for_state foreign 8790
check 'status.command reports a port held by another program with exit code 2' exits 2 status.command --port 8790
check 'stop.command refuses to stop another program' exits 1 stop.command --port 8790
check 'the other program is still running' kill -0 "$background"
stop_tree "$background"; background=''

# create-shortcut
apps="$temp/applications"
mkdir -p "$apps"
check 'create-shortcut.command succeeds' exits 0 create-shortcut.command --destination "$apps"
app="$apps/Prospero Dungeon.app"
check 'the app has a valid Info.plist' plutil -lint "$app/Contents/Info.plist"
check "the app opens this checkout's launch.command" grep -qF "$(printf '%q' "$MAC_FOLDER/launch.command")" "$app/Contents/MacOS/launch"
check 'the app launcher is executable' test -x "$app/Contents/MacOS/launch"
check 'running create-shortcut.command again keeps one app' exits 0 create-shortcut.command --destination "$apps"
check '...under the same name' test ! -e "$apps/Prospero Dungeon (checkout).app"
printf '#!/bin/bash\nexec open -a TextEdit\n' > "$app/Contents/MacOS/launch"
check 'create-shortcut.command succeeds beside an installed app' exits 0 create-shortcut.command --destination "$apps"
check 'the existing app is left alone' grep -q TextEdit "$app/Contents/MacOS/launch"
check 'the checkout app gets its own name' test -x "$apps/Prospero Dungeon (checkout).app/Contents/MacOS/launch"

# dev: backend plus Vite, with /api forwarded to the backend
"$MAC_FOLDER/dev.command" --no-browser >"$temp/dev-out.txt" 2>&1 &
background=$!
check 'dev mode starts the backend on 8785' wait_for_state running 8785
page_has() {
    local tries=120
    while [ "$tries" -gt 0 ]; do
        curl --noproxy '*' --silent --max-time 3 "$1" | grep -q "$2" && return 0
        sleep 0.5; tries=$((tries - 1))
    done
    return 1
}
check 'Vite serves the interface on 5177' page_has 'http://127.0.0.1:5177/' 'Prospero Dungeon'
check 'Vite forwards /api to the backend' page_has 'http://127.0.0.1:5177/api/health' "$DUNGEON_APP_ID"
# A background job ignores SIGINT, so stand in for Ctrl+C with SIGTERM; dev.sh traps both.
kill -TERM "$background"
wait "$background" 2>/dev/null
background=''
check 'closing dev mode stops its backend' wait_for_state stopped 8785
# stop_tree only signals Vite, which then exits on its own, so give it a moment to let go of 5177.
port_released() {
    local tries=40
    while [ "$tries" -gt 0 ]; do
        [ -z "$(port_owner "$1")" ] && return 0
        sleep 0.25; tries=$((tries - 1))
    done
    return 1
}
check 'closing dev mode stops Vite' port_released 5177

# update: fast-forward from a local origin, then reinstall. CI checkouts are shallow, so the local
# origin accepts shallow pushes.
git config --global user.email ci@example.invalid
git config --global user.name CI
remote="$temp/update-origin.git"
clone="$temp/update-clone"
git init --quiet --bare "$remote"
git -C "$remote" config receive.shallowUpdate true
git checkout --quiet -B main
git push --quiet "$remote" HEAD:refs/heads/main
git clone --quiet --branch main "$remote" "$clone"
echo pulled > "$clone/update-marker.txt"
git -C "$clone" add update-marker.txt
git -C "$clone" commit --quiet -m 'Marker for the update test'
git -C "$clone" push --quiet origin main
git remote set-url origin "$remote"
check 'update.command pulls main and reinstalls' exits 0 update.command
check 'the new commit was pulled' test -f "$CHECKOUT_ROOT/update-marker.txt"
# A main that diverged from origin (as after a squash merge) is backed up to a branch, then reset.
echo local > "$CHECKOUT_ROOT/local-only.txt"
git -C "$CHECKOUT_ROOT" add local-only.txt
git -C "$CHECKOUT_ROOT" commit --quiet -m "Local commit GitHub never got"
echo squashed > "$clone/squashed.txt"
git -C "$clone" add squashed.txt
git -C "$clone" commit --quiet -m 'Squash merge on GitHub'
git -C "$clone" push --quiet origin main
check 'update.command updates a main that diverged from origin' exits 0 update.command
check 'main now matches origin' test -f "$CHECKOUT_ROOT/squashed.txt"
check 'the local-only commit left main' test ! -e "$CHECKOUT_ROOT/local-only.txt"
backup="$(git branch --list 'backup/main-*' --format '%(refname:short)')"
check 'the local-only commit was kept on a backup branch' test -n "$backup"
check 'the backup branch has the local-only file' git cat-file -e "$backup:local-only.txt"
check 'the interface was rebuilt' test -f dist/index.html
"$python" -m dungeon.launch --no-browser >/dev/null 2>&1 &
background=$!
check 'the Dungeon launches after updating' wait_for_state running 8785
check 'update.command refuses while the Dungeon runs' exits 1 update.command
stop_tree "$background"; background=''
wait_for_state stopped 8785 >/dev/null
git checkout --quiet -b elsewhere
check 'update.command refuses a branch other than main' exits 1 update.command

# update from a ZIP download: a copy without .git gets main's ZIP (here a local one) copied over it.
# Files an earlier ZIP update listed and main no longer has are removed; anything else stays.
zip="$temp/update-main.zip"
git -C "$CHECKOUT_ROOT" archive --format=zip --prefix=prosperos-dungeon-main/ --output "$zip" HEAD
rm "$MAC_FOLDER/README.txt"
echo stale > "$CHECKOUT_ROOT/stale-from-zip.txt"
echo mine > "$CHECKOUT_ROOT/my-own-file.txt"
printf 'stale-from-zip.txt\n' > "$CHECKOUT_ROOT/.zip-update-files"
mv "$CHECKOUT_ROOT/.git" "$CHECKOUT_ROOT.git-aside"
DUNGEON_UPDATE_ZIP="$zip" "$MAC_FOLDER/update.command" >"$temp/helper-out.txt" 2>&1
code=$?
mv "$CHECKOUT_ROOT.git-aside" "$CHECKOUT_ROOT/.git"
cat "$temp/helper-out.txt"
check 'update.command updates a copy downloaded as a ZIP' test "$code" -eq 0
check 'the ZIP was copied in' test -f "$MAC_FOLDER/README.txt"
check 'the scripts are still executable' test -x "$MAC_FOLDER/launch.command"
check 'a file the last ZIP update listed and main dropped is removed' test ! -e "$CHECKOUT_ROOT/stale-from-zip.txt"
check 'a file of your own is kept' test -f "$CHECKOUT_ROOT/my-own-file.txt"
check 'the new file list was written' grep -qx 'Mac/update.command' "$CHECKOUT_ROOT/.zip-update-files"
check 'the interface was rebuilt after the ZIP update' test -f dist/index.html

# A .venv without pip (as when Homebrew moves python3 to a newer version under it) is rebuilt.
"$python" -m pip uninstall --yes --quiet pip
check 'the test .venv has lost pip' test "$("$python" -m pip --version >/dev/null 2>&1; echo $?)" -ne 0
check 'install.command rebuilds a .venv without pip' exits 0 install.command
check 'the rebuilt .venv has pip' "$python" -m pip --version

echo 'All checkout helper checks passed.'
