"""Every module that plugs steps or commit hooks into the round loop (adventure/rounds/engine.py `register`,
`on_commit`), loaded once when the app starts (adventure/main.py). A part of the loop that registers steps adds its
module here, one line each, so nothing depends on which module happened to be imported first.
"""
from adventure.rounds import (
    author,  # noqa: F401 - the Author's nudges, the beat board and their feedback
    converse,  # noqa: F401 - Converse and the reply card
    declare,  # noqa: F401 - the agents: pick, declare, lies heard, react, feelings
    modes,  # noqa: F401 - who plays the user's character outside Play
    offpage,  # noqa: F401 - off-page beats in a round with agents, and their commit
    telling,  # noqa: F401 - today's turn as steps, and the party's Resolve (resolve.py)
    watch,  # noqa: F401 - what Watch's big moments are found against
)
