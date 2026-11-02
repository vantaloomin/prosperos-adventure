"""Provider presets and model profile settings.

Adapted from prosperos-study server/providers/config.py at bbcbde4. Changes: the LM Studio native
protocol and its reasoning control are not offered (local servers use the OpenAI-compatible API),
environment fallbacks use Dungeon names for local and compatible services, and Codex text
generation runs through the same CLI login the image backend uses.
"""
import os
from typing import ClassVar, Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, model_validator

from dungeon.errors import DomainError
from dungeon.models import Input
from dungeon.providers.capabilities import validate_options
from dungeon.providers.urls import is_loopback, validate_compatible_url

Provider = Literal['openai', 'anthropic', 'openrouter', 'google', 'nanogpt', 'compatible', 'local', 'kobold', 'codex',
                   'claude_code']
PROVIDER_NAMES = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'openrouter': 'OpenRouter',
                  'google': 'Google / Gemini', 'nanogpt': 'NanoGPT', 'compatible': 'OpenAI-compatible API', 'local': 'Local / LM Studio',
                  'kobold': 'Kobold', 'codex': 'Codex / ChatGPT',
                  'claude_code': 'Claude Code / Claude plan'}
DEFAULT_URLS = {
    'openai': 'https://api.openai.com/v1',
    'anthropic': 'https://api.anthropic.com/v1',
    'openrouter': 'https://openrouter.ai/api/v1',
    'google': 'https://generativelanguage.googleapis.com/v1beta',
    'nanogpt': 'https://nano-gpt.com/api/v1',
    'compatible': '',
    'local': 'http://127.0.0.1:1234/v1',
    'kobold': 'http://127.0.0.1:5001/api/v1',
    'codex': '',
    'claude_code': '',
}
# Providers that run a program on this computer under its own login: no address and no key.
CLI_PROVIDERS = {'codex', 'claude_code'}
# Standard variable names for hosted services; the Companion's own name for anything else.
ENV_KEYS = {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY', 'openrouter': 'OPENROUTER_API_KEY',
            'google': 'GEMINI_API_KEY', 'nanogpt': 'NANOGPT_API_KEY', 'compatible': 'DUNGEON_API_KEY', 'local': 'DUNGEON_API_KEY'}
# Providers whose official API needs a key; local servers and compatible services may not.
NEEDS_KEY = {'openai', 'anthropic', 'openrouter', 'google', 'nanogpt'}
EMBEDDING_PROVIDERS = {'openai', 'nanogpt', 'compatible', 'local'}
# Decision models answer typed questions with probabilities and write no text: Jev through OpenRouter's decisions
# API, OpenAI's decisions API, or any model on a local or compatible server, scored by the odds of each answer's
# letter (dungeon/providers/decisions.py).
DECISION_PROVIDERS = {'openrouter', 'openai', 'local', 'compatible'}
# Text profiles on these servers can answer decisions the same way, so the narrator's own local model can.
SCORED_PROVIDERS = {'local', 'compatible'}


def validate_local_url(url: str):
    parts = urlsplit(url)
    if parts.scheme not in {'http', 'https'} or not is_loopback(parts.hostname):
        raise ValueError('Local services must use a localhost or loopback HTTP(S) address.')
    if any((parts.username, parts.password, parts.query, parts.fragment)):
        raise ValueError('Put credentials in the API key field, not in the server address.')


def validate_profile_url(provider, url, allow_incomplete=False):
    if provider in {'local', 'kobold'}:
        validate_local_url(url)
    elif provider == 'compatible':
        if url or not allow_incomplete:
            try:
                validate_compatible_url(url)
            except DomainError as error:
                raise ValueError(error.message) from error
    elif url != DEFAULT_URLS[provider]:
        raise ValueError('This provider uses its official API address.')


def is_recall(config) -> bool:
    return config.get('purpose') == 'recall'


def is_decisions(config) -> bool:
    return config.get('purpose') == 'decisions'


def profile_ready(config) -> bool:
    """A text profile with a model can do every job but recall (and decisions, when its server can score them)."""
    return config.get('purpose', 'text') == 'text' and bool(config.get('model', '').strip()) and \
        (config['provider'] in CLI_PROVIDERS or bool(config.get('base_url')))


def decisions_ready(config) -> bool:
    """A decisions profile with a model, or a finished text profile on a local or compatible server."""
    if profile_ready(config):
        return config['provider'] in SCORED_PROVIDERS
    return is_decisions(config) and bool(config.get('model', '').strip()) and \
        config['provider'] in DECISION_PROVIDERS and bool(config.get('base_url'))


def recall_ready(config) -> bool:
    """A recall profile with an embedding model can do recall, and only recall."""
    return is_recall(config) and bool((config.get('embedding_model') or '').strip()) and \
        config['provider'] in EMBEDDING_PROVIDERS and bool(config.get('base_url'))


def ready_for(config, job: str) -> bool:
    if job == 'decisions':
        return decisions_ready(config)
    return recall_ready(config) if job == 'recall' else profile_ready(config)


class ReportedCapabilities(Input):
    model_id: str
    context_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    supported_parameters: list[str] | None = Field(default=None, max_length=100)
    supported_efforts: list[str] | None = Field(default=None, max_length=20)


