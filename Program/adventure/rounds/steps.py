"""Every module that plugs steps or commit hooks into the round loop (adventure/rounds/engine.py `register`,
`on_commit`), loaded once when the app starts (adventure/main.py). A part of the loop that registers steps adds its
module here, one line each, so nothing depends on which module happened to be imported first.
"""
from adventure.rounds import (
    context,  # noqa: F401 - who sees what: the 'privacy' Gathering step
    converse,  # noqa: F401 - Converse and the reply card
    declare,  # noqa: F401 - the agents: pick, declare, lies heard, react, feelings
    solo,  # noqa: F401 - today's single-player turn, the 'solo' Resolving step
)
