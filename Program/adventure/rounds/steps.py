"""Every module that plugs steps or commit hooks into the round loop (adventure/rounds/engine.py `register`,
`on_commit`), loaded once when the app starts (adventure/main.py). A part of the loop that registers steps adds its
module here, one line each, so nothing depends on which module happened to be imported first.
"""
from adventure.rounds import (
    author,  # noqa: F401 - the Author's nudges, the beat board and their feedback
    context,  # noqa: F401 - who sees what: the 'privacy' Gathering step
    converse,  # noqa: F401 - Converse and the reply card
    corrections,  # noqa: F401 - corrected and struck memories, read through recall (memory.amend)
    declare,  # noqa: F401 - the agents: pick, declare, lies heard, react, feelings
    directing,  # noqa: F401 - the director's warning signs, and signs before a betrayal
    joining,  # noqa: F401 - an agent asked along answers for themselves
    modes,  # noqa: F401 - who plays the user's character outside Play
    offpage,  # noqa: F401 - off-page beats in a round with agents, and their commit
    report,  # noqa: F401 - the house rules frozen at Gather, the Reviewer and the scan after the Writer
    telling,  # noqa: F401 - today's turn as steps, and the party's Resolve (resolve.py)
    timing,  # noqa: F401 - lore timers counted in rounds
    travelling,  # noqa: F401 - the lead's travel line, and who splits off
    watch,  # noqa: F401 - what Watch's big moments are found against
    writer,  # noqa: F401 - the round Writer, in place of today's 'write' in a turn with agents
)
