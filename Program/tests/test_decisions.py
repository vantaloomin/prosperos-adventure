"""Decision models for the Referee (dungeon/providers/decisions.py, dungeon/referee.py): Jev, OpenAI Decisions and
local answer-odds scoring, the profiles that do them and the turn they decide."""
import asyncio
import json
import math
from types import SimpleNamespace

import httpx

from dungeon import referee
from dungeon.providers.decisions import DecisionProvider
from dungeon.providers.scheduling import RequestScheduler
from tests.test_text_models import LOCAL, add

JEV = {'provider': 'openrouter', 'model': 'typesafe/jev-1.14', 'purpose': 'decisions'}
LUNA = {'provider': 'openai', 'model': 'gpt-6-luna', 'purpose': 'decisions'}
SCORER = {'provider': 'local', 'model': 'qwen3.5-4b', 'purpose': 'decisions', 'base_url': 'http://127.0.0.1:8080/v1'}


def ask(config, handler, key='k'):
    sent = []

    def record(request):
        sent.append((str(request.url), json.loads(request.content)))
        return handler(request)
    full = {'base_url': {'openrouter': 'https://openrouter.ai/api/v1', 'openai': 'https://api.openai.com/v1'}.get(
        config['provider'], config.get('base_url')), 'timeout_seconds': 30, **config}
    answers = asyncio.run(DecisionProvider(httpx.MockTransport(record)).ask(full, key, 'I pick the lock',
                                                                            referee.QUESTIONS))
    return answers, sent


def test_jev_is_asked_through_openrouters_decisions_api():
    def handler(_):
        return httpx.Response(200, json={'answers': {
            'roll': {'type': 'noul', 'noul': 0.9},
            'stat': {'type': 'choice', 'choice': 'Mind', 'probabilities': {'Mind': 0.8, 'Luck': 0.2}},
            'difficulty': {'type': 'score', 'score': 2.1, 'probabilities': {'1': 0.1, '2': 0.7, '3': 0.2}}}})
    answers, sent = ask(JEV, handler)
    url, body = sent[0]
    assert url == 'https://openrouter.ai/api/alpha/decisions' and body['model'] == 'typesafe/jev-1.14'
    assert body['state'] == 'I pick the lock' and body['questions']['stat']['criteria']['Luck'].startswith('chance')
    assert answers['roll'] == {'type': 'noul', 'probability': 0.9}
    assert answers['stat']['probabilities']['Mind'] == 0.8
    assert referee.judged('I pick the lock', answers) == {'action': 'I pick the lock', 'roll': True, 'stat': 'Mind',
                                                          'difficulty': 'hard'}


def test_openai_decisions_use_named_questions_and_levels():
    def handler(_):
        return httpx.Response(200, json={'answers': [
            {'type': 'predicate', 'name': 'roll', 'probability': 0.2},
            {'type': 'choice', 'name': 'stat', 'choice': 'Luck', 'probabilities': [{'value': 'Luck', 'probability': 1}]},
            {'type': 'score', 'name': 'difficulty', 'score': 0,
             'probabilities': [{'value': 0, 'label': '0', 'probability': 1}]}]})
    answers, sent = ask(LUNA, handler)
    url, body = sent[0]
    assert url == 'https://api.openai.com/v1/decisions' and body['input'] == 'I pick the lock'
    assert [question['type'] for question in body['questions']] == ['predicate', 'choice', 'score']
    assert body['questions'][2]['levels'][0]['label'] == '0'
    assert referee.judged('I pick the lock', answers) == {'action': 'I pick the lock', 'roll': False}


