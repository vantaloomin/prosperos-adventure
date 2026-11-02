"""The playtest scenarios, played as a player would.

Each is a function of a `Play` (playtest.py), registered in SCENARIOS by name. Lines are what a player types;
`expect` adds checks. Dungeon's single-player scenarios were not carried over: Adventure's own (agents, the
Writer, Play, Author and Watch) are added here as those parts are built.
"""

SCENARIOS = {}
