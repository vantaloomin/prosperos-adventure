Prospero Dungeon on a Mac - start here

1. Double-click install.command once. It finds or installs Python and Node.js, then sets everything up.
   The first time, macOS may refuse to open it; Program/docs/macos.md shows how to allow it.
2. Double-click launch.command to start the Dungeon. It opens in your browser at http://127.0.0.1:8785.
   Keep its Terminal window open while you use it; close the window to stop.

Other scripts in this folder:
  update.command           Gets the latest version and reinstalls. Close the Dungeon first.
  status.command           Says whether the Dungeon is running.
  stop.command             Stops the Dungeon if you lost its window.
  create-shortcut.command  Puts a Prospero Dungeon app in your Applications folder.
  dev.command              Development mode, for working on the code.

Your data is normally not in this folder. It lives in ~/Library/Application Support/ProsperoDungeon,
so updating or re-downloading the program keeps it. To keep it with the app instead (for example
on an external drive), use Settings > Data > "Move into the app folder": it then lives in a Data
folder here, which updates leave alone. The app itself is in the Program folder, which you never
need to open.
