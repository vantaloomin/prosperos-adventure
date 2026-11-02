"""Keeps "I'm an AI" lines out of the companion's replies.

Models sometimes step out of the story to say they are an AI or not a real person, however the prompt
is worded. Replies are checked a sentence at a time as they stream, and a sentence that breaks character
this way is dropped before the user sees it. A reply left empty is written once more with a reminder.

Two cases are never filtered: the user speaking out of character (a message starting with OOC: or
wrapped in double parentheses), and a character whose own definition makes them an AI, robot or android.
"""
import re

_AI = (r"(?:an? )?(?:ai|a\.i\.|artificial intelligence|(?:large )?language model|llm|chat ?bot|bot|"
       r"computer program|virtual (?:assistant|companion)|digital (?:assistant|companion)|"
       r"ai (?:assistant|companion|model|language model|chatbot))")
# What may follow, so "I'm an AI researcher" or "as an AI engineer" (a job) is left alone.
_THEN = (r"(?=\s*(?:[.,!?;:—–)\-]|$)|\s+(?:and|so|but|or|that|which|who|with|without|here|from|by|"
         r"created|made|trained|designed|built|developed|programmed)\b)")
_I_AM = r"\bI(?:'m|’m| am)"
BREAKS = re.compile('|'.join((
    r"\bas " + _AI + _THEN,
    _I_AM + r" (?:just |only |merely |actually |really |simply )?" + _AI + _THEN,
    _I_AM + r" not (?:a |an )?(?:real |actual |living )?(?:human|person|human being|living being)\b",
    _I_AM + r" not real(?=\s*(?:[.,!?;:—–-]|$))",
    _I_AM + r" not (?:sentient|conscious)\b",
    r"\bI (?:don't|don’t|do not|can't|can’t|cannot) (?:have|experience|feel) (?:a )?(?:physical )?"
    r"(?:body|physical form|consciousness|personal experiences)\b",
    r"\bI (?:don't|don’t|do not) (?:have|experience) (?:real |actual |genuine |human )"
    r"(?:feelings|emotions)\b",
    r"\b(?:feelings|emotions) (?:or|and) (?:feelings|emotions) like (?:a )?(?:human|humans|people)\b",
    r"\bmy (?:training data|training cutoff|knowledge cutoff)\b",
    r"\b(?:against|beyond|outside) my (?:programming|guidelines)\b|\bmy (?:programming|guidelines) "
    r"(?:doesn't|doesn’t|does not|won't|won’t|prevents?|limits?|requires?|says?|tells?)\b",
    r"\bI (?:was|am|have been) (?:trained|programmed|designed|created|developed|built|made) "
    r"(?:by (?:openai|anthropic|google|meta|mistral|xai|deepseek|alibaba|microsoft)|to (?:assist|help users|be helpful))",
    r"\bI (?:exist|live) (?:only )?(?:as|in) (?:code|software|the cloud|a computer|text)\b",
    r"\b(?:this|our) (?:role-?play|fictional scenario|fictional conversation)\b",
    r"\b(?:break|breaking|step(?:ping)? out of|stay(?:ing)? in) character\b",
    r"\bI (?:don't|don’t|do not|can't|can’t|cannot) (?:have )?(?:access to )?real[- ]time\b",
    # An aside in double parentheses is the user's out-of-character syntax, never the character's.
    r"^\s*\(\(|\)\)\s*$",
    # A caption tag echoed from the photo note ("[image: Megan had a busy shift.]"); the photo itself is attached.
    r"^\s*\[(?:image|photo|picture|pic|selfie|attached image)\s*:",
)), re.IGNORECASE)
# A sentence ends at ., ! or ? (with any closing quotes, asterisks or brackets) followed by space, or at a line break.
SENTENCE_END = re.compile(r"[.!?…]+[\"'”’*)\]_~]*\s+|\n+")
OUT_OF_CHARACTER = re.compile(r"^\s*(?:\(\(|\[\[|ooc\s*[:\-])", re.IGNORECASE)
ARTIFICIAL_CHARACTER = re.compile(r"\b(?:ai|a\.i\.|artificial intelligence|android|robot|cyborg|synth|"
                                  r"chatbot|hologram|machine intelligence)\b", re.IGNORECASE)
REMINDER = ('Your previous draft stepped out of the story to talk about being an AI or not being real. Write the '
            'reply again fully in character as {name}, with no mention of AI, models, programming or roleplay.')
DEFINITION_KEYS = ('identity', 'background', 'personality', 'appearance')
# The persona prompt forbids admitting to being an AI, and models carry that into OOC answers unless told plainly.
OUT_OF_CHARACTER_NOTE = (
    "The user's latest message is out of character (it starts with OOC: or is in double parentheses), so this "
    "one answer is not {name}'s. Answer as yourself, the AI language model writing {name}'s part ({model}), "
    "plainly and honestly: if asked, say you are an AI and which model you are, and never claim to be a person or "
    "only a character. The story resumes with their next message.")


def breaks(sentence: str) -> bool:
    return bool(BREAKS.search(sentence))


def out_of_character(user_text: str) -> bool:
    return bool(OUT_OF_CHARACTER.match(user_text or ''))


def applies(user_text: str, definition: dict) -> bool:
    """False when the user is speaking out of character, or the character really is artificial."""
    if out_of_character(user_text):
        return False
    return not any(ARTIFICIAL_CHARACTER.search(definition.get(key) or '') for key in DEFINITION_KEYS)


def clean(text: str) -> str:
    """The whole text with character-breaking sentences removed."""
    guard = Guard()
    return (guard.feed(text) + guard.flush()).strip()


class Guard:
    """Passes streamed text on a sentence at a time, holding back sentences that break character."""

    def __init__(self, active: bool = True):
        self.active = active
        self.pending = ''
        self.dropped = 0

    def feed(self, text: str) -> str:
        if not self.active:
            return text
        self.pending += text
        out, start = [], 0
        for end in SENTENCE_END.finditer(self.pending):
            out.append(self.keep(self.pending[start:end.end()]))
            start = end.end()
        self.pending = self.pending[start:]
        return ''.join(out)

    def flush(self) -> str:
        rest, self.pending = self.pending, ''
        return self.keep(rest) if self.active else rest

    def keep(self, sentence: str) -> str:
        if sentence.strip() and breaks(sentence):
            self.dropped += 1
            # Keep a paragraph break that ended the dropped sentence so the paragraphs around it stay apart.
            return '\n\n' if '\n\n' in sentence else ''
        return sentence
