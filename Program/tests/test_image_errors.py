from dungeon.images import content
from dungeon.images.adapters.hosted import said


def test_withheld_picture_says_why():
    reason = 'its words name Ada, a child in the circle, and children are never pictured'
    found = content.classify({'withheld': True, 'withheld_reason': reason})
    assert found.tier == content.PROHIBITED and found.reasons == [reason]
    assert content.classify({'withheld': True}).reasons == ['not something to picture']


def test_provider_error_is_shown_in_its_own_words():
    assert said('{"error": {"message": "Model is overloaded", "code": 503}}') == \
        ' The provider said: "Model is overloaded"'
    assert 'Upstream refused' in said('{"error": {"message": "Provider returned error", "metadata": '
                                      '{"raw": "Upstream refused"}}}')
    assert said('{"detail": "Bad size"}') == ' The provider said: "Bad size"'
    assert said('<html><body>502</body></html>') == ''
    assert said('') == ''


def test_provider_error_never_shows_a_key():
    shown = said('{"error": {"message": "Incorrect API key provided: sk-or-v1-abcdef1234567890abcdef"}}')
    assert 'abcdef1234567890' not in shown and '[hidden]' in shown
