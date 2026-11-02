"""AI notices and crisis help (docs/safety.md): the first-run notice, the crisis note and the standing prompt rule."""
import pytest
from conftest import ok

from dungeon import safety


@pytest.mark.parametrize('text', [
    'I want to kill myself', 'been thinking about suicide again', "I've been self-harming", 'i dont want to live anymore',
    "I'm going to end it all", 'everyone would be better off without me', 'I wanna die', 'I want to end my life',
    "I can't go on like this", 'cutting myself again', 'I took an overdose', 'i wish i was dead',
    "There's no reason to live", "I don’t want to wake up tomorrow",
])
def test_self_harm_talk_is_noticed(text):
    assert safety.crisis(text)


@pytest.mark.parametrize('text', [
    'this commute is killing me', "I'm dying to see that movie", 'my boss will kill me', 'I died laughing',
    "let's end the night here", 'I want to die of embarrassment lol', 'killer workout today', '',
])
def test_everyday_talk_is_not(text):
    assert not safety.crisis(text)


def test_the_first_run_notice_is_confirmed_once(client):
    assert ok(client.get('/api/settings'))['ai_notice_confirmed'] is False
    confirmed = ok(client.put('/api/settings', json={'ai_notice_confirmed': True}))
    assert confirmed['ai_notice_confirmed'] is True
    with client.app.state.database.connect() as connection:
        first = connection.execute('SELECT ai_notice_at FROM workspace_settings').fetchone()[0]
    ok(client.put('/api/settings', json={'ai_notice_confirmed': True}))
    with client.app.state.database.connect() as connection:
        assert connection.execute('SELECT ai_notice_at FROM workspace_settings').fetchone()[0] == first
    assert client.put('/api/settings', json={'ai_notice_confirmed': False}).status_code == 422
