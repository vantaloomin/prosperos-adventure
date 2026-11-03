"""The draft scan (adventure/rounds/scan.py): hard failures never reach the record, soft warnings are reported, and
every draft gets a word count and a density read."""
import asyncio

from adventure.narration.prose import HARD, STRONG, WATCH
from adventure.rounds import scan
from adventure.rounds.house_rules import Rulebook

BOOK = Rulebook(words=('suddenly',), phrases=('a beat passed',), punctuation=('em dash', '!'))
PANE = '```\n[ Status ]\nHealth: 8 of 20\nGold: 12\n```'


def kinds(found, severity=None):
    return [item.kind for item in found.findings if severity is None or item.severity == severity]


def test_house_rules_broken_are_hard_failures():
    found = scan.scan('Elara crossed the yard — fast. Suddenly the gate banged! A beat passed. She took 12 damage '
                      'and rolled a natural 20.', BOOK)
    assert kinds(found, HARD) == ['em-dash', 'punctuation', 'outlawed-word', 'outlawed-phrase', 'outlawed-name',
                                  'game-number', 'dice']
    assert not found.clean


def test_canon_names_panes_and_ordinary_numbers_pass():
    text = (f'Thorne counted nothing. The bell rang at 9:30 in 1887, and the rain came on.\n\n{PANE}\n\n'
            '"Twelve crowns, or 12 if you like," Thorne said. "Who asked?"')
    found = scan.scan(text, BOOK, canon='Thorne Blackwood')
    assert found.clean and 'outlawed-name' not in kinds(found) and 'number' not in kinds(found)
    # Without the world holding the name, it is outlawed.
    assert 'outlawed-name' in kinds(scan.scan(text, BOOK))


def test_lifting_a_rule_lifts_its_check():
    text = 'She ran — hard. Suddenly it rained.'
    assert scan.scan(text, Rulebook(punctuation=())).clean
    assert kinds(scan.scan(text, Rulebook()), HARD) == ['em-dash']


def test_soft_warnings_are_reported_not_failed():
    found = scan.scan("You open the door. You see Hesk. She thinks *not again*. Seventeen of 40 is plenty. "
                      'It was only the beginning.', Rulebook(pov='third'))
    assert found.clean
    assert {'pov', 'thoughts', 'number', 'length'} <= set(kinds(found, WATCH))
    assert kinds(found, STRONG) == ['summing-up']
    report = found.report()
    assert report['words'] == found.words and {'kind', 'severity', 'text', 'hint'} == set(report['findings'][0])


def test_thoughts_are_checked_against_the_house_way():
    text = "She frowned. '*Not again.*' Then *never*."
    assert [item.text for item in scan.thoughts(text, Rulebook())] == ['*never*']
    assert [item.text for item in scan.thoughts(text, Rulebook(thoughts='italics'))] == ["'*Not again.*'"]
    assert len(scan.thoughts(text, Rulebook(thoughts='plain'))) == 2


def test_lines_the_players_character_never_declared_run_past_the_stop_point():
    stop = scan.Stop('Mara Quell', 'I tell the guard I am here for the auction.')
    said = ('"I am here for the auction," you say.\n\n'
            '"And I will burn this whole place to the ground tonight," you add, and draw your knife.')
    found = scan.past_stop(said, stop, 'second')
    assert [item.text for item in found] == ['And I will burn this whole place to the ground tonight,']
    third = '"Then we burn the granary at dawn and take the boats," Mara said.'
    assert scan.past_stop(third, stop, 'third') and not scan.past_stop(third, None, 'third')
    assert not scan.past_stop('"Then we burn the granary at dawn," Hesk said.', stop, 'third')


def test_word_count_and_density():
    found = scan.scan('"Who\'s there?" she asked.\n\nThe rain kept on, hard and steady, over the yard.', Rulebook())
    assert found.words == 14
    assert found.density['paragraphs'] == 2 and 0 < found.density['dialogue'] < 0.5
    assert found.density['read'] == 'sparse'


def test_a_hard_failure_is_rewritten_and_scanned_again():
    asked = []

    async def rewrite(system, messages):
        asked.append((system, messages))
        return 'Mara crossed the yard, fast. The gate banged. She stood very still and listened to the rain.'

    settled = asyncio.run(scan.settle('Mara crossed the yard — fast. Suddenly the gate banged! She stood very '
                                      'still and listened.', BOOK, rewrite))
    assert settled.scan.clean and settled.rewrites == 1 and settled.cut == ()
    assert settled.text.startswith('Mara crossed the yard, fast.')
    assert '## House rules' in asked[0][0] and 'suddenly' in asked[0][0]
    assert 'outlawed-word: "Suddenly"' in asked[0][1][0]['content']


def test_what_two_rewrites_leave_code_fixes_and_the_cut_is_reported():
    calls = []

    async def stubborn(system, messages):
        calls.append(1)
        return messages[0]['content'].split('Narration:\n\n')[1].split('\n\nFix these:')[0]

    text = f'Suddenly the gate banged! The rain kept on.\n\n{PANE}\n\n"Who is there?" Hesk asked.'
    settled = asyncio.run(scan.settle(text, BOOK, stubborn))
    assert len(calls) == scan.REWRITES and settled.scan.clean
    assert settled.cut == ('Suddenly the gate banged.',)
    assert settled.text == f'The rain kept on.\n\n{PANE}\n\n"Who is there?" Hesk asked.'


def test_with_no_rewrite_or_a_failing_one_the_draft_is_still_fixed():
    async def broken(system, messages):
        raise RuntimeError('no model')

    for rewrite in (None, broken):
        settled = asyncio.run(scan.settle('She ran — hard. It rolled a natural 20 on the floor. Then quiet.',
                                          Rulebook(), rewrite))
        assert settled.scan.clean and settled.rewrites == (0 if rewrite is None else 1)
        assert settled.text == 'She ran, hard. Then quiet.' and settled.cut == ('It rolled a natural 20 on the floor.',)


def test_a_strong_tell_gets_one_rewrite_and_then_stands():
    calls = []

    async def same(system, messages):
        calls.append(1)
        return 'The fire burned low. It was only the beginning.'

    settled = asyncio.run(scan.settle('The fire burned low. It was only the beginning.', Rulebook(), same))
    assert len(calls) == 1 and settled.scan.clean and kinds(settled.scan, STRONG) == ['summing-up']
