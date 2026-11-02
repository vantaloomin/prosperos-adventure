# Changelog

## Unreleased

- **One cast page.** "Who are you?" and "How this campaign plays" are one page: the town's people as a grid, tap one to play them and read who they are, or + to make your own; Rules, Tone (As written, Gentler, Harsher) and Begin at the foot. Ironman, an earlier story and how far you can rise sit behind Options; the finer tone, narration and dice choices start from the preset and your last campaign and change in play under Tone and rules.
- **A quieter start.** The first-run notice is one line over the title art ("Everyone here is AI"), the 18-or-older box, a Safety link and Enter; the rest is on the Safety page. Worlds are one sideways row of key art, most recently played first, with a + tile that opens the world packages. Without a text model, Send reads "Add a model" and opens Settings > Models instead of a banner.
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
- **Cleanup after the fork:** Dungeon's design notes (requirements, roadmap, Life Cards) are no longer copied here;
  code comments point to them in Dungeon's repository. The playtest runner stays, without Dungeon's single-player
  scenarios. The carry-over that kept Haddon Harbor for worlds made before it was retired is gone, since no
  Adventure world was ever set there.
