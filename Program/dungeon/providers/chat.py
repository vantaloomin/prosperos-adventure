"""Streaming replies from every supported provider, plus the connection test.

SSE parsing, status handling and the per-provider dispatch are adapted from prosperos-study
server/providers/http.py and completion.py at bbcbde4. Changes: requests carry the Companion's
conversation, a reply stopped at the token limit or by a content filter stays a visible incomplete
reply (its `finish_reason`) rather than an error, and Codex CLI runs through the same interface.
"""
import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from dungeon.errors import DomainError, require
from dungeon.providers import balance, efforts
from dungeon.providers.builtin_chat import RESOURCE_GROUP as BUILTIN_CHAT
from dungeon.providers.claude_code import ClaudeCodeProvider
from dungeon.providers.codex import CodexProvider
from dungeon.providers.discovery import discover_models
from dungeon.providers.discovery_errors import check_with_deadline
from dungeon.providers.events import Chunk, anthropic_event, chat_event, google_event, openai_event
from dungeon.providers.prompt_cache import PromptCache
from dungeon.providers.requests import REQUESTS, headers_for, validate_key
from dungeon.providers.urls import network

__all__ = ['INCOMPLETE', 'Chunk', 'ChatProvider']

INCOMPLETE = {'length': 'The reply stopped at the output token limit.',
              'content_filter': "The provider stopped this reply because of its content filter."}
FAILURES = {
    'tool_calls': 'The model asked to use a tool instead of replying. The Dungeon does not run model tools.',
    'function_call': 'The model asked to use a tool instead of replying. The Dungeon does not run model tools.',
    'unrecognized': 'The provider reported an unsupported completion reason. Check its model and settings.',
}
PARSERS = {'openai': openai_event, 'anthropic': anthropic_event, 'google': google_event,
           'openrouter': chat_event, 'nanogpt': chat_event, 'local': chat_event, 'compatible': chat_event}


def provider_of(config: dict) -> str:
    return config.get('provider') or 'compatible'


RATE_LIMIT_ATTEMPTS = 2
RATE_LIMIT_WAIT = (1.0, 2.0, 5.0)  # Shortest, default and longest wait before the one retry, in seconds.


def retry_delay(response: httpx.Response) -> float:
    shortest, default, longest = RATE_LIMIT_WAIT
    try:
        wanted = float(response.headers.get('retry-after', default))
    except ValueError:
        wanted = default
    return min(max(wanted, shortest), longest)


class Rejected(DomainError):
    """The service turned the request down as malformed (HTTP 400 or 422); `said` is its whole explanation."""

    def __init__(self, message: str, said: str):
        super().__init__(message, 502, 'provider')
        self.said = said


def provider_message(response: httpx.Response, limit: int = 200) -> str:
    """The service's own explanation from an error reply, when it gave one (OpenAI-style
    `{"error": {"message": ...}}`, or a plain `message` or `detail`), cut to `limit` characters."""
    try:
        data = json.loads(response.text)
    except (httpx.ResponseNotRead, ValueError):
        return ''
    if not isinstance(data, dict):
        return ''
    error = data.get('error')
    for value in (error.get('message') if isinstance(error, dict) else error, data.get('message'), data.get('detail')):
        if isinstance(value, str) and value.strip():
            text = ' '.join(value.split())
            return text if len(text) <= limit else text[:limit - 1] + '…'
    return ''


def check_status(response: httpx.Response, model: str | None = None):
    """A failed answer from the model service, said in plain words with the service's own reason when it gave one.
    Streamed replies are read first (`raise_for_status`), so that reason is there to quote."""
    if response.is_success:
        return
    code, said = response.status_code, provider_message(response)
    named = f' "{model}"' if model else ''
    descriptions = {
        401: "The service rejected the API key. Check the model profile's key.",
        403: 'This account cannot use the selected service or model.',
        404: f'The service did not recognize the model{named} or the address. Check the model name, and that the '
             'address ends where the service\'s docs say (usually /v1).',
        # NVIDIA NIM answers 410 for a model past its end of life.
        410: f'The service no longer offers the model{named}. Choose another one in the model profile.',
        429: 'The service reached a rate or usage limit. Try again when it is available.',
    }
    if code in descriptions:
        text = descriptions[code]
    elif code in (400, 422):
        text = f'The service turned down the request (HTTP {code}).'
        raise Rejected(f'{text} It said: "{said}"' if said else text, provider_message(response, 2000))
    elif code >= 500:
        text = f'The service had a problem on its side (HTTP {code}). Try again in a moment.'
    else:
        text = f'The service rejected this request (HTTP {code}).'
    raise DomainError(f'{text} It said: "{said}"' if said else text, 502, 'provider')


async def raise_for_status(response: httpx.Response, model: str | None = None):
    if not response.is_success:
        await response.aread()
    check_status(response, model)


