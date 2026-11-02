"""Booru tag prompts for Illustrious, NoobAI and Pony models (Vanta, 2026-10-29): Sett came out as a woman, or as two
half figures side by side, from the photo paragraph."""
import asyncio
import json

import httpx

from dungeon.images import backends, tags
from dungeon.images.adapters.comfyui import FAMILIES, ComfyAdapter, built_in, tag_kind
from tests.test_images import ComfyStandIn, request_for

LOCAL = {'base_url': 'http://127.0.0.1:8188'}
BASE = ('Sett, a man in his mid thirties with tan skin, a square face, tall muscular half-vastayan man, swept-back '
        'red-brown hair, pointed pink furry ears, amber eyes, confident grin with sharp canines, open fur-collared coat '
        'over bare chest, gold chain')


def test_a_profile_picture_paragraph_becomes_one_man_in_tags():
    paragraph = (f'{tags.ILLUSTRIOUS}. {BASE}, Sett, a waist-up portrait in a three-quarter view, wearing a denim jacket '
                 'over a plain top, a confident, easy smile, plain light grey background. The attached reference picture '
                 'shows the same person.')
    prompt, negative = tags.convert(paragraph, 'text, duplicate person', None, tags.ILLUSTRIOUS)
    parts = prompt.split(', ')
    # Quality first, then who: one man, before anything else.
    assert prompt.startswith(f'{tags.ILLUSTRIOUS}, solo, 1boy, male focus, ')
    for tag in ('sett', 'tall', 'muscular', 'swept-back red-brown hair', 'amber eyes', 'open fur-collared coat',
                'bare chest', 'gold chain', 'upper body', 'three-quarter view', 'denim jacket', 'simple background'):
        assert tag in parts, tag
    # The photo model's instruction about the reference picture has nothing to draw.
    assert 'reference' not in prompt and 'man' not in parts and 'fictional' not in prompt
    negative_parts = negative.split(', ')
    assert {'1girl', 'female focus', 'multiple people', 'multiple views', 'split screen'} <= set(negative_parts)
    # The app's own negative follows, without what the model's already says.
    assert negative_parts[-1] == 'duplicate person' and len(negative_parts) == len(set(negative_parts))


def test_the_only_person_line_and_name_say_who_and_company_drops_solo():
    paragraph = ('Anime illustration of a fictional everyday moment, a medium shot with her whole head and face in the '
                 'frame. Long black hair, freckles. She is reading at a café table. She is the only person in the '
                 'picture. Warm late-afternoon light. This is Mia.')
    prompt, negative = tags.convert(paragraph, '', None, 'Anime illustration')
    assert prompt.startswith(f'{tags.ILLUSTRIOUS}, solo, 1girl, mia, cowboy shot, long black hair, freckles, reading')
    assert 'afternoon' in prompt and '1boy' in negative
    together, negative = tags.convert('Anime illustration. He is at the market with a friend.', '', 'Sett',
                                      'Anime illustration')
    assert 'solo' not in together.split(', ') and '1boy' in together and 'multiple people' not in negative
    view, negative = tags.convert('Anime illustration of a fictional everyday moment, a fictional first-person phone '
                                  'photo of what she can see right now, nobody in focus. The harbour at dusk.', '',
                                  'Mia', 'Anime illustration')
    assert 'scenery, no humans' in view and 'mia' not in view and '1girl' not in view + negative


def test_pony_gets_its_scores_and_a_users_own_style_keeps_its_words():
    prompt, negative = tags.convert(f'{tags.ILLUSTRIOUS}. {BASE}.', '', None, tags.ILLUSTRIOUS, 'pony')
    assert prompt.startswith(f'{tags.PONY}, solo, 1boy') and tags.ILLUSTRIOUS not in prompt
    assert negative.startswith('score_4, score_5, score_6, ')
    own, _ = tags.convert(f'Watercolor, soft pastel colors. {BASE}.', '', None, 'Watercolor, soft pastel colors')
    assert own.startswith(f'{tags.ILLUSTRIOUS}, watercolor, soft pastel colors, solo, 1boy')
    # A photo style says nothing these models can use, so the quality tags stand in for it.
    photo, _ = tags.convert(f'Candid, natural-light photograph. {BASE}.', '', None, 'Candid, natural-light photograph')
    assert photo.startswith(f'{tags.ILLUSTRIOUS}, solo, 1boy') and 'photograph' not in photo
    older, _ = tags.convert('A woman in her late sixties with grey hair.', '', None, None)
    assert '1girl' in older and 'old woman' in older


def test_a_booru_backend_sends_tags_and_its_workflow_adds_nothing_of_its_own():
    assert FAMILIES['booru'].style == tags.ILLUSTRIOUS
    text = json.dumps(built_in({'family': 'booru'}))
    assert 'masterpiece' not in text and 'lowres' not in text
    server = ComfyStandIn()
    adapter = ComfyAdapter(httpx.MockTransport(server), poll_seconds=0)
    paragraph = f'{tags.ILLUSTRIOUS}. {BASE}, waist-up photo facing the camera. He is the only person in the picture.'
    asyncio.run(adapter.generate(request_for('comfyui', {**LOCAL, 'family': 'booru'}, prompt=paragraph)))
    texts = [node['inputs']['text'] for node in server.prompts[0].values() if 'text' in node['inputs']]
    assert texts[0].startswith(f'{tags.ILLUSTRIOUS}, solo, 1boy, male focus, ') and 'looking at viewer' in texts[0]
    assert texts[1].startswith('lowres, worst quality') and '1girl' in texts[1]


def test_tags_are_picked_from_the_family_or_a_workflow_that_loads_a_tag_model():
    assert tag_kind({'family': 'booru'}) == 'illustrious'
    assert tag_kind({'family': 'booru', 'ckpt_name': 'ponyDiffusionV6XL.safetensors'}) == 'pony'
    assert tag_kind({}) is None and tag_kind({'family': 'anima'}) is None
    own = json.dumps({'1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'waiIllustriousSDXL.safetensors'}}})
    assert tag_kind({'workflow': own}) == 'illustrious'
    assert tag_kind({'workflow': json.dumps({'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'flux.safetensors'}}})}) \
        is None
    booru = {'kind': 'comfyui', 'config': json.dumps({'family': 'booru'})}
    assert backends.own_style(booru) == tags.ILLUSTRIOUS


def test_a_story_portrait_prompt_becomes_one_person_in_tags():
    """Dungeon's art prompts (dungeon/art.py) are short lines, not the photo paragraph; they still say who."""
    prompt, negative = tags.convert('Portrait of Bren (he/him, 34 years old, smith), in Kingswood. A broad man with a '
                                    'burn-scarred forearm. With a warm smile.', 'text, watermark', None, tags.ILLUSTRIOUS)
    assert prompt.startswith(f'{tags.ILLUSTRIOUS}, solo, 1boy, male focus, ') and '1girl' in negative
