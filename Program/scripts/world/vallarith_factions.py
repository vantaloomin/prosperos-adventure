"""Vallarith's factions in play (dungeon/factions.py, docs/story.md "Factions"): the powers with a hand on the travel
map, from the world package (dungeon/world/packages/vallarith/factions.json), with the clocks they run in the Post-Reform era and what
happens when each fills. Run `python scripts/world/vallarith_factions.py` to rewrite
dungeon/world/data/factions/vallarith.json.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'dungeon' / 'world' / 'packages' / 'vallarith' / 'factions.json'
TRAVEL = ROOT / 'dungeon' / 'world' / 'data' / 'travel' / 'vallarith.json'
OUT = ROOT / 'dungeon' / 'world' / 'data' / 'factions' / 'vallarith.json'
# Chance in 100 that a clock moves on a given story day.
PACE = 25
# Where a faction has a hand beyond what the package says it holds (the Guild runs Kingswood's work).
HOLDS = {'cyrel-timber-guild': ['kingswood', 'cyrel'], 'brynwyr-high-elves': ['brynwyr', 'kingswood']}
# Each faction's tier on the shared ladder (dungeon/tiers.py): how far its reach goes, and the trouble it can send.
TIERS = {'kingdom-of-cyrel': 3, 'kingdom-of-asania': 3, 'cyrel-timber-guild': 2, 'brynwyr-high-elves': 3,
         'unguruk-tribe': 2, 'mossrun-expedition': 2}
# The clocks each faction runs here, Post-Reform: (name, segments, what happens when it fills).
CLOCKS = {
    'kingdom-of-cyrel': [
        ('War levy', 4, "Cyrel's war levy reaches the sister towns: every household gives a son to Bastion or pays "
                        'three crowns, and the crimps are out on the roads for those who run.'),
        ('Retake Adlmyr', 8, "Cyrel's army storms Adlmyr and takes the fallen walls back from the Unguruk. The road "
                             'through the Badlands is Cyrel\'s again, for now, and the graves outside Bastion are new.'),
    ],
    'kingdom-of-asania': [
        ('Push across the Cyrel border', 6, "Asania's army crosses the border on the lake road. Eriane burns, and "
                                            'refugees choke the Cyrel road all the way to Kingswood.'),
    ],
    'cyrel-timber-guild': [
        ('Buy out the sawmill', 6, "The Timber Guild buys Kingswood's sawmill outright. Wages drop by a fifth the same "
                                   'week, and the men who complain are not taken on again.'),
    ],
    'brynwyr-high-elves': [
        ('Move the border stones', 6, 'The wardens of Brynwyr move the border stones a mile toward Kingswood in one '
                                      'night, and shoot anyone who tries to move them back.'),
    ],
    'unguruk-tribe': [
        ('Siege works at Adlmyr', 6, 'The Unguruk finish their works at Adlmyr and start raiding past the ward-keep. '
                                     'Smoke rises from the farms on the Kingswood road.'),
    ],
    'mossrun-expedition': [
        ('The Deep Nine reaches what it is digging toward', 8,
         'The Deep Nine breaks into something old under Mossrun. The shaft is sealed with the night shift still in it, '
         'and the miners who came up will not say what they heard.'),
    ],
}


# The jobs each faction offers in the towns it holds, when it needs something done (dungeon/jobs.py): what the
# character is asked, what is really going on, what happens if nobody does it, the days given, the pay in day wages,
# the standing it earns, its tier (1, Local, when not given) and what it leaves behind (ties, for the story director).
JOBS = {
    'kingdom-of-cyrel': [
        {'id': 'deserter-in-the-woods', 'title': 'A deserter in the woods', 'days': 5, 'wages': 4, 'standing': 1,
         'giver': "the reeve's men",
         'hook': "The reeve's men want a deserter from Bastion found before the levy officer arrives: a local boy, "
                 'hiding somewhere in the woods with a stolen cloak.',
         'truth': "He ran because his sergeant sold the company's winter boots, and he can prove it. The sergeant "
                  'has friends in Cyrel who would rather the boy hanged quietly.',
         'missed': "The levy officer came and found no deserter, so he hanged the boy's father in his place.",
         'ties': [{'kind': 'npc', 'ref': 'the deserter'}, {'kind': 'clue', 'ref': 'the sold boots'}]},
        {'id': 'levy-rolls-to-eriane', 'title': 'The levy rolls to Eriane', 'days': 4, 'wages': 3, 'standing': 1,
         'giver': 'the reeve',
         'hook': 'The reeve needs the levy rolls carried to the magistrate in Eriane within four days, and trusts no '
                 'carter with them.',
         'truth': 'Half the names on the rolls were bought off. Someone in Eriane will pay well for the true list, '
                  "and the reeve's own nephew is not on it.",
         'missed': "The rolls never reached Eriane. Cyrel's magistrate has written to ask why, and the reeve's name "
                   'is mud.',
         'ties': [{'kind': 'item', 'ref': 'the levy rolls'}, {'kind': 'faction', 'ref': 'kingdom-of-cyrel'}]},
        {'id': 'tax-cart-on-the-eriane-road', 'title': 'The tax cart on the Eriane road', 'days': 8, 'wages': 12,
         'standing': 2, 'tier': 2, 'giver': 'the reeve',
         'hook': "The quarter's tax cart left for Cyrel with two guards and never reached Eriane. The reeve wants the "
                 'silver back, or the names of whoever took it, before Cyrel sends someone to ask.',
         'truth': 'The guards drove the cart into the Badlands themselves and sold the silver to Unguruk traders. One '
                  "is buried by the road where they quarrelled over it; the other bought a farm in his brother's name.",
         'missed': "Cyrel's assessor came and took the shortfall out of Kingswood, house by house. The reeve kept his "
                   'post by naming a widow as the thief.',
         'ties': [{'kind': 'npc', 'ref': 'the surviving guard'}, {'kind': 'faction', 'ref': 'unguruk-tribe'},
                  {'kind': 'item', 'ref': 'the tax silver'}]},
        {'id': 'terms-at-adlmyr', 'title': 'Terms at Adlmyr', 'days': 10, 'wages': 30, 'standing': 3, 'tier': 3,
         'giver': "the levy officer from Bastion",
         'hook': "Cyrel wants its sealed terms carried into Adlmyr and put in the war-chief's hand, by someone the "
                 'Unguruk will not take for a soldier.',
         'truth': 'The terms are a stall. The army marches on Adlmyr while the war-chief reads them, and the one who '
                  'carried them is meant to be inside the walls when it does.',
         'missed': 'No envoy went. The army marched anyway, and the levy officer wrote that Kingswood refused the '
                   "crown's errand.",
         'ties': [{'kind': 'item', 'ref': 'the sealed terms'}, {'kind': 'npc', 'ref': 'the Unguruk war-chief'},
                  {'kind': 'faction', 'ref': 'unguruk-tribe'}]},
    ],
    'cyrel-timber-guild': [
        {'id': 'debt-at-cutters-camp', 'title': "A debt at Cutters' Camp", 'days': 3, 'wages': 3, 'standing': 1,
         'giver': 'the Guild factor',
         'hook': "The Guild factor wants a feller's debt collected, nine crowns, by any means short of murder.",
         'truth': "The feller borrowed to bury his wife. The factor took a cut of the undertaker's fee as well, and "
                  'keeps a second ledger nobody is meant to see.',
         'missed': 'The Guild sent its own men. The feller lost two fingers and his place on the crews.',
         'ties': [{'kind': 'npc', 'ref': 'the indebted feller'}, {'kind': 'item', 'ref': "the factor's second ledger"}]},
        {'id': 'who-breaks-the-saws', 'title': 'Who breaks the saws', 'days': 6, 'wages': 5, 'standing': 2,
         'giver': 'the Guild factor',
         'hook': 'Someone has been breaking the big saws at the mill by night. The Guild pays well for a name.',
         'truth': "It is the factor's own nephew, paid by friends of the elves in town to slow the felling.",
         'missed': 'The Guild blamed the night watchman and turned him out. The saws keep breaking.',
         'ties': [{'kind': 'npc', 'ref': "the factor's nephew"}, {'kind': 'faction', 'ref': 'brynwyr-high-elves'}]},
        {'id': 'the-mossrun-survey', 'title': 'The Mossrun survey', 'days': 7, 'wages': 10, 'standing': 2, 'tier': 2,
         'giver': 'the Guild factor',
         'hook': 'The Guild wants its surveyor taken safely to Mossrun and back, to judge the timber on the hills the '
                 'diggers say are theirs.',
         'truth': "The surveyor's satchel holds Guild gold for the Deep Nine's foreman, to look away while the Guild "
                  'cuts. The foreman has already taken money from someone else to do the opposite.',
         'missed': 'The surveyor went alone and came back without the satchel or two of his teeth. The Guild says he '
                   'was robbed by the character, whoever asks.',
         'ties': [{'kind': 'npc', 'ref': 'the Guild surveyor'}, {'kind': 'faction', 'ref': 'mossrun-expedition'},
                  {'kind': 'item', 'ref': "the surveyor's satchel"}]},
    ],
    'brynwyr-high-elves': [
        {'id': 'a-message-past-the-stones', 'title': 'A message past the stones', 'days': 3, 'wages': 2,
         'standing': 1, 'giver': 'a warden of Brynwyr',
         'hook': 'A grey-fletched arrow came with a strip of bark: whoever carries a message to the reeve and keeps '
                 'quiet about it will be remembered past the stones.',
         'truth': 'The message names the night the wardens mean to burn the camp if the felling goes ahead. The reeve '
                  'already knows, and has told no one.',
         'missed': 'No one carried the message. The wardens take the silence for an answer.',
         'ties': [{'kind': 'faction', 'ref': 'brynwyr-high-elves'}, {'kind': 'item', 'ref': 'the bark message'}]},
        {'id': 'bones-under-the-felling-line', 'title': 'Bones under the felling line', 'days': 6, 'wages': 8,
         'standing': 2, 'tier': 2, 'giver': 'a warden of Brynwyr',
         'hook': "The wardens say the Guild's crews cut through a barrow past the stones. They want proof they can "
                 'lay before the reeve, and they will not cross the line to get it themselves.',
         'truth': 'The crews did cut through it, and filled it in. Under the elven dead lie older ones: men in '
                  'Brotherhood mail, killed with elven arrows, which neither side wants found.',
         'missed': 'The wardens took their own proof: a felling crew, left hanging in the trees along the line.',
         'ties': [{'kind': 'clue', 'ref': 'the opened barrow'}, {'kind': 'faction', 'ref': 'cyrel-timber-guild'}]},
    ],
}

def slug(name: str) -> str:
    return ''.join(ch if ch.isalnum() else '-' for ch in name.lower()).strip('-').replace('--', '-')


def build() -> dict:
    nodes = {node['id'] for node in json.loads(TRAVEL.read_text(encoding='utf-8'))['nodes']}
    factions = {item['id']: item for item in json.loads(SOURCE.read_text(encoding='utf-8'))['factions']}
    result = []
    for faction_id, clocks in CLOCKS.items():
        item = factions[faction_id]
        holds = HOLDS.get(faction_id) or [node for node in item.get('holds') or [] if node in nodes]
        result.append({
            'id': faction_id, 'name': item['name'], 'kind': item['kind'], 'tier': TIERS[faction_id],
            'summary': item['summary'],
            'goals': item.get('goals', []), 'holds': holds,
            'rivals': [other for other in item.get('rivals', []) if other in CLOCKS],
            'allies': [other for other in item.get('allies', []) if other in CLOCKS],
            'clocks': [{'id': slug(name), 'name': name, 'segments': segments, 'done': done}
                       for name, segments, done in clocks],
            'jobs': JOBS.get(faction_id, [])})
    return {'about': 'Built by scripts/world/vallarith_factions.py from dungeon/world/packages/vallarith/factions.json.',
            'world': 'vallarith', 'pace': PACE, 'factions': result}


FACTIONS = build()

if __name__ == '__main__':
    OUT.write_text(json.dumps(FACTIONS, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
