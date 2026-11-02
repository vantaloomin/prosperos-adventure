"""Kingswood, a Post-Reform logging town in Vanta's Vallarith, the Milestone 1 slice town. Run
`python scripts/world/kingswood.py` to rewrite it."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'dungeon' / 'world' / 'data' / 'cities' / 'kingswood.json'
SRC = 'curated-2026-10'


def place(id, name, kind, hood, summary, tags, cost, setting, good_for, parts, cuisine='', spots=(), seasons=()):
    return {'id': id, 'name': name, 'kind': kind, 'neighborhood': hood, 'summary': summary, 'tags': list(tags),
            'cost': cost, 'setting': setting, 'good_for': list(good_for), 'day_parts': list(parts),
            'seasons': list(seasons), 'cuisine': cuisine, 'spots': list(spots), 'source': SRC}


ALL_DAY = ('morning', 'afternoon', 'evening')
NIGHT = ('evening', 'late')

neighborhoods = [
    {'id': 'the-crossroads', 'name': 'the Crossroads', 'summary': 'Where the Cyrel road meets the timber track: the '
     'muddy green, the shrine, the Felled Oak and the market stalls, with the notice post everyone reads and nobody '
     'trusts.', 'vibe': ['central', 'market', 'busy'], 'lat': 52.012, 'lon': -2.004, 'rent_tier': 'mid',
     'rent': {'studio': [2, 3], 'one_bedroom': [4, 6], 'two_bedroom': [7, 10]},
     'housing': ['room-over-shop', 'timber-frame-house'], 'walkability': 'high', 'transit': ['on-foot', 'carters'],
     'source': SRC},
    {'id': 'mill-row', 'name': 'Mill Row', 'summary': 'The sawmill on the Kingsbrook and the timber yards around it: '
     'the scream of the blade, sawdust in every crack, and the barge that floats the cut wood down to Cyrel.',
     'vibe': ['industrial', 'loud', 'working'], 'lat': 52.009, 'lon': -2.012, 'rent_tier': 'low',
     'rent': {'studio': [1, 2], 'one_bedroom': [3, 4], 'two_bedroom': [5, 7]},
     'housing': ['workers-cottage', 'room-over-shop'], 'walkability': 'high', 'transit': ['on-foot', 'river-barge'],
     'source': SRC},
    {'id': 'cutters-camp', 'name': "Cutters' Camp", 'summary': 'Bunkhouses, cook fires and axe-sheds on the east side, '
     'nearest the forest: hired crews from all over Cyrel who drink hard, fight harder and leave when the pay does.',
     'vibe': ['rough', 'transient', 'loud'], 'lat': 52.014, 'lon': -1.992, 'rent_tier': 'low',
     'rent': {'studio': [1, 1], 'one_bedroom': [2, 3], 'two_bedroom': [3, 5]},
     'housing': ['bunkhouse', 'lean-to'], 'walkability': 'medium', 'transit': ['on-foot'], 'source': SRC},
    {'id': 'reeve-hill', 'name': 'Reeve Hill', 'summary': "The rise above the green with the reeve's hall, the watch "
     "post and the stone houses of the guild factor, the reeve and the few families with money.",
     'vibe': ['quiet', 'wealthy', 'watched'], 'lat': 52.016, 'lon': -2.008, 'rent_tier': 'high',
     'rent': {'studio': [4, 6], 'one_bedroom': [7, 10], 'two_bedroom': [11, 16]},
     'housing': ['stone-house', 'timber-frame-house'], 'walkability': 'high', 'transit': ['on-foot', 'horse'],
     'source': SRC},
    {'id': 'low-ford', 'name': 'Low Ford', 'summary': 'The poor end by the ford: the tannery, the charcoal kilns, the '
     "paupers' field and the families nobody else will rent to, half-elves and widows among them.",
     'vibe': ['poor', 'smoky', 'close-knit'], 'lat': 52.006, 'lon': -2.0, 'rent_tier': 'low',
     'rent': {'studio': [1, 1], 'one_bedroom': [1, 2], 'two_bedroom': [2, 4]},
     'housing': ['hovel', 'workers-cottage'], 'walkability': 'medium', 'transit': ['on-foot'], 'source': SRC},
    {'id': 'the-cutting-line', 'name': 'the Cutting Line', 'summary': 'The stumps, skid trails and the row of old '
     'border stones where Kingswood ends and Brynwyr begins. Past the stones the trees are older than the kingdom.',
     'vibe': ['wild', 'dangerous', 'border'], 'lat': 52.02, 'lon': -1.982, 'rent_tier': 'low',
     'housing': ['lean-to'], 'walkability': 'low', 'transit': ['on-foot'], 'source': SRC},
]

places = [
    # The Crossroads
    place('the-green', 'the Green', 'square', 'the-crossroads', 'A trampled common of mud and grass where the roads '
          'meet, with the notice post, the stocks and the well. Hiring is shouted here at dawn.',
          ['central', 'news', 'hiring'], 'free', 'outdoor', ['solo', 'friends', 'family'], ALL_DAY,
          spots=['the notice post', 'the stocks', 'the well']),
    place('felled-oak', 'the Felled Oak', 'tavern', 'the-crossroads', "Kingswood's tavern: a long low room built round "
          "the stump of the oak it is named for, dark ale, mutton stew, dice at the back and a cellar the watch "
          "pretends not to know about.", ['ale', 'dice', 'rumours', 'rooms'], '$', 'indoor',
          ['solo', 'friends', 'coworkers'], ('afternoon', 'evening', 'late'), cuisine='tavern',
          spots=['the stump bar', 'the dice table at the back', 'the fireside settle', 'the cellar door']),
    place('shrine-of-tidum', 'the Shrine of Tidum', 'temple', 'the-crossroads', 'A small stone shrine to Tidum, the '
          'New God of the Wild, ringed by yews. Loggers leave a chip of every first-felled tree on the '
          'altar, and some of them mean it.', ['shrine', 'new-gods', 'quiet', 'healing'], 'free', 'mixed',
          ['solo', 'family'], ALL_DAY, spots=['the altar of chips', 'the yew ring', 'the sickroom']),
    place('crossroads-market', 'the Crossroads market', 'market', 'the-crossroads', 'Stalls on the green on market '
          'days: bread from Eriane, salt, pots, rope, cheap blades and whatever the barge brought up from Cyrel.',
          ['market', 'bargains', 'gossip'], '$', 'outdoor', ['solo', 'friends', 'family'], ('morning', 'afternoon'),
          spots=['the bread cart', 'the salt stall', 'the herb seller']),
    place('pell-provisions', "Pell's Provisions", 'shopping', 'the-crossroads', "The general store: rope, lamp oil, "
          "boots, tinned meat at Cyrel prices plus Pell's cut, and a ledger of what half the town owes.",
          ['general-store', 'supplies', 'credit'], '$$', 'indoor', ['solo'], ('morning', 'afternoon')),
    place('the-wayhouse', 'the Wayhouse', 'inn', 'the-crossroads', 'Clean beds for guild men and travellers on the Cyrel '
          'road, with a stable yard and a landlady who asks no questions she cannot sell the answers to.',
          ['rooms', 'stable', 'travellers'], '$$', 'indoor', ['solo', 'coworkers'], ('evening', 'late')),
    # Mill Row
    place('varro-mill', "Varro's Mill", 'workshop', 'mill-row', 'The water-driven sawmill on the Kingsbrook, the reason '
          'Kingswood exists. The great blade runs dawn to dusk; men lose fingers to it every season.',
          ['sawmill', 'work', 'danger'], 'free', 'mixed', ['coworkers'], ('morning', 'afternoon'),
          spots=['the blade floor', 'the log pond', 'the tally shed']),
    place('timber-yards', 'the timber yards', 'workshop', 'mill-row', 'Stacked lumber drying under rough roofs, guarded '
          'at night, waiting for the barge. The guild mark is branded on every board.',
          ['timber', 'guild', 'storage'], 'free', 'outdoor', ['coworkers'], ALL_DAY),
    place('barge-landing', 'the barge landing', 'docks', 'mill-row', 'The plank quay where the Cyrel barge ties up '
          'twice a week to load timber and unload everything else, including news, soldiers and strangers.',
          ['river', 'arrivals', 'trade'], 'free', 'outdoor', ['solo', 'coworkers'], ('morning', 'afternoon')),
    place('guild-factor', "the guild factor's office", 'guildhall', 'mill-row', "The Cyrel Timber Guild's office, all "
          "ledgers and locked chests, where the cutting rights are bought, sold and quietly rewritten.",
          ['guild', 'contracts', 'money'], 'free', 'indoor', ['solo', 'coworkers'], ('morning', 'afternoon')),
    place('blackwood-smithy', 'the Blackwood smithy', 'workshop', 'mill-row', 'Axes, saw-teeth, hinges and, for the '
          'right price, blades that are not for trees. Hot, loud, and the smith listens more than she talks.',
          ['smith', 'weapons', 'tools'], '$$', 'indoor', ['solo'], ('morning', 'afternoon')),
    place('the-sawpit', 'the Sawpit', 'bar', 'mill-row', 'An alehouse dug into an old saw pit below the mill, so the '
          'drinkers sit lower than the street. Mill hands at noon, guild clerks after dark, sawdust in the beer.',
          ['ale', 'mill-hands', 'gossip'], '$', 'indoor', ['coworkers', 'friends'], ('afternoon', 'evening'),
          cuisine='tavern', spots=['the pit floor', 'the clerks\' bench']),
    # Cutters' Camp
    place('bunkhouses', 'the bunkhouses', 'inn', 'cutters-camp', 'Long timber bunkhouses where the hired crews sleep '
          'twenty to a room, with a cook fire out front and a strongbox nobody trusts.',
          ['crews', 'rough', 'cheap'], '$', 'indoor', ['coworkers'], NIGHT),
    place('axe-sheds', 'the axe sheds', 'workshop', 'cutters-camp', 'Open sheds where the crews grind their axes, mend '
          'harness and argue over tallies before the walk out to the line.', ['tools', 'crews', 'work'], 'free',
          'mixed', ['coworkers'], ('morning',)),
    place('stump-pit', 'the stump pit', 'venue', 'cutters-camp', 'A ring of stumps behind the bunkhouses where the crews '
          'fight for coin on rest days and the camp bets on it. The watch takes a cut to stay away.',
          ['fights', 'gambling', 'crowd'], '$', 'outdoor', ['friends'], NIGHT),
    place('cook-fire', "Old Wenna's cook fire", 'restaurant', 'cutters-camp', 'One pot, one ladle, one price: barley, '
          'whatever meat came in, and bread hard enough to hammer nails. Wenna feeds anyone who pays and some who '
          'cannot.', ['cheap', 'stew', 'crews'], '$', 'outdoor', ['solo', 'coworkers'], ('morning', 'evening'),
          cuisine='camp'),
    # Reeve Hill
    place('reeves-hall', "the Reeve's Hall", 'landmark', 'reeve-hill', 'A stone hall with a timber gallery where the '
          'reeve hears disputes, collects the King\'s tithe and keeps the map of the cutting rights on the wall.',
          ['law', 'tithe', 'records'], 'free', 'indoor', ['solo'], ('morning', 'afternoon'),
          spots=['the hearing floor', 'the map wall', "the reeve's study"]),
    place('watch-post', 'the watch post', 'landmark', 'reeve-hill', 'A squat garrison house with a dozen Cyrel '
          'soldiers, a lock-up and a signal horn. They are here for the elves, and the town knows it.',
          ['soldiers', 'lock-up', 'law'], 'free', 'indoor', ['solo'], ('morning', 'afternoon', 'evening', 'late'),
          spots=['the lock-up', 'the horn platform', 'the mess']),
    place('stone-houses', 'the stone houses', 'landmark', 'reeve-hill', 'Four stone houses with glass windows and walled '
          'gardens: the reeve, the guild factor, the mill family and an empty one with its shutters nailed shut.',
          ['wealth', 'quiet', 'walls'], 'free', 'outdoor', ['solo'], ALL_DAY),
    place('dunmore-kitchen', "Dunmore's kitchen", 'restaurant', 'reeve-hill', 'A cookshop by the reeve\'s hall that '
          'feeds the clerks, the watch and anyone waiting on a hearing: pies, pottage and very weak tea.',
          ['pies', 'watch', 'waiting'], '$', 'indoor', ['solo', 'coworkers'], ('morning', 'afternoon'),
          cuisine='cookshop', spots=['the window table', 'the bench by the hall door']),
    # Low Ford
    place('the-ford', 'the ford', 'trail', 'low-ford', 'The shallow crossing of the Kingsbrook, slick stones and cold '
          'water. Children dare each other to cross at night, when the water talks.', ['river', 'crossing', 'stories'],
          'free', 'outdoor', ['solo', 'friends'], ALL_DAY),
    place('tannery', 'the tannery', 'workshop', 'low-ford', 'Pits of lime and bark and worse. The smell sets the rent '
          'in Low Ford, and the tanner buys hides without asking whose.', ['work', 'stink', 'hides'], 'free', 'mixed',
          ['coworkers'], ('morning', 'afternoon')),
    place('paupers-field', 'the paupers\' field', 'garden', 'low-ford', 'A flood-prone burial ground by the river where the '
          'town buries its poor, its strangers and anyone the shrine would not take. Some markers are elvish.',
          ['graves', 'quiet', 'grief'], 'free', 'outdoor', ['solo'], ALL_DAY),
    place('the-kilns', 'the charcoal kilns', 'workshop', 'low-ford', 'Earth-banked kilns that smoke day and night. The '
          'burners sleep beside them in shifts and see who comes and goes along the river path after dark.',
          ['smoke', 'night', 'work'], 'free', 'outdoor', ['coworkers'], ('evening', 'late')),
    place('mother-mags', "Mother Mag's", 'bar', 'low-ford', "A front room with a barrel of plum spirit, three stools and "
          "Mag, who will sell you a drink, a cure, a curse or a girl's name in Brynwyr, in that order of honesty.",
          ['spirits', 'cures', 'secrets'], '$', 'indoor', ['solo', 'friends'], NIGHT),
    # The Cutting Line
    place('stump-fields', 'the stump fields', 'trail', 'the-cutting-line', 'Acres of raw stumps and skid trails between '
          'the camp and the border stones, where the crews work and the wardens watch.',
          ['logging', 'open', 'watched'], 'free', 'outdoor', ['coworkers'], ('morning', 'afternoon')),
    place('tally-hut', 'the tally hut', 'bar', 'the-cutting-line', 'A plank hut at the edge of the stumps where the '
          'tally men count the day\'s logs and sell small beer to the crews coming off shift.',
          ['crews', 'tally', 'small-beer'], '$', 'indoor', ['coworkers'], ('afternoon', 'evening'),
          spots=['the tally board', 'the beer barrel']),
    place('border-stones', 'the border stones', 'landmark', 'the-cutting-line', 'A line of mossed standing stones older '
          'than Cyrel, each cut with a leaf sign. By treaty no axe crosses them. Arrows have.',
          ['border', 'treaty', 'danger'], 'free', 'outdoor', ['solo'], ALL_DAY,
          spots=['the split stone', 'the arrow-scarred stone', 'the path between']),
    place('the-heartwood', 'the Heartwood', 'trail', 'the-cutting-line', 'The old grove past the border stones: '
          'trees thirty men could not ring, ground that hums underfoot, and Brynwyr wardens who kill trespassers. '
          'Something under it makes compasses spin and wounds close wrong.', ['wild', 'danger', 'ley', 'elves', 'forbidden'],
          'free', 'outdoor', ['solo'], ALL_DAY, spots=['the hollow oak', 'the humming stones', 'the warden path']),
]

careers = [
    ('logger', 'Logger', 'forest', 'early', 'staff', '$', 'Felling and limbing at the cutting line with a crew, paid by '
     'the tree.', ['the axe', 'falling timber', 'the crew', 'elf arrows'], 'men'),
    ('sawyer', 'Sawyer', 'timber', 'shift-day', 'staff', '$', 'Feeding logs to the great blade at the mill and keeping '
     'all ten fingers.', ['the blade', 'sawdust', 'noise'], 'men'),
    ('teamster', 'Teamster', 'timber', 'early', 'staff', '$', 'Driving the ox teams that skid logs from the line to the '
     'mill pond.', ['oxen', 'mud', 'the skid trail'], None),
    ('bargeman', 'Bargeman', 'river', 'rotating', 'staff', '$', 'Poling the timber barge down the Kingsbrook to Cyrel '
     'and back.', ['the river', 'Cyrel', 'smuggling'], 'men'),
    ('tally-clerk', 'Tally clerk', 'guild', 'office', 'staff', '$$', "Counting every board for the guild factor, and "
     "being paid to count some twice.", ['ledgers', 'the guild', 'skimming'], None),
    ('watch-soldier', 'Watch soldier', 'watch', 'rotating', 'rota', '$', "Standing a Cyrel soldier's watch at the post "
     "or the border stones.", ['the border', 'boredom', 'fear', 'orders'], 'men'),
    ('tanner', 'Tanner', 'craft', 'shift-day', 'staff', '$', 'Working hides in the lime pits at Low Ford.',
     ['the stink', 'hides', 'cheap work'], None),
    ('charcoal-burner', 'Charcoal burner', 'forest', 'rotating', 'staff', '$', 'Tending the smoking kilns day and night '
     'for the smithy and the barge.', ['the kilns', 'night watches', 'smoke'], 'men'),
    ('camp-cook', 'Camp cook', 'food', 'early', 'staff', '$', 'Feeding the crews from one pot before dawn and after '
     'dark.', ['the pot', 'the crews', 'gossip'], 'women'),
    ('herb-woman', 'Herb seller', 'healing', 'flexible', 'freelance', '$', 'Selling remedies, poultices and quieter '
     'things from a market stall or a back room.', ['herbs', 'cures', 'poisons'], 'women'),
    ('shrine-keeper', 'Shrine keeper', 'faith', 'early', 'staff', '$', "Keeping Tidum's shrine, nursing the sick and "
     "burying the poor.", ['the shrine', 'the sick', 'the New Gods'], None),
    ('tavern-hand', 'Tavern hand', 'food', 'evening', 'staff', '$', 'Pouring, carrying and cleaning up after loggers at '
     'the Felled Oak.', ['ale', 'fights', 'tips'], None),
    ('smith', 'Smith', 'craft', 'shift-day', 'staff', '$$', 'Forging axes, saw-teeth and the odd blade at Blackwood.',
     ['the forge', 'steel', 'customers'], None),
    ('fighter', 'Pit fighter', 'camp', 'evening', 'freelance', '$', 'Fighting in the stump pit for coin and the crowd.',
     ['the pit', 'bets', 'bruises'], None),
]
careers = [{'id': c[0], 'name': c[1], 'sector': c[2], 'schedule': c[3], 'employment': c[4], 'pay': c[5],
            'summary': c[6], 'themes': c[7], 'eras': ['fantasy'], **({'worked_by': c[8]} if c[8] else {})}
           for c in careers]

employers = [
    ('varro-sawmill', "Varro's Mill", 'timber', 'mill-row', 'medium', 'The sawmill and its yards, run by the Varro '
     'family for three generations.', ['sawyer', 'teamster']),
    ('cyrel-timber-guild', 'the Cyrel Timber Guild', 'guild', 'mill-row', 'medium', 'The guild that owns the cutting '
     'rights, hires the crews and ships the timber.', ['logger', 'tally-clerk', 'bargeman', 'teamster']),
    ('kingswood-watch', 'the Kingswood watch', 'watch', 'reeve-hill', 'small', "A dozen Cyrel soldiers under a "
     "sergeant, posted against the elves.", ['watch-soldier']),
    ('felled-oak-house', 'the Felled Oak', 'food', 'the-crossroads', 'small', "The tavern's bar and kitchen.",
     ['tavern-hand']),
    ('low-ford-tannery', 'the tannery', 'craft', 'low-ford', 'small', 'The lime pits and drying racks at the ford.',
     ['tanner']),
    ('kiln-crews', 'the kiln crews', 'forest', 'low-ford', 'small', 'The charcoal burners who sell to the smithy and the '
     'barge.', ['charcoal-burner']),
    ('blackwood', 'the Blackwood smithy', 'craft', 'mill-row', 'small', 'Axes, saw-teeth and blades.', ['smith']),
    ('cutters-cookhouse', "the camp cook fires", 'food', 'cutters-camp', 'small', 'The pots that feed the crews.',
     ['camp-cook']),
    ('tidum-shrine', 'the Shrine of Tidum', 'faith', 'the-crossroads', 'small', 'The shrine, its sickroom and its graves.',
     ['shrine-keeper']),
]
employers = [{'id': e[0], 'name': e[1], 'sector': e[2], 'neighborhood': e[3], 'size': e[4], 'summary': e[5],
              'careers': e[6], 'source': SRC} for e in employers]

career_hubs = [
    {'id': 'timber', 'name': 'The mill and the line', 'neighborhoods': ['mill-row', 'cutters-camp', 'the-cutting-line'],
     'sectors': ['timber', 'forest', 'guild', 'river'], 'summary': 'Almost every wage in Kingswood comes from cutting, '
     'hauling, sawing or shipping wood.', 'source': SRC},
    {'id': 'green-and-hill', 'name': 'The Crossroads and Reeve Hill', 'neighborhoods': ['the-crossroads', 'reeve-hill'],
     'sectors': ['food', 'faith', 'watch', 'healing'], 'summary': 'The tavern, the shrine, the market and the watch.',
     'source': SRC},
    {'id': 'ford-trades', 'name': 'Low Ford', 'neighborhoods': ['low-ford'], 'sectors': ['craft', 'forest'],
     'summary': 'The tannery and the kilns: the work nobody else wants.', 'source': SRC},
]

months = [
    (40, 29, 13, 'Cold and wet; the line shuts in hard frost.'), (42, 30, 11, 'Raw; snow lies in the Heartwood.'),
    (49, 34, 12, 'Mud season; the skid trails turn to soup.'), (56, 38, 11, 'The cutting starts again.'),
    (63, 44, 11, 'Long days at the line; the barge runs full.'), (69, 50, 10, 'Warm; midges at the ford.'),
    (73, 54, 9, 'The warmest month; the mill runs late.'), (72, 53, 10, 'Heavy, thundery air.'),
    (66, 48, 10, 'Harvest in Eriane, wages down in Kingswood.'), (57, 42, 12, 'Leaves turn; fogs off the brook.'),
    (48, 35, 13, 'Dark early; fewer crews, more drinking.'), (42, 31, 14, 'Bitter; the camp half empty.')]

names = {'mix': {'cyrel': 0.84, 'halfling': 0.1, 'half-elf': 0.06}, 'groups': {
    'cyrel': {'feminine': ['Hesk', 'Wenna', 'Maud', 'Ilse', 'Brannagh', 'Edda', 'Tamsin', 'Garra', 'Orla', 'Nell',
                           'Sabeth', 'Aud', 'Rhoswen', 'Kettie', 'Joss', 'Margery', 'Elspeth', 'Hild', 'Cass', 'Linnet'],
              'masculine': ['Aldous', 'Bram', 'Corin', 'Tobin', 'Garrick', 'Osric', 'Wat', 'Hamon', 'Dunstan', 'Piers',
                            'Rowan', 'Edric', 'Halden', 'Jory', 'Matthias', 'Colm', 'Fenwick', 'Ulric', 'Brand', 'Simkin'],
              'neutral': ['Ash', 'Wren', 'Rook', 'Linden'],
              'family': ['Marr', 'Varro', 'Tolley', 'Ashby', 'Rook', 'Pell', 'Blacklock', 'Hale', 'Thorley', 'Cutter',
                         'Fenn', 'Brook', 'Mossley', 'Grieve', 'Holt', 'Sawyer', 'Wainwright', 'Dunmore', 'Carrow',
                         'Stoat']},
    'halfling': {'feminine': ['Pip', 'Marigold', 'Tansy', 'Bree'], 'masculine': ['Dob', 'Hobb', 'Tam', 'Fennick'],
                 'family': ['Underbough', 'Hollyhock', 'Tealeaf', 'Brambleway'], 'kind': 'halfling'},
    'half-elf': {'feminine': ['Sereth', 'Ilvane', 'Ailsa'], 'masculine': ['Thalen', 'Corvane', 'Emrys'],
                 'neutral': ['Lirien'], 'family': ['of the Ford', 'Greenhand', 'Mossley'], 'kind': 'half-elf'}}}

notables = [
    {'id': 'aldous-marr', 'name': 'Aldous Marr', 'given': 'Aldous', 'pronouns': 'he/him', 'age': 54,
     'place': 'reeves-hall', 'role': 'reeve', 'staff': True, 'about': "The King's reeve of Kingswood: soft-spoken, "
     'well-fed and deep in debt to the Timber Guild. He has quietly sold them the right to fell the Heartwood, past the '
     'border stones, and needs the crews in before anyone in Cyrel asks why.', 'wants': 'to get the first crews past the stones before the week is out, and nobody asking questions', 'source': SRC},
    {'id': 'hesk-varro', 'name': 'Hesk Varro', 'given': 'Hesk', 'pronouns': 'she/her', 'age': 38, 'place': 'varro-mill',
     'role': 'mill foreman', 'staff': True, 'about': 'Runs the mill and the toughest crew on the line. Her younger '
     'brother died with an elf arrow in his throat two springs ago, and she wants the Heartwood cut more than she '
     'wants the money.', 'wants': 'to sign every axe in town onto the Heartwood contract', 'source': SRC},
    {'id': 'ilse-rook', 'name': 'Ilse Rook', 'given': 'Mother Rook', 'pronouns': 'she/her', 'age': 67,
     'place': 'shrine-of-tidum', 'role': 'shrine keeper', 'staff': True, 'about': "Keeper of Tidum's shrine, healer "
     'and gravedigger. She knows the Heartwood stands on a Ley convergence and that cutting it will crack something '
     'open under the village. She has told no one, because she once helped hide what is down there.', 'wants': 'to stop the felling without ever saying why', 'source': SRC},
    {'id': 'corin-ashby', 'name': 'Corin Ashby', 'given': 'Corin', 'pronouns': 'he/him', 'age': 31, 'place': 'felled-oak',
     'role': 'tavern keeper', 'staff': True, 'about': 'Keeps the Felled Oak, fences whatever the crews steal and sells '
     'what he overhears to whoever pays: the reeve, the watch, and lately an elf.', 'wants': 'to sell what he hears this week to the highest bidder', 'source': SRC},
    # Mag keeps her front room alone, every evening: the fence is open whenever Low Ford drinks.
    {'id': 'mag-hollin', 'name': 'Mag Hollin', 'given': 'Mother Mag', 'pronouns': 'she/her', 'age': 63,
     'place': 'mother-mags', 'role': 'keeper', 'staff': True, 'days': [0, 1, 2, 3, 4, 5, 6], 'about': 'Keeps the '
     'front room at Low Ford: plum spirit, cures, the odd curse, and quiet money for whatever the crews bring her that '
     "they shouldn't have. She asks no questions and pays a quarter of what a thing is worth.",
     'wants': 'to buy cheap and keep the watch looking the other way', 'source': SRC},
    {'id': 'sereth', 'name': 'Sereth of the Ford', 'given': 'Sereth', 'pronouns': 'they/them', 'age': 142, 'kind': 'half-elf',
     'place': 'crossroads-market', 'role': 'herb seller', 'staff': False, 'about': 'A half-elf who sells herbs at the '
     'market and lives at the ford. In truth a Brynwyr warden\'s eyes in Kingswood. They have been told that if the '
     'crews cross the stones, the wardens will burn Cutters\' Camp, and they are not sure they will warn anyone first.',
     'wants': 'the name of everyone who signs the contract, without being seen asking', 'source': SRC},
    {'id': 'bram-tolley', 'name': 'Bram Tolley', 'given': 'Sergeant Tolley', 'pronouns': 'he/him', 'age': 46,
     'place': 'watch-post', 'role': 'watch sergeant', 'staff': True, 'about': 'Sergeant of the Kingswood watch. Brutal, '
     'tired, and honest in the way of a man who has never been offered enough. He takes the stump-pit cut and '
     'hangs elves when he can catch them.', 'wants': 'to catch whoever is talking to the wardens', 'source': SRC},
]

CITY = {
    'schema_version': 1, 'id': 'kingswood', 'name': 'Kingswood', 'setting': 'original', 'era': 'fantasy',
    'category': 'fictional',
    'basis': "Vanta's own world of Vallarith (the kingdom of Cyrel, the elves of Brynwyr, the Ley, the New Gods); the "
             'town, its places and its people are written for Prospero\'s Dungeon. Set Post-Reform, about 300 RFM.',
    'region': 'the kingdom of Cyrel', 'country': 'Cyrel', 'timezone': 'Europe/London',
    'aliases': ['Kingswood village'],
    'summary': "A logging town on the edge of Brynwyr forest, one of Cyrel's three sister towns. It lives on the "
               'sawmill and the Timber Guild, sits uneasily against the High Elves across the border stones, and '
               'stands on a rumoured convergence of the Ley that nobody in charge will talk about.',
    'lat': 52.012, 'lon': -2.004,
    # Vallarith is grimdark: the world's default intensity and narrator voice (requirements "Intensity and tone").
    'intensity': {'preset': 'unflinching',
                  'voice': 'grim and earthy: a hard frontier where kindness costs something, power is bought, and '
                           'nobody is safe because they deserve to be',
                  'drama': 'eventful'},
    'currency': {'code': 'crown', 'symbol': 'cr.', 'name': 'silver crowns'}, 'rent_period': 'week',
    'speeds': {'walk': 4.5, 'horse': 10, 'boat': 5},
    'sources': {SRC: {'kind': 'curated', 'title': "Kingswood written for Prospero's Dungeon from Vanta's Vallarith lore",
                      'license': "Vanta's own setting; all rights reserved", 'retrieved': '2026-10-21',
                      'note': "Drawn from Vallarith's existing lore (Kingswood, Cyrel, Brynwyr, Tidum, the Ley). "
                              'Places, trades, prices and people are new.'}},
    'neighborhoods': neighborhoods, 'places': places,
    'transit': [
        {'id': 'on-foot', 'name': 'On foot', 'kind': 'walk', 'summary': 'Kingswood is a half hour end to end; the line '
         'is another half hour past the camp.', 'source': SRC},
        {'id': 'carters', 'name': 'Carters', 'kind': 'stagecoach', 'summary': 'Carts on the Cyrel road, a day and a '
         'half to the capital.', 'source': SRC},
        {'id': 'river-barge', 'name': 'The timber barge', 'kind': 'boat', 'summary': 'Down the Kingsbrook to Cyrel '
         'twice a week; passengers ride on the timber for a crown.', 'source': SRC},
        {'id': 'horse', 'name': 'Horse', 'kind': 'horse', 'summary': 'The watch, the reeve and the factor ride.',
         'source': SRC}],
    'careers': careers, 'work_by_gender': True, 'employers': employers, 'career_hubs': career_hubs,
    'climate': {'summary': 'Damp and temperate: long wet winters, mud springs, short warm summers, fogs off the brook.',
                'months': [{'high_f': h, 'low_f': lo, 'rain_days': r, 'note': n} for h, lo, r, n in months],
                'source': SRC},
    'annual_events': [
        {'id': 'first-felling', 'name': 'First Felling', 'months': [4], 'neighborhood': 'the-cutting-line',
         'summary': 'The first tree of the season is felled at dawn with the shrine keeper\'s blessing, and its first '
         'chip goes on Tidum\'s altar.', 'source': SRC},
        {'id': 'tithe-day', 'name': 'Tithe day', 'months': [9], 'neighborhood': 'reeve-hill', 'summary': "The reeve "
         "collects the King's tithe in coin and timber; the camp empties and the Felled Oak fills.", 'source': SRC},
        {'id': 'night-of-stones', 'name': 'the Night of Stones', 'months': [10], 'neighborhood': 'the-cutting-line',
         'summary': 'Once a year the town leaves bread at the border stones. Nobody remembers who started it, and the '
         'bread is always gone by morning.', 'source': SRC}],
    'local_color': [
        {'id': 'chip-for-tidum', 'name': 'A chip for Tidum', 'kind': 'custom', 'summary': 'Loggers keep the first chip '
         'of every tree for the shrine. A crew that forgets is a crew that loses a man.',
         'places': ['shrine-of-tidum'], 'source': SRC},
        {'id': 'past-the-stones', 'name': 'Past the stones', 'kind': 'saying', 'summary': '"Gone past the stones" '
         'means dead, missing, or ruined, and nobody asks which.', 'source': SRC},
        {'id': 'humming-ground', 'name': 'The humming ground', 'kind': 'legend', 'summary': 'Old crews say the ground '
         'past the stones hums at night, and that a man who sleeps on it wakes knowing things he should not.',
         'places': ['the-heartwood'], 'source': SRC},
        {'id': 'xiloscients-stand', 'name': "Xiloscient's stand", 'kind': 'legend', 'summary': 'In 251 AOD Gor\'gel, '
         'the Old God of War, came to the elf druid Himo Xiloscient wearing another god\'s face and talked him into '
         "opening the first portal. When Ohgnu's gnolls and the demons poured through, Himo held the line here, at "
         'Kingswood. The town tells it proudly and leaves out that he was an elf, and that the door was his.',
         'source': SRC},
        {'id': 'the-apprentice', 'name': "Tidum's apprentice", 'kind': 'legend', 'summary': 'Before he was a god, '
         'Tidum was an archdruid, and his apprentice inherited his deathlessness when he rose. The apprentice died '
         'anyway, in the first wave of devils. The keepers say the yews round the shrine grew from that grave.',
         'places': ['shrine-of-tidum'], 'source': SRC},
        {'id': 'the-empty-house', 'name': 'The empty house', 'kind': 'rumor', 'summary': 'The shuttered stone house on '
         'Reeve Hill belonged to the last reeve, who went past the stones one night and came back wrong.',
         'places': ['stone-houses'], 'source': SRC},
        {'id': 'oak-stew', 'name': 'Felled Oak stew', 'kind': 'dish', 'summary': 'Mutton, barley and dark ale, cooked '
         'until nobody can tell which is which.', 'places': ['felled-oak'], 'source': SRC},
        {'id': 'plum-spirit', 'name': "Mag's plum", 'kind': 'drink', 'summary': 'Plum spirit from Low Ford, strong '
         'enough to strip pitch off an axe.', 'places': ['mother-mags'], 'source': SRC},
        {'id': 'elf-arrows', 'name': 'Grey-fletched arrows', 'kind': 'rumor', 'summary': 'Wardens fletch with grey owl '
         'feathers. Finding one on your bunk is a warning; finding one in you is the second.',
         'places': ['border-stones'], 'source': SRC}],
    'names': names, 'calendar': 'none',
    'prices': [
        {'id': 'ale', 'item': 'Mug of ale', 'low': 0.1, 'high': 0.2, 'per': '', 'source': SRC},
        {'id': 'stew', 'item': 'Bowl of stew and bread', 'low': 0.2, 'high': 0.3, 'per': '', 'source': SRC},
        {'id': 'room', 'item': 'Room at the Wayhouse', 'low': 1, 'high': 2, 'per': 'night', 'source': SRC},
        {'id': 'bunk', 'item': 'Bunk in the camp', 'low': 0.3, 'high': 0.5, 'per': 'night', 'source': SRC},
        {'id': 'day-wage', 'item': "A logger's day wage", 'low': 1, 'high': 2, 'per': 'day', 'source': SRC},
        {'id': 'axe', 'item': 'Felling axe', 'low': 4, 'high': 6, 'per': '', 'source': SRC},
        {'id': 'sword', 'item': 'Plain sword', 'low': 15, 'high': 25, 'per': '', 'source': SRC},
        {'id': 'rope', 'item': 'Rope, fifty feet', 'low': 0.5, 'high': 1, 'per': '', 'source': SRC},
        {'id': 'lamp-oil', 'item': 'Lamp oil', 'low': 0.2, 'high': 0.4, 'per': 'flask', 'source': SRC},
        {'id': 'remedy', 'item': 'Poultice or remedy', 'low': 0.5, 'high': 3, 'per': '', 'source': SRC},
        {'id': 'barge-passage', 'item': 'Passage to Cyrel on the barge', 'low': 1, 'high': 1, 'per': '', 'source': SRC},
        {'id': 'pit-purse', 'item': 'Stump-pit purse', 'low': 2, 'high': 10, 'per': 'fight', 'source': SRC}],
    'water': [{'kind': 'river', 'name': 'Kingsbrook', 'width_km': 0.03,
               'points': [[52.018, -2.03], [52.01, -2.015], [52.006, -2.0], [52.0, -1.985]]}],
    'notables': notables,
}

if __name__ == '__main__':
    OUT.write_text(json.dumps(CITY, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