def test_a_local_model_answers_by_the_odds_of_each_letter():
    def handler(request):
        body = json.loads(request.content)
        options = body['messages'][1]['content']
        # Stat question: A is Mind; the others favour their first answer.
        odds = [{'token': ' A', 'logprob': math.log(0.6)}, {'token': 'B', 'logprob': math.log(0.3)},
                {'token': 'Sure', 'logprob': math.log(0.1)}]
        if 'Which stat' in options:
            odds = [{'token': 'E', 'logprob': math.log(0.7)}, {'token': 'A', 'logprob': math.log(0.1)}]
        return httpx.Response(200, json={'choices': [{'logprobs': {'content': [{'token': 'A', 'logprob': -0.5,
                                                                                 'top_logprobs': odds}]}}]})
    answers, sent = ask(SCORER, handler, key=None)
    assert all(url == 'http://127.0.0.1:8080/v1/chat/completions' for url, _ in sent) and len(sent) == 3
    assert sent[0][1]['max_tokens'] == 1 and sent[0][1]['logprobs'] and sent[0][1]['chat_template_kwargs']
    assert math.isclose(answers['roll']['probability'], 2 / 3)
    assert max(answers['stat']['probabilities'], key=answers['stat']['probabilities'].get) == 'Essence'
    assert referee.judged('I pick the lock', answers)['difficulty'] == 'easy'


def test_a_server_without_log_probabilities_cannot_decide():
    def handler(_):
        return httpx.Response(200, json={'choices': [{'message': {'content': 'A'}}]})
    try:
        ask(SCORER, handler, key=None)
    except Exception as error:  # noqa: BLE001
        assert 'log probabilities' in str(error)
    else:
        raise AssertionError('expected a failure')


class FakeDecider:
    def __init__(self, roll=0.9, fail=False):
        self.asked, self.roll, self.fail = [], roll, fail

    async def ask(self, config, key, state, questions):
        self.asked.append(state)
        if self.fail:
            raise RuntimeError('down')
        return {'roll': {'type': 'noul', 'probability': 0.1 if 'look' in state else self.roll},
                'stat': {'type': 'choice', 'probabilities': {'Allure': 0.7, 'Mind': 0.3}},
                'difficulty': {'type': 'score', 'probabilities': [0, 0, 1, 0, 0]}}


def state_with(decider):
    return SimpleNamespace(decider=decider, scheduler=RequestScheduler(), vault=SimpleNamespace(get=lambda _: None),
                           provider=None)


def test_without_a_referee_profile_each_sentence_is_decided():
    decider = FakeDecider()
    actions = asyncio.run(referee.decide(state_with(decider), 'I look around. Then I sweet-talk the guard.', None,
                                         {**SCORER, 'timeout_seconds': 30}))
    assert decider.asked == ['I look around', 'I sweet-talk the guard']
    assert actions == [{'action': 'I sweet-talk the guard', 'roll': True, 'stat': 'Allure', 'difficulty': 'hard',
                        'said': True}]


def test_a_failing_decision_model_falls_back_to_the_keyword_rules():
    actions = asyncio.run(referee.decide(state_with(FakeDecider(fail=True)), 'I try to persuade the guard.', None,
                                         {**SCORER, 'timeout_seconds': 30}))
    assert [action['stat'] for action in actions] == ['Allure']


def test_decisions_take_a_decisions_profile_or_a_local_text_profile(client):
    jev = add(client, JEV, api_key='or-key')
    narrator = add(client, LOCAL)
    hosted = add(client, {'provider': 'openai', 'model': 'gpt'})
    assert jev['decisions_ready'] and not jev['ready'] and narrator['decisions_ready'] and not hosted['decisions_ready']
    add(client, {**JEV, 'provider': 'anthropic', 'model': 'claude'}, status=422)
    for profile, status in ((jev, 200), (narrator, 200), (hosted, 409)):
        response = client.put('/api/models/routes', json={'job': 'decisions', 'profile_id': profile['id']})
        assert response.status_code == status, response.text
    # A decisions profile never narrates or splits turns.
    assert client.put('/api/models/routes', json={'job': 'referee', 'profile_id': jev['id']}).status_code == 409
    overview = client.get('/api/models').json()
    assert overview['routes']['decisions'] == narrator['id']
    assert any(job['key'] == 'decisions' for job in overview['jobs'])
