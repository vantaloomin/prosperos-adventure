"""Hosted voices: OpenAI, ElevenLabs and Google Cloud Text-to-Speech, each with the user's own key.

Only the note's words go to the service, with the voice to read them in; nothing about the companion or the chat.
Each returns an MP3. The voice lists come from the services themselves (ElevenLabs and Google), so new stock voices
show up without an update; OpenAI's list is fixed in dungeon/voice/voices.py because its API has none.
"""
import base64

import httpx

from dungeon.errors import DomainError

TIMEOUT = 60
OPENAI_MODEL = 'gpt-4o-mini-tts'
OPENAI_URL = 'https://api.openai.com/v1/audio/speech'
OPENAI_STYLE = 'Speak casually and warmly, like a voice message to a friend.'
ELEVENLABS = 'https://api.elevenlabs.io'
ELEVENLABS_MODEL = 'eleven_multilingual_v2'
GOOGLE = 'https://texttospeech.googleapis.com/v1'
# Google's most natural voices first.
GOOGLE_RANK = ('Chirp3-HD', 'Chirp-HD', 'Neural2', 'Studio', 'Wavenet')
ENGINE_NAMES = {'openai': 'OpenAI', 'elevenlabs': 'ElevenLabs', 'google': 'Google'}


def refused(engine: str, response: httpx.Response) -> DomainError:
    name = ENGINE_NAMES[engine]
    if response.status_code in (401, 403):
        return DomainError(f'{name} did not accept the voice key. Check it in Settings > Models > Voice notes.', 502)
    if response.status_code == 429:
        return DomainError(f'{name} says the voice account is out of credit or busy. Try again later.', 502)
    return DomainError(f'{name} could not read the note aloud ({response.status_code}).', 502)


async def call(engine: str, transport, method: str, url: str, **options) -> httpx.Response:
    try:
        async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT, trust_env=True) as client:
            response = await client.request(method, url, **options)
    except httpx.HTTPError as error:
        raise DomainError(f'Cannot reach {ENGINE_NAMES[engine]}. Check your internet connection.', 502) from error
    if response.status_code != 200:
        raise refused(engine, response)
    return response


async def speak(engine: str, key: str, voice: str, text: str, transport=None) -> bytes:
    """The note read aloud by a hosted engine, as MP3 bytes."""
    if engine == 'openai':
        response = await call(engine, transport, 'POST', OPENAI_URL, headers={'Authorization': f'Bearer {key}'},
                              json={'model': OPENAI_MODEL, 'voice': voice, 'input': text,
                                    'instructions': OPENAI_STYLE, 'response_format': 'mp3'})
        return response.content
    if engine == 'elevenlabs':
        response = await call(engine, transport, 'POST', f'{ELEVENLABS}/v1/text-to-speech/{voice}',
                              params={'output_format': 'mp3_44100_128'}, headers={'xi-api-key': key},
                              json={'text': text, 'model_id': ELEVENLABS_MODEL})
        return response.content
    language = '-'.join(voice.split('-')[:2])
    response = await call(engine, transport, 'POST', f'{GOOGLE}/text:synthesize', headers={'X-Goog-Api-Key': key},
                          json={'input': {'text': text}, 'voice': {'languageCode': language, 'name': voice},
                                'audioConfig': {'audioEncoding': 'MP3'}})
    try:
        return base64.b64decode(response.json()['audioContent'])
    except (ValueError, KeyError, TypeError) as error:
        raise DomainError('Google sent back a voice note it could not read.', 502) from error


def accent_of(text: str) -> str:
    lowered = (text or '').lower()
    return 'gb' if any(word in lowered for word in ('british', 'english', 'irish', 'scottish', 'australian')) else 'us'


async def elevenlabs_voices(key: str, transport=None) -> list[dict]:
    response = await call('elevenlabs', transport, 'GET', f'{ELEVENLABS}/v2/voices', headers={'xi-api-key': key},
                          params={'page_size': 100, 'category': 'premade'})
    found = []
    for voice in response.json().get('voices') or []:
        labels = voice.get('labels') or {}
        sex = labels.get('gender') if labels.get('gender') in ('female', 'male') else 'neutral'
        place = accent_of(labels.get('accent'))
        found.append({'id': voice['voice_id'], 'name': voice.get('name') or voice['voice_id'], 'gender': sex,
                      'accent': place, 'label': ' · '.join(part for part in (
                          voice.get('name'), labels.get('accent'), labels.get('age'), labels.get('gender')) if part)})
    return found


def google_rank(name: str) -> int:
    return next((index for index, kind in enumerate(GOOGLE_RANK) if kind in name), len(GOOGLE_RANK))


async def google_voices(key: str, transport=None) -> list[dict]:
    found = []
    for language, place in (('en-US', 'us'), ('en-GB', 'gb')):
        response = await call('google', transport, 'GET', f'{GOOGLE}/voices', headers={'X-Goog-Api-Key': key},
                              params={'languageCode': language})
        for voice in response.json().get('voices') or []:
            sex = (voice.get('ssmlGender') or '').lower()
            found.append({'id': voice['name'], 'name': voice['name'],
                          'gender': sex if sex in ('female', 'male') else 'neutral', 'accent': place,
                          'label': f"{voice['name']} ({'British' if place == 'gb' else 'American'}, "
                                   f"{'woman' if sex == 'female' else 'man' if sex == 'male' else 'either'})"})
    return sorted(found, key=lambda voice: (google_rank(voice['id']), voice['id']))
