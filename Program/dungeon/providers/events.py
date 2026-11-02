"""Stream events from each provider, reduced to text and a finish reason.

Adapted from prosperos-study server/providers/events.py at bbcbde4. Changes: events are the
Companion's `Chunk` (text and a normalized finish reason) plus completion facts, and failures
keep the Companion's wording.
"""
from dataclasses import dataclass, field

from dungeon.errors import DomainError


@dataclass
class Chunk:
    text: str = ''
    finish_reason: str | None = None
    done: bool = False
    reasoning: bool = False
    usage: dict = field(default_factory=dict)


ALLOWED = {'stop', 'length', 'content_filter', 'tool_calls', 'function_call'}


def openai_event(data: dict) -> Chunk:
    kind = data.get('type')
    if kind == 'response.output_text.delta':
        return Chunk(data['delta'])
    if kind in {'response.completed', 'response.incomplete'}:
        response = data['response']
        usage = dict(response.get('usage') or {})
        reason = 'stop'
        if kind == 'response.incomplete':
            detail = (response.get('incomplete_details') or {}).get('reason')
            reason = {'max_output_tokens': 'length', 'content_filter': 'content_filter'}.get(detail, 'unrecognized')
        thinking = bool((usage.get('output_tokens_details') or {}).get('reasoning_tokens', 0))
        return Chunk('', reason, done=True, reasoning=thinking, usage=usage)
    if kind in {'error', 'response.failed'}:
        raise DomainError('The provider did not complete this reply.', 502, 'provider')
    return Chunk()


ANTHROPIC_REASONS = {'end_turn': 'stop', 'stop_sequence': 'stop', 'max_tokens': 'length', 'tool_use': 'tool_calls',
                     'refusal': 'content_filter'}


def anthropic_event(data: dict) -> Chunk:
    kind = data.get('type')
    if kind == 'content_block_delta':
        delta = data.get('delta', {})
        return Chunk(delta.get('text', ''), reasoning=delta.get('type') == 'thinking_delta')
    if kind == 'message_start':
        return Chunk(usage=data['message'].get('usage', {}))
    if kind == 'message_delta':
        reason = data.get('delta', {}).get('stop_reason')
        return Chunk('', ANTHROPIC_REASONS.get(reason, 'unrecognized') if reason else None,
                     usage=dict(data.get('usage') or {}))
    if kind == 'error':
        raise DomainError('The provider interrupted this reply.', 502, 'provider')
    return Chunk(done=kind == 'message_stop')


def google_event(data: dict) -> Chunk:
    if data.get('error') or data.get('promptFeedback', {}).get('blockReason'):
        raise DomainError('Google could not return this reply. Choose another model or try again.', 502, 'provider')
    candidates = data.get('candidates', [])
    candidate = candidates[0] if candidates else {}
    finish = candidate.get('finishReason')
    parts = candidate.get('content', {}).get('parts', [])
    text = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
    usage = dict(data.get('usageMetadata') or {})
    reason = {'STOP': 'stop', 'MAX_TOKENS': 'length', 'SAFETY': 'content_filter'}.get(finish, 'unrecognized') \
        if finish else None
    thinking = any(part.get('thought') for part in parts) or bool(usage.get('thoughtsTokenCount', 0))
    return Chunk(text, reason, done=bool(finish), reasoning=thinking, usage=usage)


def chat_event(data: dict) -> Chunk:
    if data.get('error'):
        raise DomainError('The provider reported a generation error. Check the selected model.', 502, 'provider')
    choices = data.get('choices') or [{}]
    choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = choice.get('delta') or {}
    usage = dict(data.get('usage') or {})
    reason = choice.get('finish_reason')
    if reason:
        reason = reason if reason in ALLOWED else 'unrecognized'
    tokens = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens', 0)
    thinking = (isinstance(tokens, (int, float)) and tokens > 0) or any(
        delta.get(key) for key in ('reasoning_content', 'reasoning', 'reasoning_details'))
    text = delta.get('content') if isinstance(delta.get('content'), str) else ''
    return Chunk(text, reason, reasoning=thinking, usage=usage)
