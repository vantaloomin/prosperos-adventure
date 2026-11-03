"""Lore timers in agent play (docs/spec.md "Timing": "Lore timers and off-page beats count rounds").

Dungeon counts the player's lines. Every round opens on a line of its own in every mode (adventure/rounds/play.py), so
a round is one line on the lore's clock and switching modes never changes when lore lingers or rests. At Gather the
round's line and what its timers say are frozen with the snapshot (`settings['lore']`: lingering entries, which come
in keyword or not, and held ones, resting, waiting or missing their chance on this line's dice), for the context
builders' lore (adventure/rounds/context.py). At Commit the timed entries the round brought up (in the player's line
or the post) start their timers (adventure/lore.py `remember`). The clock is the story's lines on the branch, so going
back rewinds it, and chance stays seeded by branch and line. Today's single-player turn keeps its own timing (adventure/story.py).

Off-page beats count rounds through their own commit hook (adventure/rounds/offpage.py).
"""
from adventure import lore, timeline
from adventure.database import one
from adventure.rounds import engine
from adventure.rounds.contract import State
from adventure.rounds.solo import SOLO


def line_of(connection, seq: int) -> int:
    """Which line on the branch being played the round's opening line is, counting from 1."""
    where, values = timeline.visible(connection)
    return one(connection, f"SELECT COUNT(*) AS n FROM story_messages WHERE {where} AND role='user' AND seq<=?",
               (*values, seq))['n']


async def frozen(turn: engine.Turn):
    """Gathering: the round's place on the lore's clock."""
    with turn.database.connect() as connection:
        turn.snapshot.settings['lore'] = lore.round_timing(connection, line_of(connection, turn.row['seq']),
                                                           turn.row['branch_id'])


def committed(connection, turn: engine.Turn):
    """The timed entries the round brought up start their timers; a solo turn starts its own."""
    timing = turn.snapshot.settings.get('lore')
    if not timing or SOLO in turn.draft.extra:
        return
    said = str(turn.snapshot.settings.get('said') or '')
    lore.remember(connection, lore.started_in(connection, f'{said}\n{turn.draft.post}', timing), timing['line'])


engine.register(State.GATHERING, 'lore_timers', frozen, after='pick')
engine.on_commit('lore_timers', committed)
