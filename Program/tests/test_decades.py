"""Decades (dungeon/world/decades.py): a modern world in a past year keeps to it, and the present is untouched."""
import asyncio
from datetime import datetime

import pytest
from pydantic import ValidationError

from dungeon import passages, story
from dungeon.world import catalog, decades
from dungeon.world.schema import Career

AUTUMN_2009 = datetime(2009, 10, 3, 20, 0)
TODAY = 2026


def haven() -> dict:
    return catalog.city('haven')


def today_city() -> dict:
    """Haven as a city written for today."""
    return haven() | {'names': {**haven()['names'], 'year': None}}


def test_the_year_counts_only_for_a_modern_city_before_today():
    assert decades.year_of(haven(), AUTUMN_2009, TODAY) == 2009
    assert decades.year_of(haven(), present=TODAY) == 2009
    assert decades.year_of(haven(), datetime(2026, 5, 1), TODAY) is None
    assert decades.year_of(catalog.city('kingswood'), datetime(1200, 5, 1), TODAY) is None
    assert decades.decade(2009) == '2000s' and decades.part(2009) == 'late' and decades.part(2001) == 'early'


def test_careers_keep_to_their_years():
    offered = catalog.careers_for(haven())
    assert 'video-store-clerk' in offered and 'web-designer' in offered
    assert 'subscription-creator' not in catalog.careers_for(haven(), needs_met=False)
    today = catalog.careers_for(today_city())
    assert 'video-store-clerk' not in today and 'film-projectionist' not in today
    assert 'subscription-creator' in catalog.careers_for(today_city(), needs_met=False)


def test_a_career_runs_its_years_forward():
    base = catalog.careers()['barista']
    assert Career.model_validate(base | {'years': [1995, None]}).years == (1995, None)
    with pytest.raises(ValidationError):
        Career.model_validate(base | {'years': [2010, 1995]})


def test_prices_are_in_the_city_s_own_year_and_scaled_to_another():
    assert decades.share(haven(), 2009) == pytest.approx(1.0)
    assert decades.share(haven(), 2026) > 1.4
    assert 0.6 < decades.share(today_city(), 2009) < 0.7
    assert '$1.50' in decades.prices_text(haven(), 2009)


def test_the_year_s_slang_media_and_pastimes():
    words = decades.slang(2009)
    assert 'totes' in words and 'as if' not in words and 'YOLO' not in words
    shown = decades.media(haven(), 2009, 'seed')
    assert shown == decades.media(haven(), 2009, 'seed')
    assert len(shown['shows']) == decades.SHOWS and len(shown['songs']) == decades.SONGS and shown['books']
    bank = decades.media_bank()
    years = {entry[0]: entry[2] for kind in ('show', 'book', 'music') for entry in bank[kind]}
    for title in shown['shows'] + shown['songs'] + shown['books']:
        assert years[title.rsplit(' (', 1)[0]] <= 2009
    assert 'LAN parties' in decades.pastimes(2009) and 'Blogging' not in decades.pastimes(1995)


def test_the_narrator_is_told_the_year_and_nothing_in_the_present():
    text = decades.prompt_text(haven(), AUTUMN_2009, 'seed', TODAY)
    assert text.startswith('## The year: 2009') and 'flip' in text and 'Instagram' in text and 'totes' in text
    assert decades.prompt_text(haven(), datetime(2026, 5, 1), 'seed', TODAY) == ''
    assert decades.prompt_text(catalog.city('kingswood'), datetime(1200, 5, 1), 'seed', TODAY) == ''
    assert '2009' in decades.picture_text(haven(), AUTUMN_2009, TODAY)
    assert decades.picture_text(haven(), datetime(2026, 5, 1), TODAY) == ''


@pytest.mark.parametrize('text, labels', [
    ('She checked Instagram, took a selfie and said "YOLO."', {'Instagram', 'the word selfie', 'the slang "YOLO"'}),
    ('He called an Uber and opened a dating app.', {'Uber and ride-hailing', 'dating apps and swiping'}),
    ('A stream ran past; birds tweeted. He texted her back, burned a CD and rented a DVD from Blockbuster.', set()),
    ('She kept a notebook and drank a cold one. A low drone came from the vents. The ghost drifted by.', set()),
])
def test_later_things_are_caught_in_narration_and_older_words_are_not(text, labels):
    assert {finding['label'] for finding in decades.anachronisms(text, 2009)} == labels
    assert decades.anachronisms(text, None) == []
    assert decades.anachronisms(text, 2025) == []


def test_a_passage_naming_a_later_thing_is_flagged_with_why():
    text = 'The bar was loud.\n\nShe scrolled Instagram while she waited.'
    flagged = passages.flags(text, {}, later=passages.later_reasons(text, 2009))
    assert [flag['passage'] for flag in flagged] == ['She scrolled Instagram while she waited.']
    assert 'only came in 2010' in flagged[0]['why'][0]
    assert passages.flags(text, {}, later=passages.later_reasons(text, None)) == []


def test_the_rewrite_takes_a_later_thing_out_or_the_draft_stands():
    draft = 'She checked Instagram on her phone while the band set up and the bar slowly filled with people.'
    found = decades.anachronisms(draft, 2009)
    fixed = 'She checked her flip phone for texts while the band set up and the bar slowly filled with people.'

    async def rewrite(_system, messages):
        assert 'only came in 2010' in messages[0]['content']
        return fixed

    async def worse(_system, _messages):
        return 'Instagram.'

    async def broken(_system, _messages):
        raise RuntimeError('no model')

    assert asyncio.run(story.anachronism_rewrite(draft, found, 2009, rewrite)) == fixed
    assert asyncio.run(story.anachronism_rewrite(draft, found, 2009, worse)) == draft
    assert asyncio.run(story.anachronism_rewrite(draft, found, 2009, broken)) == draft
