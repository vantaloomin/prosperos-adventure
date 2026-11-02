"""The dice log (requirements "Play screen and widgets": dice log; "Each turn has a time budget": how long each step
took is shown in the dice log).

Every roll of the branch being played, turn by turn, newest first, with how long each turn took and what gave way
for time (dungeon/pace.py), and a tally of how the rolls landed. Only while the dice are shown: hidden dice never
leave the app.
"""
from dungeon import pace, timeline, turn
from dungeon.database import decode, many

MOST_TURNS = 200
LANDED = ('success_cost', 'success', 'critical_success')


def log(connection, shown: bool) -> dict:
    if not shown:
        return {'shown': False, 'turns': [], 'tally': None}
    where, values = timeline.visible(connection)
    lines = many(connection, f"SELECT id, seq, text FROM story_messages WHERE {where} AND role='user' "
                             'ORDER BY seq DESC LIMIT ?', (*values, MOST_TURNS))
    turns = []
    for line in lines:
        rolls = [turn.shown(row) for row in turn.saved(connection, line['id'])]
        steps = decode(pace.saved(connection, line['id']) or 'null')
        if rolls or steps:
            turns.append({'id': line['id'], 'seq': line['seq'], 'line': line['text'], 'rolls': rolls, 'pace': steps})
    rolled = [roll for item in turns for roll in item['rolls']]
    tally = {band: sum(roll['band'] == band for roll in rolled) for band in {roll['band'] for roll in rolled}}
    return {'shown': True, 'turns': turns,
            'tally': {'rolls': len(rolled), 'landed': sum(roll['band'] in LANDED for roll in rolled), 'bands': tally}}
