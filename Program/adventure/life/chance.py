"""Seeded dice and outcome tables.

Copied from Prospero's Study (vantaloomin/prosperos-study at bbcbde49426bc86d2430c3a912472e05be4fd89a):
`Draws` is server/mechanics/randomness.py unchanged; `face` and `resolve` are TableSet.face and
TableSet.resolve from server/mechanics/table_engine.py, trimmed to plain dict tables (no table
versions, disabled tables or excluded rows). A row is {id, low, high, kind, child}; `kind` is
'event' or 'no_event', and `child` names a table to roll on next.

The same seed, stream and order of draws always give the same results, on any machine.
"""
import hashlib

ALGORITHM = "sha256-counter-rejection-v1"


class Draws:
    def __init__(self, seed):
        self.seed = seed
        self.counters = {}
        self.log = []

    def die(self, sides, stream, purpose):
        counter = self.counters.get(stream, 0)
        limit = (1 << 256) - ((1 << 256) % sides)
        while True:
            digest = hashlib.sha256(f"{ALGORITHM}:{self.seed}:{stream}:{counter}".encode()).digest()
            counter += 1
            number = int.from_bytes(digest, "big")
            if number < limit:
                break
        self.counters[stream] = counter
        result = number % sides + 1
        self.log.append({"stream": stream, "counter": counter, "purpose": purpose,
                         "sides": sides, "result": result})
        return result


def face(tables, table_id, draws, stream):
    """One row of a table, weighted by its range; None when the table is empty or unknown."""
    rows = sorted(tables.get(table_id, ()), key=lambda row: row["low"])
    if not rows:
        return None
    weight = sum(row["high"] - row["low"] + 1 for row in rows)
    draw = draws.die(weight, stream, table_id)
    for row in rows:
        width = row["high"] - row["low"] + 1
        if draw <= width:
            return row
        draw -= width
    raise AssertionError("Table has no result")


def resolve(tables, table_id, draws, stream) -> list[dict]:
    """The rows rolled from a table and its children, in order; empty on a no-event result."""
    chain = []
    while table_id:
        row = face(tables, table_id, draws, stream)
        if row is None or row["kind"] == "no_event":
            return []
        chain.append(row)
        table_id = row.get("child")
    return chain
