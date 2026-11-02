# Changelog

## Unreleased

- **Your Claude and ChatGPT accounts, found for you.** A Claude Code or Codex profile now lists the accounts on this
  PC to pick from: the usual one, plus each second command such as `claude2` (a script on PATH, or a function or
  alias in your PowerShell profile) and account folders like `.claude-account2`, with whether each is signed in and
  as whom. Codex profiles can now use a second ChatGPT account too, through their own account folder. (Ported from
  Prospero's Dungeon #234.)
- **Starting point:** a clean copy of [Prospero's Dungeon](https://github.com/vantaloomin/prosperos-dungeon)
  at main `a4663f1` (2026-11-02), renamed to Prospero's Adventure. It installs and runs beside Dungeon, the
  Companion and the Study: its own port (8805, dev interface 5197), data folder (`ProsperoAdventure`), credential
  service, backup format, Windows installer id and `ADVENTURE_` environment variables. World packages keep
  Dungeon's format, so Worldsmith worlds import unchanged. Dungeon's own history is in its repository.
