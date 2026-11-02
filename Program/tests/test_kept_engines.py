"""Engines kept from Companion for later milestones (M0): the odds engine and the Life Cards deck. They have no
callers yet, so these tests keep them working until the story uses them."""
from dungeon import consequences
from dungeon.life import deck


def test_the_odds_sum_to_one_and_a_rule_that_matches_moves_its_option():
    choice = 'storyline:friend_new_job:1'
    names = {'name': 'You', 'a': 'Ana'}
    plain = consequences.odds(choice, {}, names)
    close = consequences.odds(choice, {'closeness_a': 5}, names)
    assert abs(sum(item['odds'] for item in plain) - 1) < 0.01
    assert close[0]['odds'] > plain[0]['odds'] and close[0]['moves'] == ['more']
    assert close[0]['reasons'] == ['You is close to Ana and keeps telling them to go for it']
    # The same seed always lands on the same option.
    assert consequences.roll('seed', close) == consequences.roll('seed', close)
    assert consequences.roll('seed', close) in (0, 1)


def test_a_card_is_drawn_by_seed_and_only_from_what_is_allowed():
    found, share = deck.draw('day-1', 3, set(), set(), forced=True)
    assert found is not None and 0 < share <= 1 and found['drama'] <= 3
    assert deck.draw('day-1', 3, set(), set(), forced=True) == (found, share)
    assert all(item['drama'] <= 0 and not item['needs'] for item in deck.eligible(0, set(), set()))
    assert deck.card(found['id']) == found