class ProfileConfig(Input):
    allow_incomplete: ClassVar[bool] = False
    provider: Provider
    model: str = Field(min_length=1, max_length=200)
    base_url: str = ''
    max_output_tokens: int = Field(default=800, ge=64, le=128000)
    context_tokens: int = Field(default=16000, ge=1024, le=2000000)
    timeout_seconds: int = Field(default=180, ge=10, le=1800)
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: Literal['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'] | None = None
    top_p: float | None = Field(default=None, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0, le=1000)
    min_p: float | None = Field(default=None, ge=0, le=1)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    repetition_penalty: float | None = Field(default=None, gt=0, le=3)
    seed: int | None = Field(default=None, ge=0, le=2147483647)
    thinking_mode: Literal['off', 'budget', 'adaptive'] | None = None
    thinking_budget_tokens: int | None = Field(default=None, ge=-1, le=128000)
    response_reserve_tokens: int = Field(default=256, ge=64, le=128000)
    response_verbosity: Literal['low', 'medium', 'high'] | None = None
    compatible_thinking: bool | None = None
    output_token_parameter: Literal['max_tokens', 'max_completion_tokens'] = 'max_tokens'
    reported_capabilities: ReportedCapabilities | None = None
    resource_group: str = Field(default='', max_length=80, pattern=r'^[a-zA-Z0-9 _.-]*$')
    # Text profiles write; recall profiles only turn text into embeddings for semantic recall, through
    # the service's /embeddings with embedding_model, so recall can use a different service from replies.
    # Decisions profiles only answer the Referee's questions with probabilities.
    purpose: Literal['text', 'recall', 'decisions'] = 'text'
    embedding_model: str = Field(default='', max_length=200)
    # Where the Claude Code CLI is installed, when it is not on PATH. Models are set up on the PC only.
    cli_path: str = Field(default='', max_length=500)
    # The folder that keeps this profile's own Claude account (CLAUDE_CONFIG_DIR), so two accounts can each have a
    # profile; empty uses the account Claude Code is usually signed in to.
    cli_account_dir: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def validate_capabilities(self, info: ValidationInfo):
        self.base_url = (self.base_url or DEFAULT_URLS[self.provider]).rstrip('/')
        validate_profile_url(self.provider, self.base_url, self.allow_incomplete)
        if self.provider == 'codex' and self.temperature is not None:
            raise ValueError('Codex CLI does not support a temperature setting here.')
        self.cli_path = self.cli_path.strip()
        if self.cli_path and (self.provider != 'claude_code' or not os.path.isabs(self.cli_path)):
            raise ValueError('The Claude Code location must be a full path to the program on this computer.')
        self.cli_account_dir = self.cli_account_dir.strip()
        if self.cli_account_dir and (self.provider != 'claude_code' or not os.path.isabs(self.cli_account_dir)):
            raise ValueError('The Claude account folder must be a full path to a folder on this computer.')
        if self.provider == 'claude_code' and self.reasoning_effort not in {None, 'low', 'medium', 'high', 'xhigh', 'max'}:
            raise ValueError('Claude Code takes an effort of low, medium, high, xhigh or max.')
        if self.provider == 'anthropic' and self.temperature is not None and self.temperature > 1:
            raise ValueError('Anthropic temperature must be between 0 and 1.')
        if self.purpose == 'recall':
            if self.provider not in EMBEDDING_PROVIDERS:
                raise ValueError('Recall profiles need an OpenAI, NanoGPT, local or OpenAI-compatible connection.')
            self.model = ''
        elif self.embedding_model.strip():
            raise ValueError('Embedding models go in a recall profile, apart from text profiles.')
        if self.purpose == 'decisions' and self.provider not in DECISION_PROVIDERS:
            raise ValueError('Decisions profiles need OpenRouter (Jev), OpenAI, or a local or OpenAI-compatible server.')
        validate_options(self)
        return self


class DiscoveryConfig(ProfileConfig):
    model: str = Field(default='', max_length=200)


class SavedProfileConfig(ProfileConfig):
    """A profile can be saved before a model is chosen, so a key is never lost to an unfinished form."""
    allow_incomplete: ClassVar[bool] = True
    model: str = Field(default='', max_length=200)


class ConnectionProbe(Input):
    config: DiscoveryConfig
    api_key: str | None = Field(default=None, max_length=4000)
    profile_id: str | None = None


class ProfileCreate(Input):
    name: str = Field(default='', max_length=120)
    config: SavedProfileConfig
    api_key: str | None = Field(default=None, max_length=4000)
    # On an update: a new key on a profile whose key other profiles share replaces it for all of them (a rotated key
    # keeps every job working); False gives this profile a key of its own instead. A new profile has no one to share
    # with yet, so it ignores this.
    share_key: bool = True


class ProfileUpdate(ProfileCreate):
    expected_revision: int


class MixUpdate(Input):
    job: str = Field(default='story', min_length=1, max_length=40)
    profile_ids: list[str] = Field(default_factory=list, max_length=20)
    mode: str = Field(default='random', max_length=20)
    enabled: bool = True


class RouteUpdate(Input):
    job: str = Field(min_length=1, max_length=40)
    profile_id: str | None = None
