"""The narrator's layered prompt and the checks on what it writes (dungeon/narration)."""
import asyncio

from dungeon.narration import prompt, prose


def test_the_prompt_is_layered_with_the_turn_last():
    text = prompt.system(prompt.CORE, prompt.CRAFT, scene='## Scene\nPlace: the Gilded Eel.',
                         persona='Kael, a debt collector with a bad knee.', persona_name='Kael',
                         outcomes=[{'actor': 'Kael', 'action': 'taunt the demon', 'band': 'success_cost',
                                    'detail': 'He loses his footing; the code marked a sprained wrist.'}])
    order = [text.index(part) for part in ('tabletop roleplaying game for adults', 'Never write:',
                                           'close third person on Kael, past tense', 'Intensity:',
                                           "## The player's character", '## Scene', '## This turn')]
    assert order == sorted(order)
    assert '- Kael tries to taunt the demon: succeeds, at a real cost. He loses his footing' in text
    assert 'Rolls are hidden: never mention dice' in text


def test_the_prompt_itself_has_no_em_dashes_and_no_strong_tells():
    for text in (prompt.CORE, prompt.CRAFT, prompt.CRAFT_COMPACT):
        assert not prose.DASH.search(text)
    assert not prose.needs_rewrite(prose.check(prompt.CORE))


def test_small_models_get_the_compact_craft_and_the_settings_read_plainly():
    assert prompt.craft_for(8192) == prompt.CRAFT_COMPACT and prompt.craft_for(128_000) == prompt.CRAFT
    assert prompt.craft_for(None, 'edited') == 'edited'
    assert len(prompt.CRAFT_COMPACT) < len(prompt.CRAFT) / 3
    text = prompt.Intensity(levels={'violence': 3, 'sex': 0}, veils=('sexual violence',), voice='grim').text()
    assert '- Violence: unflinching' in text and '- Sex: off the page' in text
    assert '- Veiled: sexual violence.' in text and 'Voice: grim.' in text
    assert prompt.Format('second', 'present', 'short').text(None).startswith(
        'Narration: second person, addressing the player\'s character as "you", present tense, about 150')
    assert 'Rolls are shown' in prompt.outcomes_text([{'actor': 'Kael', 'action': 'jump', 'band': 'failure'}], True)


def test_em_dashes_in_every_form_are_found_but_ranges_and_game_windows_are_not():
    for text in ('She stopped—then ran.', 'She stopped -- then ran.', 'She stopped - then ran.',
                 'She stopped – then ran.', 'She stopped―then ran.'):
        assert [finding.kind for finding in prose.check(text)] == ['em-dash'], text
    assert prose.check('It cost 3–4 silver. A well-worn blade.') == []
    assert prose.check('```\n[Quest] -- Find the key --\n```\nShe ran.') == []


def test_the_mechanical_fix_leaves_no_dash():
    text = 'The door gave—barely—and Kael shoved through.\n"Wait—"\nHe was not listening -- not now—\n—Run.'
    fixed = prose.without_dashes(text)
    assert not prose.DASH.search(fixed)
    assert fixed == 'The door gave, barely, and Kael shoved through.\n"Wait..."\nHe was not listening, not now...\nRun.'


def test_strong_tells_and_hard_dialogue_rules_are_found_but_literal_words_only_watched():
    text = ('A shiver ran down her spine. She noted the blade. And in that moment, she understood.\n\n'
            '"It\'s easier to see from here," Mira said.\n\n"It is easier to see," he said.\n\n'
            'He told her that the road was closed. The merchant opened his ledger.')
    found = {finding.kind: finding.severity for finding in prose.check(text)}
    assert found['stock-intimacy'] == found['thinking-tic'] == found['scene-closer'] == prose.STRONG
    assert found['echo'] == found['reported-speech'] == prose.STRONG
    assert found['watch-word'] == prose.WATCH


def test_ritual_repeats_and_one_speakers_own_words_are_not_echoes():
    assert prose.echoes('"Amen."\n\n"Amen."') == []
    assert prose.echoes('"I came back for the money," he said. "Came back for the money, nothing else."') == []


def test_more_than_four_bare_lines_is_ping_pong():
    bare = '\n\n'.join(f'"Line {number}."' for number in range(5))
    assert [finding.kind for finding in prose.ping_pong(bare)] == ['ping-pong']
    assert prose.ping_pong('\n\n'.join(f'"Line {number}."' for number in range(4))) == []


def polish(text, replies):
    asked = []

    async def rewrite(system, messages):
        asked.append((system, messages))
        return replies.pop(0)
    return (*asyncio.run(prose.polish(text, rewrite)), asked)


def test_a_rewrite_is_used_when_it_fixes_the_tells():
    draft = 'Kael kicked the door open—hard. A shiver ran down her spine as the room went quiet around them.'
    text, findings, asked = polish(draft, ['Kael kicked the door open, hard. Mira went still at the bar, one hand '
                                           'flat on the wood.'])
    assert text.startswith('Kael kicked the door open, hard.') and findings == []
    system, messages = asked[0]
    assert system == prose.REWRITE and 'em-dash' in messages[0]['content'] and 'stock-intimacy' in messages[0]['content']


def test_a_rewrite_that_runs_short_is_ignored_and_dashes_still_go():
    draft = 'Kael kicked the door open—hard. The room went quiet around them, and the fire guttered low in the grate.'
    text, findings, _ = polish(draft, ['Door opened.'])
    assert text == 'Kael kicked the door open, hard. The room went quiet around them, and the fire guttered low ' \
                   'in the grate.' and findings == []


def test_with_the_rewrite_off_only_the_dashes_are_fixed():
    text, findings = asyncio.run(prose.polish('She stopped—the blade was old. She noted it twice.'))
    assert text == 'She stopped, the blade was old. She noted it twice.'
    assert [finding.kind for finding in findings] == ['thinking-tic']


def test_a_failed_rewrite_keeps_the_draft():
    async def broken(_system, _messages):
        raise RuntimeError('model offline')
    text, _ = asyncio.run(prose.polish('A shiver ran down her spine—again.', broken))
    assert text == 'A shiver ran down her spine, again.'

