"""A reasoning effort the model turns down is swapped for the nearest one it takes, rather than failing the request.

Services do not list the effort levels a model takes (OpenAI's model list says nothing about them), so a profile can
ask for one the model refuses. OpenAI answers HTTP 400 with words such as "Unsupported value: 'minimal' is not
supported with this model. Supported values are: 'none', 'low', 'medium', and 'high'." The app reads the levels it
names, asks again with the nearest one (or with no effort, when it names none), and remembers the answer for this run
of the app. The chat provider also hands it to `learned`, which updates the profile (text_models.learn_effort), so
Settings > Models offers only the levels the model takes. The user can still pick another one there.
"""
import re

from dungeon.providers.capabilities import EFFORTS

LEVEL = re.compile(r'\b(' + '|'.join(EFFORTS) + r')\b')
ABOUT_EFFORT = re.compile(r'reasoning|effort', re.IGNORECASE)
TURNED_DOWN = re.compile(r'not support|unsupported|unrecognized|invalid|not allowed|must be one of', re.IGNORECASE)

# (provider, base_url, model, rejected effort) -> the effort to send instead (None: send none), for this run.
REPLACED: dict[tuple, str | None] = {}


def model_key(config: dict, effort: str) -> tuple:
    return config.get('provider'), config.get('base_url'), config.get('model'), effort


def turned_down(config: dict, said: str) -> bool:
    """Whether a refusal is about the reasoning effort this request asked for."""
    effort = config.get('reasoning_effort')
    return bool(effort) and bool(ABOUT_EFFORT.search(said)) and \
        (re.search(rf'\b{effort}\b', said, re.IGNORECASE) is not None or bool(TURNED_DOWN.search(said)))


def supported(said: str, effort: str) -> list[str] | None:
    """The levels the refusal names as supported, in order, or None when it names none."""
    at = said.lower().rfind('support')
    tail = said[at:].lower() if at >= 0 else ''
    named = {level for level in LEVEL.findall(tail) if level != effort}
    return [level for level in EFFORTS if level in named] or None


def nearest(effort: str, levels: list[str] | None) -> str | None:
    """The supported level closest to the one asked for; between two equally close, the lighter one."""
    if not levels:
        return None
    wanted = EFFORTS.index(effort)
    return min(levels, key=lambda level: (abs(EFFORTS.index(level) - wanted), EFFORTS.index(level)))


def replacement(config: dict, said: str) -> tuple[str | None, list[str] | None]:
    """The effort to ask with instead and the levels the model takes, and remembers them for this model."""
    effort = config['reasoning_effort']
    levels = supported(said, effort)
    instead = nearest(effort, levels)
    REPLACED[model_key(config, effort)] = instead
    return instead, levels


def known(config: dict) -> dict:
    """The request settings with an effort this model already turned down swapped for its replacement."""
    effort = config.get('reasoning_effort')
    key = model_key(config, effort)
    return {**config, 'reasoning_effort': REPLACED[key]} if effort and key in REPLACED else config
