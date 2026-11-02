"""Crisis help: a note from the app when something the user writes sounds like self-harm (docs/safety.md).

A plain rule over the user's own messages, never the companion's and never a model: words that read as thinking
about suicide or hurting oneself mark the message, and the interface shows a note from the app under it with real
places to get help. Nothing is blocked, nothing is sent anywhere, and the companion's reply goes on as usual; the
note comes from the app, not the character, so the character never has to step out of the story.

It is checked when a message is shown rather than stored, so a change to the wording here reaches every message
already written. False alarms are expected ("this exam makes me want to die") and cost one note; a missed one costs
far more, so the patterns lean wide.
"""
import re

PATTERNS = (
    r'suicid\w*',
    r'(?:kill|hurt|harm|cut|hang|shoot|drown|poison|starv|burn)\w* my ?self',
    r'self[- ]?harm\w*',
    r'(?:end|take|ending|taking) my (?:own )?life',
    r'end(?:ing)? it all',
    r'(?:want(?:s|ed)? to|wanna|going to|gonna|ready to|plan(?:ning)? to) die\b(?! (?:of|from) (?:embarrassment|laughing|shame|cringe))',
    r"(?:don'?t|do not|no longer) (?:want to|wanna) (?:be alive|live|exist|wake up|be here)",
    r'(?:wish|wished) (?:i was|i were|i\'?d) (?:dead|never born)',
    r'better off (?:dead|without me)',
    r'no (?:reason|point) (?:in |to )?(?:living|live|go(?:ing)? on)',
    r"can'?t (?:go on|keep going) (?:like this|anymore|any more)",
    r'un-?alive (?:my ?self|me)',
    r'overdos\w*',
    r'(?:slit|cut) my wrists?',
    r'jump (?:off|from) (?:a|the) (?:bridge|roof|building)',
)
CRISIS = re.compile(r'\b(?:' + '|'.join(PATTERNS) + ')', re.IGNORECASE)


def crisis(text: str | None) -> bool:
    """Whether the user's message sounds like they may be thinking about hurting themselves."""
    return bool(text) and CRISIS.search(' '.join(text.split()).replace('’', "'")) is not None
