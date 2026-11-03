"""The Sidebar Assistant's API (adventure/assistant.py, docs/assistant.md)."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import Field

from adventure import assistant
from adventure.models import Input

router = APIRouter(prefix='/api/assistant')


class AssistantTurn(Input):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=4000)


class AssistantAsk(Input):
    message: str = Field(min_length=1, max_length=8000)
    history: list[AssistantTurn] = Field(default_factory=list, max_length=10)
    view: str = Field('story', max_length=60)
    focus_message_id: str | None = Field(None, max_length=80)


@router.post('/chat')
async def chat(request: Request, body: AssistantAsk):
    """One message to the sidebar: its reply and the changes it proposes. Nothing is stored or applied."""
    return await assistant.chat(request.app.state, body)
