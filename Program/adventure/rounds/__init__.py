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
- offpage.py: off-page beats in a round: code draws them, an offscreen agent writes its own lines, Commit writes them
- queue.py: one writer per world, stale commands refused, Cancel at once
- play.py: Next in Author and Watch, the reply card, re-asking an agent, picking up after a restart
- steps.py: every module that registers steps, loaded once at startup (add yours there)
- solo.py: a player's line played as a turn of the loop (send, retry)
- telling.py: today's turn as the loop's steps (Gather, Resolve, Write, Commit)
- resolve.py: every character's risky acts rolled by code, the one question on ambiguity, the TurnResult and brief
- house_rules.py: the campaign's house rulebook as data, and the user's rulings, applied from their turn forward
- scan.py: the draft scan every Writer post passes before Commit, with the fixes code makes when a rewrite can't
- reviewer.py: a second reader's notes on the draft, applied or declined by the Writer
- report.py: the checks at the end of Writing, the turn report and the status line
- corrections.py: turn-keyed patches to a committed turn, and struck inventions

The API is adventure/round_routes.py.
"""