async def sse_data(response: httpx.Response) -> AsyncIterator[dict]:
    lines = []
    async for line in response.aiter_lines():
        if line.startswith('data:'):
            lines.append(line[5:].lstrip())
        elif not line and lines:
            yield parse_sse('\n'.join(lines))
            lines = []
    if lines:
        yield parse_sse('\n'.join(lines))


def parse_sse(value: str) -> dict:
    if value == '[DONE]':
        return {'_done': True}
    try:
        data = json.loads(value)
        require(isinstance(data, dict), 'The service returned an invalid stream event.', 502)
        return data
    except json.JSONDecodeError as error:
        raise DomainError('The service returned a malformed stream event.', 502) from error


@dataclass
class Completion:
    """Whether the service finished its reply, and whether what arrived can be a reply at all."""
    completed: bool = False
    has_text: bool = False
    reasoning: bool = False
    finish_reason: str | None = None

    def observe(self, chunk: Chunk):
        self.completed = self.completed or chunk.done or bool(chunk.finish_reason)
        self.has_text = self.has_text or bool(chunk.text.strip())
        self.reasoning = self.reasoning or chunk.reasoning
        self.finish_reason = chunk.finish_reason or self.finish_reason

    def spent_on_thinking(self) -> bool:
        return self.reasoning and not self.has_text and self.finish_reason == 'length'

    def validate(self):
        require(self.completed, 'The connection ended before the service completed its reply.', 502)
        if self.finish_reason in FAILURES:
            raise DomainError(FAILURES[self.finish_reason], 502, 'provider')
        if self.reasoning and not self.has_text and self.finish_reason not in INCOMPLETE:
            raise DomainError('The model returned reasoning but no reply text. Check its thinking settings or raise '
                              'the longest reply in Settings > Models.', 502, 'provider')


