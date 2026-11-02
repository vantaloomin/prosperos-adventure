"""Decision models: typed questions answered with probabilities, never with text (docs/requirements.md "Referee model").

Three kinds of question, as Jev asks them: `noul` (how likely a statement is true), `choice` (one of named options)
and `score` (a level on an ordered scale, lowest first). Every backend answers in one shape:

- noul: `{'type': 'noul', 'probability': p}`
- choice: `{'type': 'choice', 'probabilities': {option: p, ...}}`
- score: `{'type': 'score', 'probabilities': [p for each level, lowest first]}`

Backends, by the profile's provider:

- `openrouter`: Jev (typesafe/jev-1.14) through OpenRouter's `POST /api/alpha/decisions`.
- `openai`: OpenAI's `POST /v1/decisions` (gpt-6-luna).
- `local` and `compatible`: any chat model, asked for one token with its log probabilities. Each option gets a
  letter, and the odds of the letters are the answer, so the model never writes a reply to refuse or misread.
  Text profiles on these servers work too, so the narrator's own local model can decide.
"""
import asyncio
import math
import string

import httpx

from dungeon.errors import DomainError, require
from dungeon.providers.builtin_chat import RESOURCE_GROUP as BUILTIN_CHAT
from dungeon.providers.chat import check_status
from dungeon.providers.requests import headers_for, validate_key
from dungeon.providers.urls import network

LETTERS = string.ascii_uppercase
# How many of the likeliest first tokens a local server is asked for; the letters must be among them.
TOP_TOKENS = 20
SCORED = 'You answer multiple-choice questions about one action in a tabletop roleplaying game. You never write ' \
         'story. Answer with the letter of one option and nothing else.'


def lettered(question: dict) -> list[tuple[str, str, str]]:
    """(letter, option, description) for each answer a question allows, in order."""
    if question['type'] == 'noul':
        return [('A', 'true', 'Yes'), ('B', 'false', 'No')]
    if question['type'] == 'choice':
        return [(LETTERS[index], option, text) for index, (option, text) in enumerate(question['criteria'].items())]
    return [(LETTERS[index], str(index), text) for index, text in enumerate(question['criteria'])]


def shaped(question: dict, odds: dict[str, float]) -> dict:
    """The one answer shape from odds keyed by option (choice), level index (score) or 'true'/'false' (noul)."""
    total = sum(odds.values())
    require(total > 0, 'The decision model gave none of the answers.', 502)
    odds = {option: value / total for option, value in odds.items()}
    if question['type'] == 'noul':
        return {'type': 'noul', 'probability': odds.get('true', 0.0)}
    if question['type'] == 'choice':
        return {'type': 'choice', 'probabilities': {option: odds.get(option, 0.0) for option in question['criteria']}}
    return {'type': 'score', 'probabilities': [odds.get(str(index), 0.0) for index in range(len(question['criteria']))]}


def letter_odds(data: dict, letters: dict[str, str]) -> dict[str, float]:
    """The chance of each letter as the first token, from an OpenAI-style `logprobs` reply."""
    try:
        first = data['choices'][0]['logprobs']['content'][0]
        tokens = first.get('top_logprobs') or [first]
    except (KeyError, IndexError, TypeError) as error:
        raise DomainError('This server did not return log probabilities, so it cannot answer decisions.', 502,
                          'provider') from error
    odds = dict.fromkeys(letters.values(), 0.0)
    for token in tokens:
        text = str(token.get('token', '')).strip().strip('.):').upper()
        if text in letters and isinstance(token.get('logprob'), (int, float)):
            odds[letters[text]] += math.exp(token['logprob'])
    return odds


def jev_url(config: dict) -> str:
    """OpenRouter's decisions API sits beside its /v1 API."""
    return config['base_url'].removesuffix('/v1') + '/alpha/decisions'


def jev_body(config: dict, state: str, questions: dict) -> dict:
    return {'model': config['model'], 'state': state,
            'questions': {name: {key: question[key] for key in ('type', 'instructions', 'criteria') if key in question}
                          for name, question in questions.items()}}


def jev_answer(question: dict, answer: dict) -> dict:
    require(isinstance(answer, dict) and answer.get('type') == question['type'],
            'The decision model answered a different kind of question.', 502)
    if question['type'] == 'noul':
        value = answer.get('noul')
        require(isinstance(value, (int, float)), 'The decision model gave no probability.', 502)
        return {'type': 'noul', 'probability': float(value)}
    odds = answer.get('probabilities')
    require(isinstance(odds, dict), 'The decision model gave no probabilities.', 502)
    if question['type'] == 'choice':
        return shaped(question, {option: float(odds.get(option) or 0) for option in question['criteria']})
    # Score levels come back under the legend's keys, "0" for the lowest.
    return shaped(question, {str(index): float(odds.get(str(index)) or 0) for index in range(len(question['criteria']))})


