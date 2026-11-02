# Changelog

## Unreleased

- **Lore that not everyone knows.** A lore entry can be public, known to some characters, or GM only, and the narrator reads only public lore. Untagged lore stays public. A world package's hidden truths and its cast's secrets count as GM only or known to the characters they belong to, never public, and the world importer names any visibility tag it cannot read.
- **Agents in Settings > Models.** A new Agents role picks the model the agent characters think with (the Default without one), and a character can have a model of its own. The agents' preset (Quick and cheap, Balanced, Rich and slow, each with an estimate of calls and tokens a turn), how much they scheme, how fast their loyalties shift and a spend cap for the session are kept per campaign, ready for the cast and settings screens.
- **World pitches on hover.** Hovering or focusing a world on the title screen floats its pitch over the art in a frosted card above the name, which stays put.
- **Plainer model settings.** Models, Decisions and Recall are each a heading and an Add button, without the explanations above them. The computer report shows only when a chosen local model won't fit, and the job picker is called Roles.
- **A calmer play screen.** The scene is one line: the place (tap it to go somewhere else), the time and how you are. The composer is the message box and Send; Ideas, the author's note, stepping out of the story, every panel view and starting a new story are in a menu (the button beside the box, or ⌘K / Ctrl+K). The panel opens on who's here: you first, then the people met at this place, each opening to show more, with who else is around and the weather under them. The Scene, Sheet, Pack, Journal and More tabs are gone. "Characters are AI and can make mistakes" stays under the box.
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
