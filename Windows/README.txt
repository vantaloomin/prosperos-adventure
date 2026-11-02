Prospero Dungeon on Windows - start here

1. Double-click install.bat once. It finds or installs Python and Node.js, then sets everything up.
2. Double-click launch.bat to start the Dungeon. It opens in your browser at http://127.0.0.1:8785.
   Keep its window open while you use it; close the window to stop.

Other scripts in this folder:
  update.bat           Gets the latest version and reinstalls. Close the Dungeon first.
  status.bat           Says whether the Dungeon is running.
  stop.bat             Stops the Dungeon if you lost its window.
  create-shortcut.bat  Puts a Prospero Dungeon shortcut on your desktop.
  dev.bat              Development mode, for working on the code.
  backdrops.bat        Makes the worlds' default place pictures with ChatGPT images (needs the
                       Codex CLI signed in: npm i -g @openai/codex, then codex login).

Your data is normally not in this folder. It lives in %LOCALAPPDATA%\ProsperoDungeon,
so updating or re-downloading the program keeps it. To keep it with the app instead (for example
on an external drive), use Settings > Data > "Move into the app folder": it then lives in a Data
folder here, which updates leave alone. The app itself is in the Program folder, which you never
need to open.
