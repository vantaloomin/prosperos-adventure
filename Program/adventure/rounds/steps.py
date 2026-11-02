"""Every module that plugs steps or commit hooks into the round loop (adventure/rounds/engine.py `register`,
`on_commit`), loaded once when the app starts (adventure/main.py). A part of the loop that registers steps adds its
module here, one line each, so nothing depends on which module happened to be imported first.
"""
from adventure.rounds import solo  # noqa: F401 - today's single-player turn, the 'solo' Resolving step