class ChatProvider:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, codex: CodexProvider | None = None,
                 claude_code: ClaudeCodeProvider | None = None):
        self.transport = transport
        self.codex = codex or CodexProvider()
        self.claude_code = claude_code or ClaudeCodeProvider()
        # Instant replies on local models: each companion's prompt start kept and put back (prompt_cache.py).
        self.prompts = PromptCache()
        # The built-in chat model's server (builtin_chat.py), set by the app.
        self.builtin_chat = None
        # Told when a model turns down the profile's reasoning effort (efforts.py): (config, instead, levels).
        self.learned_effort = None

    async def builtin_address(self, config: dict) -> dict:
        """The built-in chat profile asks the server where it runs now, starting it on the first reply."""
        if config.get('resource_group') != BUILTIN_CHAT or self.builtin_chat is None:
            return config
        try:
            return {**config, 'base_url': await self.builtin_chat.address()}
        except DomainError as error:
            raise DomainError(f'The built-in chat model is not running: {error.message}', 503, 'connection') \
                from error

    async def stream(self, config: dict, key: str | None, system: str, messages: list[dict]) -> AsyncIterator[Chunk]:
        provider = provider_of(config)
        if provider in {'codex', 'claude_code'}:
            cli = self.codex if provider == 'codex' else self.claude_code
            async for chunk in cli.stream(config, key, system, messages):
                yield chunk
            return
        config = efforts.known({**await self.builtin_address(config), 'provider': provider})
        validate_key(provider, key)
        REQUESTS[provider](config, system, messages)  # A broken setting fails before anything is sent.
        try:
            async with asyncio.timeout(config['timeout_seconds']):
                async with httpx.AsyncClient(transport=self.transport, timeout=config['timeout_seconds'],
                                             follow_redirects=False, **network(config['base_url'])) as client:
                    async for chunk in self.send(client, config, key, system, messages):
                        yield chunk
        except (httpx.TimeoutException, TimeoutError) as error:
            raise DomainError('The reply reached the configured time limit. Partial text is saved.', 504,
                              'timeout') from error
        except httpx.RequestError as error:
            raise DomainError('Cannot reach the model service. Check the address and that it is running.', 502,
                              'connection') from error

    async def send(self, client, config, key, system, messages) -> AsyncIterator[Chunk]:
        """One request; when the model turns down the reasoning effort, once more with one it takes (efforts.py)."""
        sent = False
        try:
            async for chunk in self.ask(client, config, key, system, messages):
                sent = True
                yield chunk
            return
        except Rejected as error:
            if sent or not efforts.turned_down(config, error.said):
                raise
            instead, levels = efforts.replacement(config, error.said)
            if self.learned_effort:
                self.learned_effort(config, instead, levels)
        async for chunk in self.ask(client, {**config, 'reasoning_effort': instead}, key, system, messages):
            yield chunk

    async def ask(self, client, config, key, system, messages) -> AsyncIterator[Chunk]:
        path, body = REQUESTS[config['provider']](config, system, messages)
        body = {**body, **await self.prompts.prepare(client, config, system)}
        async for chunk in self.request(client, config, key, path, body):
            yield chunk

    async def request(self, client, config, key, path, body) -> AsyncIterator[Chunk]:
        url = config['base_url'] + path
        if config['provider'] == 'kobold':
            response = await client.post(url, headers=headers_for(config, key), json=body)
            check_status(response, body.get('model'))
            yield kobold_result(response)
            return
        model = (config['provider'], body.get('model'))
        if model in THINKS_PAST_THE_LIMIT and (lower := low_effort(config, body)):
            body = lower
        completion = Completion()
        held = []
        async for chunk in self.attempt(client, config, key, url, body, completion):
            if completion.has_text:
                for waiting in held:
                    yield waiting
                held = []
                yield chunk
            else:
                # Nothing to show yet: a reply that ends here may be all thinking and no text.
                held.append(chunk)
        if completion.spent_on_thinking() and (lighter := lighter_body(config, body)):
            # The model spent the whole reply limit thinking (Sonnet 5.5 on OpenRouter cannot turn thinking
            # off). Ask once more with less thinking and more room rather than show an empty reply.
            THINKS_PAST_THE_LIMIT.add(model)
            completion, held = Completion(), []
            async for chunk in self.attempt(client, config, key, url, lighter, completion):
                yield chunk
        else:
            for waiting in held:
                yield waiting
        if completion.reasoning and completion.finish_reason == 'length':
            # It also cuts replies short after some text, which can't be asked again once shown: from now on this
            # model is asked to think less from the start.
            THINKS_PAST_THE_LIMIT.add(model)
        completion.validate()

    async def attempt(self, client, config, key, url, body, completion) -> AsyncIterator[Chunk]:
        parser = PARSERS[config['provider']]
        for attempt in range(RATE_LIMIT_ATTEMPTS):
            async with client.stream('POST', url, headers=headers_for(config, key), json=body) as response:
                if response.status_code == 429 and attempt + 1 < RATE_LIMIT_ATTEMPTS:
                    # Hosted models answer 429 for a few seconds at busy times; one short wait usually clears it.
                    await asyncio.sleep(retry_delay(response))
                    continue
                await raise_for_status(response, body.get('model'))
                async for data in sse_data(response):
                    chunk = Chunk(done=True) if data.get('_done') else parser(data)
                    completion.observe(chunk)
                    if chunk.text or chunk.finish_reason:
                        yield chunk
            break

    async def check(self, config: dict, key: str | None) -> dict:
        """List the service's models without generating anything."""
        cli = {'codex': (self.codex, 'Codex'), 'claude_code': (self.claude_code, 'Claude Code')}.get(config['provider'])
        if cli:
            try:
                return await cli[0].check(config, key)
            except (OSError, NotImplementedError) as error:
                raise DomainError(f'The {cli[1]} CLI could not be started on this computer: '
                                  f'{error or type(error).__name__}', 502, 'provider') from error
        config = await self.builtin_address(config)
        validate_key(config['provider'], key)
        async with httpx.AsyncClient(transport=self.transport, timeout=15, follow_redirects=False,
                                     **network(config['base_url'])) as client:
            return await check_with_deadline(discover_models, client, config, key)

    async def usage(self, profile_key: tuple, config: dict, key: str | None, fresh: bool = False) -> dict | None:
        """Credits or plan limits when the service reports them for free; None otherwise."""
        return await balance.cached(profile_key, config, key, fresh, transport=self.transport, codex=self.codex)


# (provider, model) pairs that ran out of reply room while reasoning, for this run of the app.
THINKS_PAST_THE_LIMIT: set[tuple[str, str | None]] = set()
OUTPUT_LIMITS = ('max_tokens', 'max_completion_tokens', 'max_output_tokens')


def lighter_body(config: dict, body: dict) -> dict | None:
    """The same request with twice the output room and, unless the user chose a thinking setting, low effort."""
    limits = [key for key in OUTPUT_LIMITS if key in body]
    if not limits:
        return None
    lighter = low_effort(config, body) or {**body}
    for key in limits:
        lighter[key] = lighter[key] * 2
    return lighter


def low_effort(config: dict, body: dict) -> dict | None:
    """The same request asking for low reasoning effort, or None when the user chose a thinking setting."""
    if config.get('reasoning_effort') or config.get('thinking_mode'):
        return None
    if config['provider'] in {'openrouter', 'openai'}:
        return {**body, 'reasoning': {'effort': 'low'}}
    if config['provider'] == 'anthropic':
        return {**body, 'output_config': {**body.get('output_config', {}), 'effort': 'low'}}
    return None


def kobold_result(response: httpx.Response) -> Chunk:
    try:
        text = response.json()['results'][0]['text']
        require(isinstance(text, str), 'Kobold returned an invalid text result.', 502)
        return Chunk(text, 'stop', done=True)
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise DomainError('Kobold did not return a readable reply.', 502) from error
