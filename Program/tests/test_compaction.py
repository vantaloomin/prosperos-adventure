"""Compaction that keeps what's live (adventure/compaction.py)."""
import asyncio

from conftest import Chunk, tell

from adventure import compaction, record


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


def test_what_a_fold_must_keep_is_its_names_numbers_and_pledges(app):
    database = app.state.database
    with database.connect(write=True) as connection:
        record.add(connection, 'fact', 'Mara', 'Mara keeps the ledger.', database.now())
        record.add(connection, 'fact', 'the bouncer', 'The bouncer works the door.', database.now())
        live = compaction.live(
            connection, 'You owe the tide-priest. "I will drown you myself," he said.',
            'The player: I pay Mara 40 crowns at 9:30. "I swear I will bring the rest," I say. "Nice boots," she says.')
    assert compaction.Kept('quote', 'I will drown you myself,') in live
    assert compaction.Kept('quote', 'I swear I will bring the rest,') in live
    # Small talk is not kept word for word; a name the record has is, and every number.
    assert not any(item.text.startswith('Nice boots') for item in live)
    assert compaction.Kept('name', 'Mara') in live and compaction.Kept('name', 'the bouncer') not in live
    assert {item.text for item in live if item.kind == 'number'} == {'40', '9:30'}


def test_a_summary_holds_a_number_in_words_and_a_quote_with_curly_marks():
    items = [compaction.Kept('number', '3'), compaction.Kept('quote', "I'll pay you back."),
             compaction.Kept('name', 'Mara'), compaction.Kept('number', '40')]
    text = 'mara owed three debts and said “I’ll pay you back” before dawn.'
    assert compaction.dropped(items, text) == [compaction.Kept('number', '40')]
    assert compaction.also('Short.', [compaction.Kept('number', '40'), compaction.Kept('quote', 'Never.')]) == \
        'Short.\n\nAlso kept: 40; "Never.".'


def test_a_second_draft_is_kept_only_when_it_drops_less():
    items = [compaction.Kept('name', 'Mara'), compaction.Kept('number', '40')]
    asked = []

    async def draft(note):
        asked.append(note)
        return 'Mara left.' if not note else 'Someone left.'

    answer, missing = asyncio.run(compaction.checked(draft, items))
    assert answer == 'Mara left.' and missing == [compaction.Kept('number', '40')]
    assert asked[1] == compaction.again([compaction.Kept('number', '40')])


def test_a_fold_that_drops_something_live_is_redrafted_and_what_it_still_drops_is_kept(client, connected, app,
                                                                                       provider, monkeypatch):
    monkeypatch.setattr(record, 'RECENT', 4)
    monkeypatch.setattr(record, 'FOLD', 2)
    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'fact', 'Mara', 'Mara keeps the ledger.', app.state.database.now())
    provider.replies = [reply('Mara counts the coins.'), reply('Narration 2.'), reply('Narration 3.'),
                        reply('You paid a debt.'), reply('You paid Mara 40 crowns.')]
    tell(client, 'I pay Mara 40 crowns. "I swear I will bring the rest by the new moon," I say.', 'story-0001')
    tell(client, 'Turn 2.', 'story-0002')
    tell(client, 'Turn 3.', 'story-0003')
    first, second = provider.requests[-2:]
    assert first['system'].startswith(record.SUMMARIZE) and 'Your last draft dropped' not in first['system']
    assert '- Mara\n- 40' in second['system'] and '- "I swear I will bring the rest by the new moon,"' in second['system']
    with app.state.database.connect() as connection:
        kept = record.summary(connection)['text']
    assert kept == 'You paid Mara 40 crowns.\n\nAlso kept: "I swear I will bring the rest by the new moon,".'


def test_a_summary_that_keeps_everything_is_asked_once(client, connected, app, provider, monkeypatch):
    monkeypatch.setattr(record, 'RECENT', 4)
    monkeypatch.setattr(record, 'FOLD', 2)
    provider.replies = [reply('The door opens.'), reply('Narration 2.'), reply('Narration 3.'),
                        reply('You knocked 3 times and the door opened.')]
    tell(client, 'I knock 3 times.', 'story-0001')
    tell(client, 'Turn 2.', 'story-0002')
    tell(client, 'Turn 3.', 'story-0003')
    assert provider.requests[-1]['system'].startswith(record.SUMMARIZE)
    assert sum(request['system'].startswith(record.SUMMARIZE) for request in provider.requests) == 1
    with app.state.database.connect() as connection:
        assert record.summary(connection)['text'] == 'You knocked 3 times and the door opened.'


def test_a_chapter_summary_keeps_what_its_hook_does_not(client, connected, app, provider):
    from adventure import chapters
    from adventure.text_models import config_for

    with app.state.database.connect(write=True) as connection:
        record.add(connection, 'fact', 'Pell', 'Pell runs the inn.', app.state.database.now())
        config = config_for(connection, record.JOB)
    lines = [{'role': 'user', 'text': 'I pay Pell 6 silver.', 'status': 'complete'},
             {'role': 'narrator', 'text': 'Pell bites the coin.', 'status': 'complete'}]
    provider.replies = [reply('{"title": "At the inn", "summary": "You paid for a room.", "hook": "Pell watches."}'),
                        reply('{"title": "At the inn", "summary": "You paid.", "hook": "Pell watches."}')]
    done = asyncio.run(chapters.summed(app.state, config, lines))
    # The hook names Pell; the number was dropped twice, so it is added after the summary.
    assert '- 6' in provider.requests[-1]['system'] and '- Pell' not in provider.requests[-1]['system']
    assert done == {'title': 'At the inn', 'summary': 'You paid for a room.\n\nAlso kept: 6.', 'hook': 'Pell watches.'}
