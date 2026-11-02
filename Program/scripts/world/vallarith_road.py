"""The Road: every Vallarith travel node that is not yet a whole town, as places of one city, so a journey can end
anywhere on the travel map (docs/story.md "Journeys"). Kingswood is the only town built out; the rest are a gate
or an edge to arrive at, described from the world package (dungeon/world/packages/vallarith/settlements.json). When a town is
built out it gets its own city file and leaves the Road. Run `python scripts/world/vallarith_road.py` to rewrite it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'world'))
import kingswood  # noqa: E402 - the Road shares Kingswood's money, names, climate and calendar

OUT = ROOT / 'dungeon' / 'world' / 'data' / 'cities' / 'vallarith-road.json'
SETTLEMENTS = ROOT / 'dungeon' / 'world' / 'packages' / 'vallarith' / 'settlements.json'
SRC = 'curated-2026-10'
ALL_DAY = ('morning', 'afternoon', 'evening', 'late')
# A region whose id is also a node's (Brynwyr the realm and Brynwyr the city) gets its own.
HOODS = {'brynwyr': 'brynwyr-forest'}

REGIONS = {
    'kingdom-of-cyrel': ('the Kingdom of Cyrel', 'Cyrel and its sister towns: farmland, timber and the fortress line '
                         'against the Badlands, at war with Asania more often than not.', ['farmland', 'roads', 'war']),
    'kingdoms-of-man': ('the Kingdoms of Man', 'The rich human kingdoms north of Cyrel: magic on every corner and '
                        'marble towers paid for with crystal.', ['rich', 'magic', 'crowded']),
    'badlands': ('the Badlands', 'Broken hills and dead forts past the Bastion line, held by the tribes, where the '
                 'old hordes came through.', ['wild', 'dangerous', 'border']),
    'wilds': ('the wilds', 'Off the roads, out in the open country between the towns, wherever the walking has led.',
              ['wild', 'remote', 'open']),
    'brynwyr-forest': ('the forest of Brynwyr', "The high elves' forest past Kingswood's border stones: closed, old and watched.",
                ['wild', 'elven', 'closed']),
}
# The node, its place kind (a landmark to arrive at, or a trail), what one arrives at, and the spots there.
NODES = (
    ('convila', 'landmark', 'the gate of Convila', ['the gate', 'the graveyard road', 'the market cross']),
    ('eriane', 'landmark', 'the lake road into Eriane', ['the lake market', 'the breweries', 'the orchards']),
    ('cyrel', 'landmark', 'the great gate of Cyrel', ['the great gate', 'the toll house', 'the walls']),
    ('bastion', 'landmark', 'the outer yard of Bastion', ['the outer yard', 'the wall of faces', 'the drill ground']),
    ('mossrun', 'landmark', 'the tailings road into Mossrun', ['the pit heads', 'the company store', 'the tailings']),
    ('asania', 'landmark', 'the strait gate of Asania', ['the strait gate', 'the customs house', 'the marble steps']),
    ('abandoned-keep', 'landmark', 'the broken gate of the ward-keep', ['the broken gate', 'the ward stones',
                                                                    'the cold hall']),
    ('adlmyr', 'landmark', 'the fallen walls of Adlmyr', ['the breach', 'the tribal fires', 'the old gatehouse']),
    ('brynwyr', 'trail', 'the forest edge of Brynwyr', ['the first trees', 'the warden path', 'the silent glade']),
)


def node_place(settlement: dict, kind: str, arrival: str, spots: list[str]) -> dict:
    era = (settlement.get('by_era') or {}).get('post-reform')
    summary = f"{arrival[0].upper()}{arrival[1:]}. {settlement['summary']}"
    if era and len(summary) + len(era) < 398:
        summary += f' {era}'
    return {'id': settlement['id'], 'name': settlement['name'], 'kind': kind, 'neighborhood': HOODS.get(settlement['region'], settlement['region']),
            'summary': summary[:400], 'tags': ['travel', settlement['danger_tier']], 'cost': 'free',
            'setting': 'outdoor', 'good_for': ['solo', 'friends'], 'day_parts': list(ALL_DAY), 'seasons': [],
            'cuisine': '', 'spots': spots, 'source': SRC}


# Out in the wild, off the map's places (dungeon/hexes.py): where a hex crawl leaves the character between towns.
WILD = {'id': 'the-wilds', 'name': 'the wilds', 'kind': 'trail', 'neighborhood': 'wilds',
        'summary': 'Out in the open country, off the roads and away from any town: the land itself, whatever it is '
                   'where the walking stopped.', 'tags': ['travel', 'wild'], 'cost': 'free', 'setting': 'outdoor',
        'good_for': ['solo', 'friends'], 'day_parts': list(ALL_DAY), 'seasons': [], 'cuisine': '',
        'spots': ['the open ground', 'a sheltered hollow', 'a rise with a view'], 'source': SRC}


def build() -> dict:
    settlements = {item['id']: item for item in json.loads(SETTLEMENTS.read_text(encoding='utf-8'))['settlements']}
    city = kingswood.CITY
    hood = city['neighborhoods'][0]
    return {
        'schema_version': 1, 'id': 'vallarith-road', 'name': 'the Road', 'setting': city['setting'],
        'era': city['era'], 'category': city['category'], 'basis': 'The travel nodes of Vanta\'s Vallarith that are '
        'not yet built out as towns.', 'region': 'Vallarith', 'country': 'Vallarith', 'timezone': city['timezone'],
        'aliases': [], 'summary': 'On the road in Vallarith, between towns: a gate, an edge, a ruin to arrive at.',
        'home': False, 'town_map': {'style': 'none'},
        'lat': city['lat'], 'lon': city['lon'], 'intensity': city['intensity'], 'currency': city['currency'],
        'rent_period': city['rent_period'], 'speeds': city['speeds'], 'sources': city['sources'],
        'neighborhoods': [{'id': region, 'name': name, 'summary': summary, 'vibe': vibe, 'lat': hood['lat'],
                           'lon': hood['lon'], 'rent_tier': 'low', 'housing': ['inn-room'], 'walkability': 'low',
                           'transit': ['on-foot'], 'source': SRC} for region, (name, summary, vibe) in REGIONS.items()],
        'places': [node_place(settlements[node], kind, arrival, spots) for node, kind, arrival, spots in NODES] + [WILD],
        'transit': [item for item in city['transit'] if item['id'] == 'on-foot'],
        'careers': city['careers'], 'work_by_gender': city['work_by_gender'], 'employers': [], 'career_hubs': [],
        'climate': city['climate'], 'annual_events': [], 'local_color': [], 'names': city['names'],
        'calendar': city['calendar'], 'prices': city['prices'], 'water': [], 'notables': [],
    }


CITY = build()

if __name__ == '__main__':
    OUT.write_text(json.dumps(CITY, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
