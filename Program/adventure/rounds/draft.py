"""The turn draft: everything a turn has made before it is committed (docs/spec.md "Turn state and persistence": "Steps
1 to 8 build a turn draft nothing else reads; step 9 commits it in one transaction").

Steps write only here. Nothing in the record, anyone's memory or feelings changes until Commit
(adventure/rounds/engine.py `commit`) writes the draft in one SQLite transaction, so a cancelled turn, a crash or a
re-ask leaves no trace. The draft is kept with the turn as JSON after every step: a turn waiting on the user's reply
picks up from it after a restart.

- `declarations`: each seat's Declaration from Declare, replaced by its reaction in React (the first one is kept in
  `declared` for the minds panel and for re-asking).
- `knowledge`: what each character learned this turn, with its holder. Contexts built later in the turn read it as
  in-turn knowledge; Commit turns each item into a memory. Code adds every item; a model never names a holder.
- `feelings`: changes to how one character feels toward another, written at Commit.
- `exchanges`: the Converse step's questions and answers, in order.
- `awaiting`: the reply card, while the turn waits on a human seat; `replies` keeps each answer by seat.
- `result`: Resolve's TurnResult. `post`: the Writer's text.
- `extra`: room for each workstream's own staged data, under its own key, committed by its own commit hook.
"""
from dataclasses import dataclass, field

from adventure.rounds.contract import Declaration, Knowledge, TurnResult, built, plain


@dataclass
class Draft:
    declared: dict[str, Declaration] = field(default_factory=dict)
    declarations: dict[str, Declaration] = field(default_factory=dict)
    knowledge: list[Knowledge] = field(default_factory=list)
    feelings: list[dict] = field(default_factory=list)
    refreshed: list[dict] = field(default_factory=list)
    exchanges: list[dict] = field(default_factory=list)
    awaiting: dict | None = None
    replies: dict[str, dict] = field(default_factory=dict)
    result: TurnResult | None = None
    post: str = ''
    extra: dict = field(default_factory=dict)

    # Staging ------------------------------------------------------------------------------------------------------

    def declare(self, declaration: Declaration):
        self.declarations[declaration.seat] = declaration
        self.declared.setdefault(declaration.seat, declaration)

    def learn(self, holder: str, kind: str, text: str, *, source: str = '', about: str = '', importance: int = 1):
        if text.strip():
            self.knowledge.append(Knowledge(holder, kind, text.strip(), source, about, importance))

    def feel(self, from_key: str, to_key: str, changes: dict[str, int], why: str = ''):
        if from_key != to_key:
            self.feelings.append({'from': from_key, 'to': to_key, 'changes': dict(changes), 'why': why})

    def bring_back(self, holder: str, memory_id: str):
        """A memory of `holder`'s mentioned again: fresh from this turn once committed."""
        self.refreshed.append({'holder': holder, 'memory_id': memory_id})

    def wait_for(self, seat: str, speaker: str, line: str, context: list[str]):
        """Pause the turn on the reply card for `seat` (adventure/rounds/engine.py stops after the step)."""
        self.awaiting = {'seat': seat, 'speaker': speaker, 'line': line, 'context': context[-2:]}

    def known_to(self, holder: str) -> list[Knowledge]:
        """`holder`'s in-turn knowledge so far."""
        return [item for item in self.knowledge if item.holder == holder]

    # JSON ---------------------------------------------------------------------------------------------------------

    def data(self) -> dict:
        return {'declared': {key: plain(value) for key, value in self.declared.items()},
                'declarations': {key: plain(value) for key, value in self.declarations.items()},
                'knowledge': [plain(item) for item in self.knowledge], 'feelings': self.feelings,
                'refreshed': self.refreshed, 'exchanges': self.exchanges, 'awaiting': self.awaiting,
                'replies': self.replies, 'result': plain(self.result) if self.result else None, 'post': self.post,
                'extra': self.extra}

    @classmethod
    def of(cls, data: dict | None) -> 'Draft':
        data = data or {}
        return cls(declared={key: Declaration.of(value) for key, value in data.get('declared', {}).items()},
                   declarations={key: Declaration.of(value) for key, value in data.get('declarations', {}).items()},
                   knowledge=[built(Knowledge, item) for item in data.get('knowledge', [])],
                   feelings=data.get('feelings', []), refreshed=data.get('refreshed', []),
                   exchanges=data.get('exchanges', []), awaiting=data.get('awaiting'),
                   replies=data.get('replies', {}),
                   result=TurnResult.of(data['result']) if data.get('result') else None, post=data.get('post', ''),
                   extra=data.get('extra', {}))
