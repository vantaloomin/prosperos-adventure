"""The pastimes catalogue and milestone banks (dungeon/world/data/hobbies/): enough specific milestones for every
hobby at every level in every era it belongs to, in words that fit the app's rules."""
import json
import re
from pathlib import Path

import pytest

BANKS = Path(__file__).resolve().parents[1] / 'dungeon' / 'world' / 'data' / 'hobbies'
ERAS = ('modern', 'jazz-age', 'victorian', 'steampunk', 'frontier', 'medieval', 'fantasy')
LEVELS = range(5)
# Words that would give the companion a gender, or that the app keeps out of milestones and pictures.
GENDERED = re.compile(r"\b(?:he|she|him|her|his|hers|himself|herself)\b", re.I)
HURT = re.compile(r'\b(?:injur\w*|bruis\w*|blood\w*|sprain\w*|broke (?:a|an|their) \w+|wound\w*|bleed\w*|scars?|'
                  r'heal\w*|cast on (?:their|a) (?:arm|leg|wrist))\b', re.I)
MODERN_ONLY = re.compile(r'\b(?:phone|app|online|instagram|tiktok|youtube|video|videos|podcast|email|internet|'
                         r'playlist|spotify|laptop|tablet|selfie|upload\w*|subreddit|'
                         r'discord|zoom|strava|wifi|smartwatch|duolingo)\b', re.I)
PLACEHOLDERS = re.compile(r'\{(\w+)\}')


def catalogue() -> dict:
    return json.loads((BANKS / 'catalogue.json').read_text(encoding='utf-8'))


def kinds() -> list[str]:
    return list(catalogue()['kinds'])


def bank(kind: str) -> dict:
    return json.loads((BANKS / f'{kind}.json').read_text(encoding='utf-8'))


def in_era(eras: list[str], era: str) -> bool:
    return 'any' in eras or era in eras


def hobbies_of(kind: str) -> list[dict]:
    if kind == 'general':
        return [{'id': 'custom', 'eras': ['any']}]
    return [item for item in catalogue()['hobbies'] if item['kind'] == kind]


def test_catalogue_hobbies_are_complete():
    found = catalogue()
    ids = [item['id'] for item in found['hobbies']]
    assert len(ids) == len(set(ids))
    for item in found['hobbies']:
        assert item['kind'] in found['kinds'], item['id']
        assert item['words'] and item['session'] and item['picture'], item['id']
        assert all(era == 'any' or era in ERAS for era in item['eras']), item['id']
        assert not GENDERED.search(item['picture'] + item['session']), item['id']
        assert not HURT.search(item['picture']), item['id']
    for era in ERAS:
        assert sum(in_era(item['eras'], era) for item in found['hobbies']) >= 25, era


@pytest.mark.parametrize('kind', kinds())
def test_each_kind_has_a_hundred_specific_milestones(kind):
    found = bank(kind)
    assert found['kind'] == kind
    milestones = found['milestones']
    assert len(milestones) >= 100
    texts = [item['text'] for item in milestones]
    assert len(texts) == len(set(texts)), 'repeated milestone'
    known = {item['id'] for item in hobbies_of(kind)} | {'any'}
    for item in milestones:
        assert item['level'] in LEVELS, item
        assert set(item['for']) <= known, item
        assert all(era == 'any' or era in ERAS for era in item['eras']), item
        words = f"{item['text']} {item['post']}"
        assert not GENDERED.search(words), item
        assert not HURT.search(words), item
        assert set(PLACEHOLDERS.findall(words)) <= {'hobby'}, item
        assert item['text'][:1].islower() and not item['text'].endswith('.'), item
        # It follows the companion's name: "Kim was asked", never "Kim were asked".
        assert not re.match(r'(?:were|are|have)\b', item['text']), item
        assert len(item['post']) <= 120, item
        if MODERN_ONLY.search(words):
            assert item['eras'] == ['modern'], item
    for line in found.get('sessions', ()):
        assert not GENDERED.search(line['text']) and not HURT.search(line['text']), line
        assert set(PLACEHOLDERS.findall(line['text'])) <= {'hobby'}, line


@pytest.mark.parametrize('kind', kinds())
def test_every_hobby_has_milestones_at_every_level_in_its_eras(kind):
    milestones = bank(kind)['milestones']
    for hobby in hobbies_of(kind):
        eras = ERAS if 'any' in hobby['eras'] else hobby['eras']
        for era in eras:
            for level in LEVELS:
                fitting = [item for item in milestones if item['level'] == level and in_era(item['eras'], era)
                           and ('any' in item['for'] or hobby['id'] in item['for'])]
                assert len(fitting) >= 4, (hobby['id'], era, level, len(fitting))
            specific = [item for item in milestones if hobby['id'] in item['for'] and in_era(item['eras'], era)]
            if kind != 'general':
                assert len(specific) >= 3, (hobby['id'], era, len(specific))


# The chat turns "their"/"they" into "your"/"you" (hobbies.yours), so a line never uses them for someone else.
OTHERS_THEIR = re.compile(r'\b(?:beginners?|neighbou?r|friends?|student|someone|stranger|teacher|coach|children|kids|'
                          r'child|people|group|class|everyone|audience|partner|rival|newcomer|members?|regulars?|crowd|'
                          r'family|parents|mother|father|sister|brother|club|players?|opponent|judges?)\b[^.]*'
                          r'\b(?:their|they|them|themselves|theirs)\b', re.I)


@pytest.mark.parametrize('kind', kinds())
def test_every_era_has_a_hundred_milestones_and_their_means_the_companion(kind):
    milestones = bank(kind)['milestones']
    for era in ERAS:
        assert sum(in_era(item['eras'], era) for item in milestones) >= 100, era
    assert not [item['text'] for item in milestones if OTHERS_THEIR.search(item['text'])]