def openai_body(config: dict, state: str, questions: dict) -> dict:
    asked = []
    for name, question in questions.items():
        item = {'type': 'predicate' if question['type'] == 'noul' else question['type'], 'name': name,
                'instructions': question['instructions']}
        if question['type'] == 'choice':
            item['choices'] = [{'value': option, 'description': text} for option, text in question['criteria'].items()]
        elif question['type'] == 'score':
            item['levels'] = [{'label': str(index), 'description': text}
                              for index, text in enumerate(question['criteria'])]
        asked.append(item)
    return {'model': config['model'], 'input': state, 'questions': asked}


def openai_answer(question: dict, answer: dict) -> dict:
    require(isinstance(answer, dict), 'The decision model gave no answer.', 502)
    require(answer.get('type') != 'refusal', 'The decision model refused this question.', 502)
    if question['type'] == 'noul':
        value = answer.get('probability')
        require(isinstance(value, (int, float)), 'The decision model gave no probability.', 502)
        return {'type': 'noul', 'probability': float(value)}
    odds = answer.get('probabilities')
    require(isinstance(odds, list), 'The decision model gave no probabilities.', 502)
    # A choice is named by its value; a level by the label we sent, its index.
    named = 'value' if question['type'] == 'choice' else 'label'
    return shaped(question, {str(item.get(named)): float(item.get('probability') or 0)
                             for item in odds if isinstance(item, dict)})


def scored_body(config: dict, state: str, question: dict) -> dict:
    options = '\n'.join(f'{letter}. {text}' for letter, _, text in lettered(question))
    body = {'model': config['model'], 'max_tokens': 1, 'temperature': 0, 'logprobs': True, 'top_logprobs': TOP_TOKENS,
            'stream': False,
            'messages': [{'role': 'system', 'content': SCORED},
                         {'role': 'user', 'content': f'Action: {state}\n\nQuestion: {question["instructions"]}\n\n'
                                                     f'{options}\n\nAnswer with one letter.'}]}
    if config['provider'] == 'local':
        # Thinking models (Qwen and others on llama.cpp) would spend the one token opening a thought.
        body['chat_template_kwargs'] = {'enable_thinking': False}
    return body


class DecisionProvider:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport
        # The built-in chat model's server (builtin_chat.py), set by the app, for a built-in text profile.
        self.builtin_chat = None

    async def address(self, config: dict) -> str:
        if config.get('resource_group') != BUILTIN_CHAT or self.builtin_chat is None:
            return config['base_url']
        return await self.builtin_chat.address()

    async def ask(self, config: dict, key: str | None, state: str, questions: dict[str, dict]) -> dict[str, dict]:
        """Each question's answer, by its name. Raises DomainError when the service fails or answers out of shape."""
        provider = config['provider']
        validate_key(provider, key)
        limit = config.get('timeout_seconds', 180)
        headers = headers_for({'provider': provider}, key)
        try:
            async with asyncio.timeout(limit):
                base_url = await self.address(config)
                async with httpx.AsyncClient(transport=self.transport, timeout=limit, follow_redirects=False,
                                             **network(base_url)) as client:
                    if config.get('purpose') == 'decisions' and provider == 'openrouter':
                        return await self.jev(client, {**config, 'base_url': base_url}, headers, state, questions)
                    if config.get('purpose') == 'decisions' and provider == 'openai':
                        return await self.openai(client, base_url, config, headers, state, questions)
                    asked = [self.scored(client, base_url, config, headers, state, question)
                             for question in questions.values()]
                    return dict(zip(questions, await asyncio.gather(*asked)))
        except (httpx.TimeoutException, TimeoutError) as error:
            raise DomainError('The decision model did not answer in time.', 504, 'timeout') from error
        except (httpx.RequestError, ValueError) as error:
            raise DomainError('Cannot reach the decision model.', 502, 'connection') from error

    async def jev(self, client, config, headers, state, questions) -> dict[str, dict]:
        response = await client.post(jev_url(config), headers=headers, json=jev_body(config, state, questions))
        check_status(response, config['model'])
        answers = response.json().get('answers')
        require(isinstance(answers, dict), 'The decision model returned no answers.', 502)
        return {name: jev_answer(question, answers.get(name)) for name, question in questions.items()}

    async def openai(self, client, base_url, config, headers, state, questions) -> dict[str, dict]:
        response = await client.post(base_url + '/decisions', headers=headers,
                                     json=openai_body(config, state, questions))
        check_status(response, config['model'])
        answers = response.json().get('answers')
        require(isinstance(answers, list), 'The decision model returned no answers.', 502)
        by_name = {answer.get('name'): answer for answer in answers if isinstance(answer, dict)}
        return {name: openai_answer(question, by_name.get(name)) for name, question in questions.items()}

    async def scored(self, client, base_url, config, headers, state, question) -> dict:
        response = await client.post(base_url + '/chat/completions', headers=headers,
                                     json=scored_body(config, state, question))
        check_status(response, config['model'])
        letters = {letter: option for letter, option, _ in lettered(question)}
        return shaped(question, letter_odds(response.json(), letters))
