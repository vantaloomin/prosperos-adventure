
from dungeon.in_character import applies, breaks, clean


def test_ai_denials_are_recognized():
    for line in ("As an AI, I don't have feelings.", "I'm just an AI language model.", "I'm not a real person.",
                 "I don't have a physical body.", "I was created by OpenAI.", "I’m not a human being.",
                 "That's against my programming.", "Let's get back to our roleplay.",
                 "I don't have access to real-time weather data.", "((Sorry, the lookup failed.",
                 "So I can't say.)) "):
        assert breaks(line), line


def test_ordinary_lines_are_left_alone():
    for line in ("I'm an AI researcher at the lab.", "As an AI engineer, I debug models all day.",
                 "I'm a software engineer.", "I'm not a real fan of jazz.", "I'm not real sure about that.",
                 "I don't have feelings for him.", "That was so out of character for her.",
                 "My programming class ran late.", "He's such a bot about it lol", "(Sorry (I mean it).)"):
        assert not breaks(line), line


def test_only_the_breaking_sentence_is_removed():
    text = "Hey you! As an AI, I can't actually see you. But tell me about your day.\n\nWhat did you eat?"
    assert clean(text) == "Hey you! But tell me about your day.\n\nWhat did you eat?"


def test_out_of_character_questions_and_artificial_characters_are_not_filtered():
    assert not applies('OOC: which model are you?', {})
    assert not applies('((are you Claude?))', {})
    assert not applies('hi', {'identity': 'An android who runs a night-shift diner'})
    assert applies('are you even real?', {'identity': 'A nurse in Lisbon'})


def test_a_caption_tag_echoed_from_the_photo_note_is_removed():
    reply = '[image: Megan Lawson had a busy shift, with one rush after another.]\nJust got off work! You?'
    assert clean(reply) == 'Just got off work! You?'
