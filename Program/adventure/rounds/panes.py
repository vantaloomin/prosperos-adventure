"""System panes, written by code (docs/spec.md "Numbers, System panes and who can see them": "Numbers live in panes").

Numbers appear on the page only in the house System pane format (adventure/rounds/house_rules.py `pane`), generated
by code from what the game decided, so every number on the page traces to a roll or a stats entry:

- The Writer never writes a pane (the house rules tell it so). One it writes anyway is taken out at the start of the
  checks (adventure/rounds/report.py `checks`), since its numbers trace to nothing.
- After the scan, code adds a "Rolls" pane from the brief's math (adventure/rounds/resolve.py `math_line`, kept in
  step with any override), when the Table shows the odds: the same switch that puts numbers in the turn report.
- `status` is a character's stats as a pane, from `character_stats`, for any step that shows them.

Whether a reader may see panes at all is a fact about the people they are (W1's game-knowledge flag); until that
flag exists, the Table's odds switch decides.
"""
from adventure import sheet
from adventure.rounds import scan
from adventure.rounds.house_rules import Rulebook, pane

ROLLS = 'Rolls'


def stripped(text: str) -> str:
    """The post without any pane in it, the blank lines it leaves closed up."""
    if not scan.PANE.search(text):
        return text
    parts = [part.strip() for part in scan.PANE.split(text)]
    return '\n\n'.join(part for part in parts if part)


def row(line: str) -> tuple[str, str]:
    """A math line ("Hesk: d100 54 + 6 = 60: Success.") as a pane row: who, then the arithmetic."""
    label, _, value = line.partition(': ')
    return (label, value.rstrip('.')) if value else ('', line.rstrip('.'))


def rolls(book: Rulebook, math: list[str]) -> str:
    """The turn's rolls as a pane; empty when nothing was rolled."""
    return pane(book, ROLLS, [row(line) for line in math]) if math else ''


def status(connection, book: Rulebook, actor: str, title: str) -> str:
    """A character's stats as a pane, every value from their stats entries; empty when they have none."""
    values = sheet.stats(connection, actor)
    return pane(book, title, [(stat, str(value)) for stat, value in values.items()]) if values else ''


def placed(text: str, *panes: str) -> str:
    """The post with code's panes after it."""
    shown = [item for item in panes if item]
    return '\n\n'.join([text.rstrip(), *shown]) if shown else text
