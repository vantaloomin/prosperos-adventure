# Installing on a Mac

[Back to the README](../../README.md)

There is no Mac app or disk image yet. On a Mac you run Prospero Dungeon from a copy of this
project with the `.command` files in its `Mac` folder, which you double-click in Finder. They work on
Apple Silicon and Intel Macs running macOS 11 or later.

**Nobody on the project has tested these on a real Mac.** The only check is CI, which runs every
script on GitHub's macOS machines (Apple Silicon and Intel) on each change. Please report anything
that behaves differently on your Mac.

## Getting it running

1. Get the project, either way:
   - With Git: `git clone https://github.com/vantaloomin/prosperos-dungeon.git` in Terminal. This
     is the easier path: macOS does not flag cloned files.
   - Or download the ZIP from GitHub (Code > Download ZIP) and unzip it. See
     [the security warning](#the-first-time-macos-blocks-installcommand) below.
2. Open the `Mac` folder and double-click `install.command`. It needs Python 3.12 or newer and Node.js 22.13 or newer.
   - If you have [Homebrew](https://brew.sh), it installs whichever is missing with `brew install`.
   - If not, it opens the download page for the missing one ([python.org](https://www.python.org/downloads/macos/)
     or [nodejs.org](https://nodejs.org/en/download)). Install it and double-click `install.command` again.
   - The `python3` that comes with Apple's command line tools is too old (3.9) and is skipped.
3. Double-click `launch.command`. It starts the Dungeon at http://127.0.0.1:8785 and opens it in
   your browser. Keep the Terminal window open while you use it; close it or press Ctrl+C to stop.

## The first time macOS blocks install.command

Files downloaded in a ZIP are marked as coming from the internet, and these scripts are not signed
by an Apple developer account (signing is still an open decision). So the first double-click shows
a message like **"install.command" Not Opened: Apple could not verify "install.command" is free of
malware**. Click **Done**, then:

- **macOS 15 Sequoia and later:** open System Settings > Privacy & Security, scroll to Security,
  click **Open Anyway** next to the message about `install.command`, confirm with your password,
  then click **Open Anyway** once more.
- **macOS 14 Sonoma and earlier:** Control-click `install.command` in Finder, choose **Open**, then
  **Open** again.

You only do this once: `install.command` clears the mark from the other scripts in the folder.
Alternatively, run this in Terminal before the first double-click (with your folder's path):

```sh
xattr -dr com.apple.quarantine ~/Downloads/prosperos-dungeon-main
```

A Git clone never shows this warning.

## The other scripts

| Script | What it does |
| --- | --- |
| `install.command` | Finds or installs Python and Node.js, installs the locked dependencies into `.venv` and builds the interface. `--check-only` verifies an existing install. |
| `launch.command` | Starts the Dungeon on http://127.0.0.1:8785 and opens it in the browser. Takes `--port <n>` and `--no-browser`. |
| `update.command` | Gets the latest `main` and reinstalls. Close the Dungeon first. A Git clone pulls; a ZIP copy downloads the latest ZIP and copies it over the folder (files you added stay). The folder must be writable, so copy it off a disk image or read-only drive first. |
| `status.command` | Says whether the Dungeon is running. Exit code 0 running, 1 stopped, 2 port held by another program. Takes `--port <n>`. |
| `stop.command` | Stops a running Dungeon, for when its window is lost. Never stops another program on the port. Takes `--port <n>`. |
| `create-shortcut.command` | Puts a small **Prospero Dungeon** app in `~/Applications` that opens `launch.command` in Terminal. Spotlight and Launchpad find it, and you can drag it to the Dock. `--destination <folder>` puts it elsewhere. |
| `dev.command` | Development mode: the backend reloads on Python changes and Vite serves http://127.0.0.1:5177. Ctrl+C stops both. |

The `.command` files only start the matching script in `Program/scripts/macos/`, written for the
`/bin/bash` that ships with macOS. You can also run them from Terminal, for example
`Mac/launch.command --no-browser`.

## Where your data lives

Your workspace is in `~/Library/Application Support/ProsperoDungeon` (to see it in
Finder, press Cmd+Shift+G and paste that path). It is separate from the project folder, so deleting
or re-downloading the project keeps your worlds. Backups, private city packs (`city-packs/`)
and logs live there too. `DUNGEON_DATA_DIR` points it elsewhere.

To keep it with the project instead, for example on an external drive, use **Settings > Data >
Move into the app folder**. On the next start the app copies the workspace into a `Data` folder
beside `Mac/` and `Program/`, checks the copy, and uses it from then on; the old folder is left as
it was, with a `MOVED.txt`, until you delete it. Updates never touch `Data/`. On an external drive
macOS asks once whether Terminal may access files on a removable volume: allow it. Keep the drive
connected while the Dungeon runs.

API keys go in your login keychain under **Prospero Dungeon**. If Python is upgraded (for example
by Homebrew), macOS may ask once whether `python` may use that keychain item; choose **Always Allow**.

## What is different or missing on a Mac

| Feature | On a Mac |
| --- | --- |
| The story, worlds, cities, backups | Same as on Windows. Covered by the full test suite on macOS in CI. |
| Packaged app, installer, automatic restore of a failed upgrade | Windows only for now. A signed and notarized Mac app needs an Apple Developer account and is not planned yet. |
| Pictures with ComfyUI and Krea 2 | The app only talks to a ComfyUI address, so a ComfyUI on another computer works. ComfyUI does run on Apple Silicon, but whether Krea 2 (16 to 24 GB) runs well there is untested. |
| Pictures with the Codex CLI or hosted services | Should work as on Windows; untested. The `codex` command must be one Terminal can find. |
| Timezone | Read from the Mac's setting (`/etc/localtime`), as on Linux. |
