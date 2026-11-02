"""The round loop: several minds declare, react and talk, code resolves, the Writer writes (docs/spec.md).

- contract.py: the shapes every step shares (states, modes, seats, declarations, knowledge, snapshot, result, events)
- engine.py: the state machine and the step registry each part of the loop plugs into
- draft.py: the turn draft, the only thing a turn writes before Commit
- turns.py: turns as rows, with their snapshot and draft saved after every step
- memory.py: each character's memory and feelings, keyed by turn and read through the branch's ancestry
- seats.py: who sits at the table and how each decides; the mode and caps
- converse.py: the talk inside a turn: the Writer picks who asks whom, each asker's own agent writes the question
- reply.py: the reply card, when someone addresses the user's character and the turn waits on their answer
- writer.py: the Writer's calls, reading only the Writer's context for the mode
- queue.py: one writer per world, stale commands refused, Cancel at once
- play.py: Next in Author and Watch, the reply card, re-asking an agent, picking up after a restart
- steps.py: every module that registers steps, loaded once at startup (add yours there)
- solo.py: today's single-player turn, run as one step of the loop until its pieces are steps of their own

The API is adventure/round_routes.py.
"""
