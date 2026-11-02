"""OpenAI-compatible embeddings for semantic recall (PRD M10).

The Dungeon never downloads embedding weights: semantic recall uses the `/embeddings` endpoint of
the model profile assigned to recall when it names an embedding model, or the built-in llama.cpp server
the user set up with a model file they downloaded (`builtin_recall.py`), and keyword recall alone
otherwise. Only OpenAI, local and OpenAI-compatible profiles offer embeddings.
"""
import asyncio
import math

import httpx

from dungeon.errors import DomainError, require
from dungeon.providers.chat import check_status, provider_of
from dungeon.providers.config import EMBEDDING_PROVIDERS
from dungeon.providers.requests import headers_for, validate_key
from dungeon.providers.urls import network

# Embedding the message being answered must not hold up the reply for long.
QUERY_TIMEOUT = 2
# The built-in server reads at most 2,048 tokens per text; longer texts are cut rather than refused.
BUILTIN_TEXT_LIMIT = 6000

# Retrieval models trained with instructions search better with them: (name contains, query, document).
PROMPTS = (
    ('embeddinggemma', 'task: search result | query: ', 'title: none | text: '),
    ('qwen3-embedding', 'Instruct: Given a chat message, retrieve memories and earlier messages that relate to it'
     '\nQuery: ', ''),
    ('nomic-embed-text', 'search_query: ', 'search_document: '),
    ('mxbai-embed-large', 'Represent this sentence for searching relevant passages: ', ''),
    ('snowflake-arctic-embed', 'Represent this sentence for searching relevant passages: ', ''),
)
# Stored vectors made with instructions are kept apart from older plain ones, so they are re-made once.
PROMPTED = '#prompted-1'


def prompts_for(config) -> tuple[str, str] | None:
    name = (config.get('embedding_model') or '').lower()
    return next(((query, document) for marker, query, document in PROMPTS if marker in name), None)


def vector_model(config) -> str:
    """The name stored vectors are kept under for this setup."""
    return config['embedding_model'] + (PROMPTED if prompts_for(config) else '')


def as_query(config, text: str) -> str:
    prompts = prompts_for(config)
    return prompts[0] + text if prompts else text


def as_documents(config, texts: list[str]) -> list[str]:
    prompts = prompts_for(config)
    return [prompts[1] + text for text in texts] if prompts else texts


class EmbeddingProvider:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport
        # The built-in server (builtin_recall.BuiltinRecall), set by the app.
        self.builtin = None

    async def embed(self, config: dict, key: str | None, texts: list[str], timeout: float | None = None
                    ) -> list[list[float]]:
        """One vector per text, in order."""
        limit = timeout or config['timeout_seconds']
        provider = provider_of(config)
        require(provider in EMBEDDING_PROVIDERS, 'Embeddings need an OpenAI, NanoGPT, local or OpenAI-compatible profile.', 409)
        validate_key(provider, key)
        headers = headers_for({'provider': provider}, key)
        base_url = config['base_url']
        if config.get('builtin'):
            require(self.builtin is not None, 'Built-in recall is not available here.', 409)
            texts = [text[:BUILTIN_TEXT_LIMIT] for text in texts]
        body = {'model': config['embedding_model'], 'input': texts}
        try:
            async with asyncio.timeout(limit):
                if config.get('builtin'):
                    base_url = await self.builtin.address()
                async with httpx.AsyncClient(transport=self.transport, timeout=limit, follow_redirects=False,
                                             **network(base_url)) as client:
                    response = await client.post(base_url + '/embeddings', headers=headers, json=body)
                    check_status(response)
                    data = response.json().get('data')
        except (httpx.TimeoutException, TimeoutError) as error:
            raise DomainError('The embedding request timed out.', 504, 'timeout') from error
        except (httpx.RequestError, ValueError) as error:
            raise DomainError('Cannot reach the embedding service.', 502, 'connection') from error
        require(isinstance(data, list) and len(data) == len(texts), 'The service returned the wrong embeddings.', 502)
        ordered = sorted(data, key=lambda item: item.get('index', 0))
        vectors = [item.get('embedding') for item in ordered]
        require(all(isinstance(vector, list) and vector for vector in vectors), 'The service returned empty embeddings.',
                502)
        return [[float(value) for value in vector] for vector in vectors]


def cosine(left, right) -> float:
    """How alike two vectors point: 1 the same way, 0 unrelated (0 for vectors of different sizes)."""
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0
