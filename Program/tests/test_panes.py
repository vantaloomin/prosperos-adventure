"""System panes, written by code (adventure/rounds/panes.py)."""
from adventure.rounds import panes
from adventure.rounds.house_rules import Rulebook


def test_a_writers_pane_is_taken_out_and_codes_go_after_the_post():
    text = 'The door gave.\n\n```\n[ Status ]\nHealth: 3\n```\n\nShe went in.'
    assert panes.stripped(text) == 'The door gave.\n\nShe went in.'
    assert panes.stripped('No panes.') == 'No panes.'
    book = Rulebook(pane_title='== {title} ==', pane_row='{label} -> {value}')
    shown = panes.rolls(book, ['Hesk: d100 54 + 6 = 60: Success.', 'No label here.'])
    assert shown == '```\n== Rolls ==\nHesk -> d100 54 + 6 = 60: Success\n -> No label here\n```'
    assert panes.rolls(book, []) == ''
    assert panes.placed('She went in.\n', shown, '') == f'She went in.\n\n{shown}'
    assert panes.placed('She went in.', '') == 'She went in.'


def test_a_status_pane_holds_only_stats_entries(app):
    from adventure import sheet
    database = app.state.database
    with database.connect(write=True) as connection:
        assert panes.status(connection, Rulebook(), 'hesk', 'Hesk') == ''
        sheet.set_stats(connection, {'Luck': 12}, database.now(), actor='hesk')
        assert panes.status(connection, Rulebook(), 'hesk', 'Hesk') == '```\n[ Hesk ]\nLuck: 12\n```'
