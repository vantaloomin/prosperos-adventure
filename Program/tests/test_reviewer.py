"""The Reviewer (adventure/rounds/reviewer.py): a second reader's notes, kept only when their quote is in the draft,
then applied or declined by the Writer; a Reviewer that fails leaves the draft as it was."""
import asyncio
import json

from adventure.rounds import reviewer
from adventure.rounds.contract import Brief
from adventure.rounds.house_rules import Rulebook

DRAFT = ('Hesk set the cup down. "Fine," she said. "Fine, fine."\n\nThe rain went on against the shutters, and '
         'Mara told her that she would pay.')


def replying(*replies):
    asked = []

    async def complete(system, messages):
        asked.append((system, messages))
        reply = replies[len(asked) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)
    return complete, asked


def test_the_reviewer_reads_the_rules_the_brief_and_the_story_so_far_and_only_quotes_from_the_draft():
    notes = {'notes': [{'quote': 'Mara told her that she would pay', 'problem': 'Reported speech.',
                        'fix': 'Quote what Mara says.'},
                       {'quote': 'a line that is not there', 'problem': 'x', 'fix': 'y'},
                       {'quote': 'Fine, fine.', 'problem': 'A tic.', 'fix': ''}, 'not a note']}
    complete, asked = replying('Here you go:\n```json\n' + json.dumps(notes) + '\n```')
    brief = Brief(beats=['A storm breaks.'], stop_point='Before Mara answers the offer.')
    found = asyncio.run(reviewer.review(complete, Rulebook(rulings=('Hesk never drinks.',)), brief, DRAFT,
                                        ['Earlier post one.', 'Earlier post two.']))
    assert found == [{'quote': 'Mara told her that she would pay', 'problem': 'Reported speech.',
                      'fix': 'Quote what Mara says.'}]
    system, messages = asked[0]
    assert '## House rules' in system and 'Hesk never drinks.' in system and 'Intensity:' in system
    assert '- A storm breaks.' in system and 'Before Mara answers the offer.' in system
    assert 'Earlier post two.' in messages[0]['content'] and messages[0]['content'].endswith(DRAFT)


def test_a_failing_or_unreadable_reviewer_leaves_no_notes():
    for reply in (RuntimeError('timeout'), 'I think it is great!', '{"notes": "none"}'):
        complete, _ = replying(reply)
        assert asyncio.run(reviewer.review(complete, Rulebook(), None, DRAFT, [])) == []


def test_the_writer_applies_or_declines_each_note():
    notes = [{'quote': 'Mara told her that she would pay', 'problem': 'Reported speech.', 'fix': 'Quote her.'},
             {'quote': 'Fine, fine.', 'problem': 'A tic.', 'fix': 'Cut the repeat.'}]
    revised = DRAFT.replace('Mara told her that she would pay', '"You\'ll pay for this," Mara said')
    complete, asked = replying({'text': revised, 'declined': [{'quote': 'fine, fine.', 'reason': 'It is her tic.'}]})
    text, outcome = asyncio.run(reviewer.apply(complete, Rulebook(), DRAFT, notes))
    assert text == revised
    assert [(item['applied'], item['reason']) for item in outcome] == [(True, ''), (False, 'It is her tic.')]
    assert '1. "Mara told her that she would pay": Reported speech. Fix: Quote her.' in asked[0][1][0]['content']


def test_a_revision_that_summarises_or_fails_is_not_used():
    notes = [{'quote': 'Fine, fine.', 'problem': 'A tic.', 'fix': 'Cut it.'}]
    for reply in ({'text': 'Short.'}, RuntimeError('down'), 'not json'):
        complete, _ = replying(reply)
        text, outcome = asyncio.run(reviewer.apply(complete, Rulebook(), DRAFT, notes))
        assert text == DRAFT and outcome[0]['applied'] is False and outcome[0]['reason'] == 'Kept as written.'
    assert asyncio.run(reviewer.apply(None, Rulebook(), DRAFT, [])) == (DRAFT, [])


def test_the_reviewer_is_on_in_rich_and_slow_and_a_toggle_elsewhere():
    assert reviewer.enabled({'preset': 'rich'}) and not reviewer.enabled({'preset': 'balanced'})
    assert reviewer.enabled({'preset': 'quick', 'reviewer': True})
    assert not reviewer.enabled({'preset': 'rich', 'reviewer': False}) and not reviewer.enabled({})
