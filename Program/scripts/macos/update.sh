#!/bin/bash
# Updates this copy to the latest main, then reruns install.sh (locked dependencies and a fresh interface
# build). A Git clone pulls main; a copy downloaded as a ZIP downloads main's ZIP and copies it over.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DUNGEON_ROOT" || exit 1

UPDATE_ZIP_URL='https://github.com/vantaloomin/prosperos-dungeon/archive/refs/heads/main.zip'
# The files the last ZIP update copied in, so the next one can remove the ones main no longer has.
UPDATE_MANIFEST="$CHECKOUT_ROOT/.zip-update-files"

fail() {
    say_error "Update failed: $*"
    echo "Your Dungeon data was not touched."
    exit 1
}

program_version() {
    sed -n 's/^  "version": "\([^"]*\)".*/\1/p' "$1/package.json" | head -n 1
}

reset_diverged_main() {
    # main has commits GitHub's main lacks, usually because a pull request was squash-merged: the squash
    # makes one new commit, so the local ones it replaced never fast-forward. They are kept on a dated
    # backup branch, then main is moved to match GitHub.
    local before="$1" latest="$2" backup count
    [ -z "$(git status --porcelain --untracked-files=no)" ] ||
        fail "main has changes GitHub's main does not have, and edited files that are not committed. Commit or stash them ('git stash'), then update again. Nothing was changed."
    backup="backup/main-$(date +%Y%m%d-%H%M%S)"
    count="$(git rev-list --count "$latest..$before")"
    git branch "$backup" "$before" || fail "Could not make the backup branch $backup. Nothing was changed."
    git reset --quiet --hard "$latest" || fail "git reset failed; your commits are on $backup."
    echo "Your main had $count commit(s) that GitHub's main does not (usually left over from a squash merge)."
    echo "They are saved on the branch $backup; main now matches GitHub. Delete that branch once you no longer need it."
}

update_with_git() {
    # On a Mac without the command line tools, /usr/bin/git is a stub that offers to install them.
    git --version >/dev/null 2>&1 || fail 'Git is not installed. Run "xcode-select --install" in Terminal, then update again.'
    local branch before after latest
    branch="$(git -C "$CHECKOUT_ROOT" rev-parse --abbrev-ref HEAD 2>&1)" || fail "Git could not read this folder: $branch"
    [ "$branch" = main ] || fail "This checkout is on '$branch'. update.command only updates main; switch with 'git switch main' first."
    before="$(git rev-parse HEAD)"
    git fetch origin main || fail 'git fetch failed; see above.'
    latest="$(git rev-parse FETCH_HEAD)"
    if git merge-base --is-ancestor "$before" "$latest"; then
        git merge --ff-only "$latest" || fail 'git merge failed; see above.'
    else
        reset_diverged_main "$before" "$latest"
    fi
    after="$(git rev-parse HEAD)"
    if [ "$before" = "$after" ]; then
        echo 'Already up to date. Reinstalling to make sure everything matches.'
    else
        echo "Updated ${before:0:7} to ${after:0:7}:"
        git log --oneline --no-decorate "$before..$after"
    fi
}

update_from_zip() {
    [ -w "$CHECKOUT_ROOT" ] || fail "This folder can't be changed (it may be on a read-only disk): $CHECKOUT_ROOT. Copy the whole folder to your Mac, for example into Documents, and run update.command from there."
    local work source before after relative
    work="$(mktemp -d "${TMPDIR:-/tmp}/dungeon-update.XXXXXX")" || fail 'Could not make a temporary folder.'
    trap 'rm -rf "$work"' EXIT
    if [ -n "$DUNGEON_UPDATE_ZIP" ]; then
        cp "$DUNGEON_UPDATE_ZIP" "$work/main.zip" || fail "Could not read $DUNGEON_UPDATE_ZIP."
    else
        echo 'This copy was downloaded as a ZIP, so the latest version is downloaded the same way.'
        curl --fail --location --silent --show-error --output "$work/main.zip" "$UPDATE_ZIP_URL" ||
            fail "Could not download $UPDATE_ZIP_URL. Check the internet connection and try again."
    fi
    unzip -q "$work/main.zip" -d "$work/unpacked" || fail 'The downloaded ZIP could not be opened. Try again.'
    # GitHub puts everything in one folder named after the repository and branch.
    for source in "$work"/unpacked/*; do break; done
    [ -f "$source/Program/pyproject.toml" ] && [ -f "$source/Mac/update.command" ] ||
        fail 'The downloaded ZIP does not look like Prospero Dungeon. Nothing was changed.'

    before="$(program_version "$DUNGEON_ROOT")"
    after="$(program_version "$source/Program")"
    (cd "$source" && find . -type f | sed 's|^\./||' | LC_ALL=C sort) > "$work/files"
    # Remove what an earlier ZIP update put here that main no longer has. Only paths from that list are
    # touched, so files you added yourself (and .venv, node_modules, dist) stay.
    if [ -f "$UPDATE_MANIFEST" ]; then
        LC_ALL=C sort "$UPDATE_MANIFEST" | LC_ALL=C comm -23 - "$work/files" | while IFS= read -r relative; do
            case "$relative" in ''|/*|*..*) continue ;; esac
            [ -f "$CHECKOUT_ROOT/$relative" ] && rm -f "$CHECKOUT_ROOT/$relative"
        done
    fi
    cp -R "$source/." "$CHECKOUT_ROOT/" || fail 'Copying the new version into this folder failed; see above. Run update.command again to finish.'
    cp "$work/files" "$UPDATE_MANIFEST"
    chmod +x "$MAC_FOLDER"/*.command "$DUNGEON_ROOT"/scripts/macos/*.sh 2>/dev/null
    if [ "$before" = "$after" ]; then
        echo "Copied in the latest main (version $after). Reinstalling to make sure everything matches."
    else
        echo "Updated version $before to $after."
    fi
}

# Everything runs from this function so bash has read the whole script before a ZIP update replaces it.
main() {
    echo 'Prospero Dungeon - update'
    dungeon_state "$DUNGEON_PORT"
    [ "$STATE" = running ] && fail 'Prospero Dungeon is running. Close its window (or double-click stop.command), then update again.'
    if [ -e "$CHECKOUT_ROOT/.git" ]; then
        update_with_git
    else
        update_from_zip
    fi
    /bin/bash "$DUNGEON_ROOT/scripts/macos/install.sh" || fail 'The reinstall failed; see above.'
}

main "$@"; exit
