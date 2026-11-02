"""The companion is nudged when their last replies keep reaching for the same words."""

from dungeon.memory import phrases

REPLIES = ['Honestly the ER was a zoo.', 'Ugh, honestly I need a nap.', 'That movie was honestly great!',
           'Christina is coming over, honestly so excited.', 'We could try the new taco place, honestly.',
           'I told Christina about it. Total chaos at work again.', 'My shift ran late, total chaos at work again.',
           'Pizza tonight? Total chaos at work again.', 'Gym was packed.', 'Saw Christina at lunch.',
           'Reading on the couch.']


def passages(texts):
    return [{'id': f'm{index}', 'text': text} for index, text in enumerate(texts)]


def test_a_repeated_phrase_and_a_filler_word_are_named():
    found = {item['phrase']: item for item in phrases.detect(passages(REPLIES))[0]}
    assert found['total chaos at work again']['passage_count'] == 3
    words = {item['phrase'] for item in phrases.filler(passages(REPLIES))}
    # A name written capitalized mid-sentence is never a habit; neither is an ordinary word.
    assert words == {'honestly'}
    assert phrases.repeats_line(passages(REPLIES)) == (
        'You keep repeating: "honestly" (5 of your last 11 messages), "total chaos at work again" (3 of your last '
        '11 messages). Say it differently.')


def test_varied_replies_get_no_nudge():
    texts = ['Long shift, but we saved someone.', 'Pizza tonight?', 'My sister called.', 'Rain again!',
             'Reading on the couch.', 'Gym was packed.']
    assert phrases.repeats_line(passages(texts)) is None
    assert phrases.repeats_line(passages(['Honestly, chaos.'] * 4)) is None
