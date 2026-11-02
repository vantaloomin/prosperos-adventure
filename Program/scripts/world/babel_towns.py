"""BABEL's towns, from Vanta's Mabry Curve archive (dungeon/world/packages/babel): the Concourse (Floor Zero, where
the arrivals land), Hollin on Varrow (the starter floor, with the Close, the Keep and the Reachwall), the Gilded
Bazaar (three floors up, where Bri and Chase come down) and the other floors, as the places on the travel map
between them (babel-floors). Run `python scripts/world/babel_towns.py` to rewrite them."""
import json
from pathlib import Path

CITIES = Path(__file__).resolve().parents[2] / 'dungeon' / 'world' / 'data' / 'cities'
SRC = 'mabry-curve-2026-10'
SOURCES = {SRC: {
    'kind': 'curated', 'title': "BABEL written for Prospero's Dungeon from Vanta's Mabry Curve archive",
    'license': "Vanta's own setting; all rights reserved", 'retrieved': '2026-10-22',
    'note': 'Places, people and customs from the Mabry Curve story, hidden files and side cast '
            '(dungeon/world/packages/babel/sources.md). Names the story does not give are new.'}}
ALL_DAY = ('morning', 'afternoon', 'evening')
NIGHT = ('evening', 'late')
EVERY = ('morning', 'afternoon', 'evening', 'late')
CURRENCY = {'code': 'talent', 'symbol': 'T', 'name': 'Talents'}
INTENSITY = {'preset': 'unflinching', 'drama': 'eventful',
             'voice': 'pulpy and mythic in a modern frame: omens, weather and System panes, where every win carries '
                      'a bill and desire is a power with a price'}
# The tower has no Earth position; these are Round Rock's, where the Halvorsen's wave was taken, nudged per floor.
LAT, LON = 30.508, -97.679


def place(id, name, kind, hood, summary, tags, cost, setting, good_for, parts, cuisine='', spots=(), seasons=()):
    return {'id': id, 'name': name, 'kind': kind, 'neighborhood': hood, 'summary': summary, 'tags': list(tags),
            'cost': cost, 'setting': setting, 'good_for': list(good_for), 'day_parts': list(parts),
            'seasons': list(seasons), 'cuisine': cuisine, 'spots': list(spots), 'source': SRC}


def hood(id, name, summary, vibe, lat, lon, tier, rent, housing, walk, transit):
    found = {'id': id, 'name': name, 'summary': summary, 'vibe': list(vibe), 'lat': lat, 'lon': lon, 'rent_tier': tier,
             'housing': list(housing), 'walkability': walk, 'transit': list(transit), 'source': SRC}
    if rent:
        found['rent'] = {'studio': rent[0], 'one_bedroom': rent[1], 'two_bedroom': rent[2]}
    return found


def career(id, name, sector, schedule, employment, pay, summary, themes, worked_by=None, adult=False):
    found = {'id': id, 'name': name, 'sector': sector, 'schedule': schedule, 'employment': employment, 'pay': pay,
             'summary': summary, 'themes': list(themes), 'eras': ['fantasy']}
    if worked_by:
        found['worked_by'] = worked_by
    if adult:
        found['adult'] = True
    return found


def employer(id, name, sector, hood, size, summary, careers):
    return {'id': id, 'name': name, 'sector': sector, 'neighborhood': hood, 'size': size, 'summary': summary,
            'careers': list(careers), 'source': SRC}


def notable(id, name, given, pronouns, age, place, role, about, wants, staff=True, kind=None):
    found = {'id': id, 'name': name, 'given': given, 'pronouns': pronouns, 'age': age, 'place': place, 'role': role,
             'staff': staff, 'about': about, 'wants': wants, 'source': SRC}
    if kind:
        found['kind'] = kind
    return found


def price(id, item, low, high, per=''):
    return {'id': id, 'item': item, 'low': low, 'high': high, 'per': per, 'source': SRC}


def color(id, name, kind, summary, places=()):
    return {'id': id, 'name': name, 'kind': kind, 'summary': summary, 'places': list(places), 'source': SRC}


def months(high, low, rain, notes):
    return [{'high_f': hi, 'low_f': lo, 'rain_days': rain_days, 'note': note}
            for hi, lo, rain_days, note in zip(high, low, rain, notes)]


def city(id, name, summary, region, aliases, lat, lon, speeds, hoods, places, careers, employers, hubs, transit,
         climate, events, colors, names, prices, notables):
    return {'schema_version': 1, 'id': id, 'name': name, 'setting': 'original', 'era': 'fantasy',
            'category': 'fictional',
            'basis': "Vanta's own world of BABEL, from the Mabry Curve roleplay: a living tower of themed floors "
                     'wearing the skin of an unreleased full-dive game.',
            'region': region, 'country': 'the tower', 'timezone': 'America/Chicago', 'aliases': list(aliases),
            'summary': summary, 'lat': lat, 'lon': lon, 'intensity': INTENSITY, 'currency': CURRENCY,
            'rent_period': 'week', 'speeds': speeds, 'sources': SOURCES, 'neighborhoods': hoods, 'places': places,
            'transit': transit, 'careers': careers, 'work_by_gender': False, 'employers': employers,
            'career_hubs': hubs, 'climate': climate, 'annual_events': events, 'local_color': colors, 'names': names,
            'calendar': 'none', 'prices': prices, 'water': [], 'notables': notables}


# The Concourse ------------------------------------------------------------------------------------

CONCOURSE_NAMES = {'groups': {
    'concourse': {
        'feminine': ['Darla', 'Ruth Ann', 'Marisol', 'Osk', 'Bettany', 'Ines', 'Wenda', 'Lupe', 'Hattie', 'Corinne',
                     'Ama', 'Greer', 'Nadia', 'Rosalind', 'Tova', 'Junie'],
        'masculine': ['Hamid', 'Danny', 'Ed', 'Cobb', 'Ivo', 'Tunde', 'Lyle', 'Arturo', 'Bascom', 'Pieter', 'Rafe',
                      'Hollis', 'Omar', 'Desmond', 'Clem', 'Jakob'],
        'neutral': ['Pia', 'Sunny', 'Ash', 'Kit'],
        'family': ['Kinney', 'Teel', 'Oyelaran', 'Sallis', 'Brask', 'Morrow-Hale', 'Quist', 'Delacroix', 'Ambrose',
                   'Okafor', 'Lindqvist', 'Pruett', 'Vasquez', 'Hanley', 'Stroud', 'Achterberg']}}}

concourse_hoods = [
    hood('waystone-plaza', 'the Waystone plaza', 'The broad round plaza at the heart of Floor Zero, with the great white '
         'Waystone in the middle and the Roll carved at its top. Arrivals stand here looking up at the dome; everyone '
         'else stands here looking at the arrivals.', ['central', 'safe-zone', 'busy'], LAT, LON, 'high',
         ([20, 30], [35, 50], [60, 90]), ['room-over-shop', 'garret'], 'high', ['on-foot']),
    hood('the-market-streets', 'the market streets', 'Stall-packed streets running off the plaza under banners and '
         'cookfire smoke, at their fullest on Fire Market day: skewers, cloth, starter kits, maps of floors that may '
         'not look like that any more.', ['market', 'loud', 'cheap'], LAT + 0.002, LON - 0.002, 'mid',
         ([10, 15], [18, 25], [30, 45]), ['room-over-shop', 'stall-loft'], 'high', ['on-foot', 'porters']),
    hood('guild-row', 'the guild row', 'A street of guild halls east of the plaza, tall narrow fronts with banners hung '
         'from the upper windows, most faded past reading. The Landing is the last and least impressive.',
         ['guilds', 'veterans', 'faded'], LAT + 0.001, LON + 0.003, 'mid', ([12, 18], [20, 30], [35, 50]),
         ['guild-hall', 'garret'], 'high', ['on-foot']),
    hood('the-east-gate', 'the east gate', 'The gate onto the Stair, with MIND THE STAIR painted over the arch in the '
         'oldest lettering on the floor and the lift cage swinging on its chains beyond. Porters, toll touts and people '
         'saying goodbye.', ['gate', 'travel', 'goodbyes'], LAT + 0.0015, LON + 0.006, 'low',
         ([6, 10], [12, 16], [18, 26]), ['bunkhouse', 'garret'], 'medium', ['on-foot', 'the-lift-cage']),
    hood('the-lamp-quarter', 'the Lamp Quarter', 'Lodging houses, cook-shops and taprooms in the lanes behind the '
         'market, lit all night by lamps on brackets: where climbers sleep when they are not in a guild, and where '
         'natives sell the only food that tastes.', ['lodgings', 'night', 'rough'], LAT - 0.002, LON + 0.001, 'low',
         ([5, 8], [10, 14], [16, 22]), ['lodging-house', 'bunkhouse'], 'high', ['on-foot']),
]

concourse_places = [
    place('the-waystone', 'the Concourse Waystone', 'landmark', 'waystone-plaza', 'A great white standing stone with '
          'light at its heart. Touch it to attune: your return point, the quest board, a class confirmed. The Roll of '
          'arrivals is carved at the top, newest first; Nth Floor\'s maker\'s mark, NF, is cut small into its foot.',
          ['waystone', 'safe-zone', 'the-roll', 'quests'], 'free', 'outdoor', ['solo', 'friends', 'family'], EVERY,
          spots=['the Roll', 'the quest board', 'the maker\'s mark at the foot', 'the steps where arrivals sit']),
    place('the-plaza', 'the plaza', 'square', 'waystone-plaza', 'Flagstones worn smooth around the Stone, the dome far '
          'overhead with weather in it and bells hung in the haze. Plate armor, rags, and now and then a Texas '
          'Longhorns hoodie.', ['central', 'crowds', 'news'], 'free', 'outdoor', ['solo', 'friends'], EVERY,
          spots=['the Stone\'s shadow', 'the criers\' corner', 'the edge of the market']),
    place('hamids-cart', "Hamid's skewer cart", 'restaurant', 'the-market-streets', 'A charcoal cart half a block from '
          'the plaza, meat on iron forks over coals, and Hamid in his leather apron daring you to complain. Plain meat: '
          'to a climber it tastes of ash.', ['street-food', 'fire-market'], '$', 'outdoor', ['solo', 'friends'],
          ALL_DAY, cuisine='skewers', spots=['the coals', 'the awning']),
    place('fire-market-rows', 'the Fire Market rows', 'market', 'the-market-streets', 'The market streets on Fire Market '
          'day, the best trading day of the week: stalls three deep, starter kits resold, cloth, lamps, maps, and debts '
          'changing hands.', ['market', 'fire-market', 'bargains', 'debts'], '$', 'outdoor',
          ['solo', 'friends', 'family'], ALL_DAY, spots=['the map sellers', 'the kit stalls', 'the rent men\'s table']),
    place('brask-and-daughters', 'Brask and Daughters', 'shopping', 'the-market-streets', 'Armorers and outfitters '
          'with a stall front and a forge behind: blades, mail, packs, and gear graded on BABEL\'s ladder since the '
          'Turning, which the Brask daughters resent.', ['arms', 'gear', 'graded'], '$$', 'indoor', ['solo'],
          ('morning', 'afternoon'), spots=['the blade rack', 'the forge', 'the grading slate']),
    place('the-landing', 'the Landing', 'guildhall', 'guild-row', 'Darla Kinney\'s guild in a squat domed bathhouse of '
          'green-veined marble, its bronze plaque scratched over in block capitals. The pools are drained: bedrolls in '
          'the shallow end, a long table in the deep end, a cookfire in the old hot bath venting through a hole in the '
          'dome, fish mosaics missing tiles like teeth. It still smells faintly of chlorine.',
          ['guild', 'veterans', 'safe-zone'], 'free', 'indoor', ['solo', 'friends', 'coworkers'], EVERY,
          spots=['the long table in the deep end', 'the shallow end', 'the hot-bath cookfire', 'the bronze door']),
    place('the-guild-halls', 'the guild halls', 'guildhall', 'guild-row', 'Bigger guilds than the Landing, behind '
          'faded banners: halls that recruit arrivals on the plaza, buy what they know about the floors, and do not '
          'like a veteran guild getting ahead of them on the Turning.', ['guilds', 'recruiting'], '$$', 'indoor',
          ['solo', 'coworkers'], ALL_DAY, spots=['the recruiting table', 'the trophy wall']),
    place('the-gate-arch', 'the east gate', 'landmark', 'the-east-gate', 'The arch onto the Stair, MIND THE STAIR '
          'over it. Beyond, the shaft as wide as a stadium, the stair spiraling its wall and the iron lift cage on its '
          'chains. The operator in the leather cap calls the floors.', ['gate', 'stair', 'travel'], 'free',
          'outdoor', ['solo', 'friends'], EVERY,
          spots=['the arch', 'the cage landing', 'the first step down', 'the operator\'s lever']),
    place('the-porters-yard', 'the porters\' yard', 'workshop', 'the-east-gate', 'Where porters wait for loads going '
          'up or down the Stair, and where you can hire one, or a guide, or someone who says he is a guide.',
          ['hiring', 'porters', 'guides'], '$', 'outdoor', ['solo', 'coworkers'], ('morning', 'afternoon')),
    place('osks-kitchen', "Osk's Kitchen", 'restaurant', 'the-lamp-quarter', 'A cook-shop run by a native Cook whose '
          'dishes carry a System effect, so they are the only meals on the street that taste of anything to a climber. '
          'There is always a queue of the Unhungry, and Osk charges for it.', ['buff-food', 'unhungry', 'queue'],
          '$$', 'indoor', ['solo', 'friends', 'date'], ALL_DAY, cuisine='buff food',
          spots=['the counter', 'the slate of today\'s buffs', 'the back table']),
    place('the-tap-and-tally', 'the Tap and Tally', 'tavern', 'the-lamp-quarter', 'A low taproom where natives drink and '
          'climbers come for the talk, since the beer is ash in their mouths. Dice, gossip about the floors, and a '
          'board of the missing.', ['tavern', 'rumors', 'dice', 'missing'], '$', 'indoor', ['solo', 'friends'],
          NIGHT + ('afternoon',), cuisine='tavern', spots=['the board of the missing', 'the dice table', 'the bar']),
    place('the-pallet-house', 'the Pallet House', 'inn', 'the-lamp-quarter', 'A lodging house of straw pallets by the '
          'night or the week, for arrivals with no guild, a few Talents, and nobody to vouch for them.',
          ['lodgings', 'cheap'], '$', 'indoor', ['solo'], NIGHT),
    place('sallis-counting-house', 'Sallis\'s counting house', 'shopping', 'the-lamp-quarter', 'Ivo Sallis lends '
          'Talents against what you will be worth, and writes it down. His terms are fair the first week.',
          ['lender', 'debt', 'contracts'], '$$$', 'indoor', ['solo'], ('morning', 'afternoon')),
    place('the-scriveners-stall', 'the scrivener\'s stall', 'shopping', 'waystone-plaza', 'A native with good eyes and '
          'a ladder who will search the Roll for a name, copy it out, and tell you how long it has been there, for a '
          'Talent. For more, she will tell you who else has asked.', ['the-roll', 'information', 'missing'], '$',
          'outdoor', ['solo'], ALL_DAY, spots=['the ladder', 'the copy book']),
    place('the-water-sellers', 'the water sellers', 'market', 'waystone-plaza', 'Natives with yokes and dippers '
          'working the edge of the plaza, selling cups of water to arrivals who have not yet learned they do not '
          'need it.', ['water', 'new-wave'], '$', 'outdoor', ['solo', 'friends'], ALL_DAY,
          spots=['the plaza steps', 'the trough']),
    place('the-guild-mess', 'the guild mess', 'restaurant', 'guild-row', 'A long room off the guild row where any '
          'registered climber can eat at a common table, and every guild on the row listens in.',
          ['guilds', 'rumors', 'common-table'], '$', 'indoor', ['friends', 'coworkers'], ALL_DAY,
          cuisine='stew and bread', spots=['the common table', 'the hatch']),
    place('the-gate-tea-stall', 'the gate tea stall', 'cafe', 'the-east-gate', 'A tin-roofed stall under the arch '
          'where porters drink strong tea before a carry and the touts work the line.',
          ['porters', 'tea', 'touts'], '$', 'outdoor', ['solo', 'coworkers'], ('morning', 'afternoon'),
          cuisine='tea', spots=['the bench under the arch', 'the kettle']),
]

concourse_careers = [
    career('stall-keeper', 'Stall keeper', 'market', 'early', 'freelance', '$', 'Running a cart or a stall on the '
           'market streets, and paying the rows their rent.', ['the rows', 'Fire Market', 'rent']),
    career('cook-shop-cook', 'Cook', 'food', 'shift-day', 'staff', '$$', 'Cooking food with a System effect, the only '
           'meals climbers can taste.', ['buffs', 'the Unhungry', 'queues']),
    career('porter', 'Stair porter', 'travel', 'early', 'freelance', '$', 'Carrying loads up and down the Stair for '
           'whoever pays.', ['the Stair', 'loads', 'tolls']),
    career('cage-hand', 'Cage hand', 'travel', 'rotating', 'staff', '$', 'Working the lift cage\'s chains and lever.',
           ['the cage', 'the drop', 'floors']),
    career('guild-climber', 'Guild climber', 'guild', 'rotating', 'rota', '$$', 'Climbing for a guild: escorts, quests, '
           'floor runs, and sharing what comes back.', ['ranks', 'escorts', 'the Turning']),
    career('scrivener', 'Scrivener', 'information', 'shift-day', 'freelance', '$', 'Copying the Roll, writing letters '
           'and contracts for those who cannot.', ['the Roll', 'letters', 'secrets']),
    career('armorer', 'Armorer', 'craft', 'shift-day', 'staff', '$$', 'Forging and fitting arms and armor, graded on '
           'the ladder.', ['the forge', 'grades', 'customers']),
    career('lodging-keeper', 'Lodging keeper', 'lodging', 'evening', 'staff', '$', 'Renting pallets and rooms by the '
           'night.', ['arrivals', 'debts', 'thin walls']),
    career('rent-collector', 'Rent man', 'market', 'early', 'staff', '$$', 'Collecting the market rows\' stall rents.',
           ['the rows', 'debts', 'standing near carts']),
]

concourse_employers = [
    employer('the-landing-guild', 'the Landing', 'guild', 'guild-row', 'small', 'Darla Kinney\'s guild of veterans from '
             'before the Turning.', ['guild-climber']),
    employer('the-big-guilds', 'the guild halls', 'guild', 'guild-row', 'large', 'The bigger guilds on the row.',
             ['guild-climber', 'scrivener']),
    employer('the-rows', 'the market rows', 'market', 'the-market-streets', 'large', 'Whoever controls the stall '
             'rents.', ['stall-keeper', 'rent-collector']),
    employer('the-east-gate-crew', 'the east gate', 'travel', 'the-east-gate', 'medium', 'The cage and the porters.',
             ['cage-hand', 'porter']),
    employer('osks', "Osk's Kitchen", 'food', 'the-lamp-quarter', 'small', 'The cook-shop with food that tastes.',
             ['cook-shop-cook']),
    employer('brask', 'Brask and Daughters', 'craft', 'the-market-streets', 'small', 'Armorers and outfitters.',
             ['armorer']),
]

concourse = city(
    'the-concourse', 'the Concourse',
    'Floor Zero of the tower, where the arrivals land: a city under a gold-veined dome so high it has weather, with '
    'the great white Waystone in its plaza, the guild row, the market streets and the east gate onto the Stair. A Safe '
    'Zone covers all of it. Since the Turning it looks almost exactly like BABEL\'s Floor Zero.',
    'Floor Zero', ['Floor Zero', 'the Concourse'], LAT, LON, {'walk': 4.5},
    concourse_hoods, concourse_places, concourse_careers, concourse_employers,
    [{'id': 'the-market', 'name': 'The market and the gate', 'neighborhoods': ['the-market-streets', 'the-east-gate',
      'the-lamp-quarter'], 'sectors': ['market', 'travel', 'food', 'lodging', 'craft'], 'summary': 'Most native wages '
      'on the Concourse come from selling to climbers or carrying for them.', 'source': SRC}],
    [{'id': 'on-foot', 'name': 'On foot', 'kind': 'walk', 'summary': 'The plaza to the east gate is a quarter hour.',
      'source': SRC},
     {'id': 'porters', 'name': 'Porters', 'kind': 'walk', 'summary': 'For a Talent a load.', 'source': SRC},
     {'id': 'the-lift-cage', 'name': 'The lift cage', 'kind': 'tram', 'summary': 'Up one to Varrow or down one to St. '
      'Agathe\'s, from the east gate, to Waystones you have touched.', 'source': SRC}],
    {'summary': 'Under the dome: mild, smoky, with its own weather high up. Rain falls from the haze some days and '
     'never reaches the plaza dry.', 'months': months(
         [70] * 12, [58] * 12, [4, 4, 5, 5, 4, 3, 3, 3, 4, 5, 5, 4],
         ['The dome is gray for days at a time.', 'Haze rain.', 'The bells ring in the weather.', 'Warm smoke.',
          'Clear high up.', 'The cookfire smoke hangs low.', 'Bright.', 'Bright.', 'Mist in the bells.',
          'Rain from the haze.', 'Gray.', 'Gray and close.']), 'source': SRC},
    [],
    [color('fire-market', 'Fire Market', 'custom', 'The best trading day of the week. Cookfires never go out and the '
           'rows collect double.', ['fire-market-rows', 'hamids-cart']),
     color('mind-the-stair', 'Mind the stair', 'saying', 'What the Concourse says instead of goodbye, from the words '
           'over the east gate.', ['the-gate-arch']),
     color('down-somewhere-worse', 'Down somewhere worse', 'saying', 'Anyone not on the Roll by nightfall came down '
           'somewhere worse, or did not come down.', ['the-waystone']),
     color('the-unhungry', 'The Unhungry', 'custom', 'Natives sell climbers food they cannot taste and drink they do '
           'not need, and climbers buy it anyway, for the company.', ['the-tap-and-tally', 'osks-kitchen']),
     color('new-wave', 'New wave', 'saying', 'Said with a sigh whenever an arrival does something stupid, or flashes '
           'red in a Safe Zone.', ['the-plaza']),
     color('the-white-ring', 'The white ring', 'rumor', 'Old natives look twice at white-ringed eyes. Ask why and they '
           'say a big one came down in an earlier wave, and something bad followed.', ['hamids-cart']),
     color('the-long-house', 'The Long House', 'legend', 'Before the Turning, the Stone greeted arrivals like a tent '
           'preacher: Welcome, child, to the Long House.', ['the-waystone']),
     color('never-st-agathes', 'Never go down to St. Agathe\'s', 'saying', 'Every veteran\'s first piece of advice.',
           ['the-gate-arch'])],
    CONCOURSE_NAMES,
    [price('skewer', 'Skewer of charcoal meat', 0.3, 0.5), price('buff-meal', 'Meal at Osk\'s (it tastes)', 3, 6),
     price('ale', 'Mug of ale', 0.2, 0.4), price('pallet', 'Pallet at the Pallet House', 1, 2, 'night'),
     price('room', 'Room in the Lamp Quarter', 3, 5, 'night'), price('porter', 'A porter', 1, 2, 'load'),
     price('cage', 'The lift cage', 2, 2, 'one way'), price('sword', 'A plain graded sword (F)', 30, 50),
     price('roll-search', 'A search of the Roll', 1, 1), price('day-wage', 'A porter\'s day wage', 2, 3, 'day'),
     price('starter-kit', 'A resold starter satchel', 15, 25), price('cart', 'A skewer cart and a morning\'s stock',
                                                                       30, 30)],
    [notable('hamid', 'Hamid', 'Hamid', 'he/him', 58, 'hamids-cart', 'skewer seller', 'Runs a skewer cart by the '
             'plaza and refers to himself in the third person. He owes the market rows his stall rent and fears big '
             'arrivals with white-ringed eyes.', 'to make his Fire Market take'),
     notable('darla-kinney', 'Darla Kinney', 'Darla', 'she/her', 55, 'the-landing', 'head of the Landing', 'A veteran '
             'from before the Turning in a Dallas Cowboys jacket, Lv 14 ▸ Rank D. Wants leverage on the new skin, and '
             'lies to keep useful people close.', 'someone who understands the new skin before the guilds do'),
     notable('ruth-ann-teel', 'Ruth Ann Teel', 'Ruth Ann', 'she/her', 49, 'the-landing', 'quartermaster and smith',
             'A Delver who has kept the Landing\'s stores for eleven years and watched a man named Teague over its '
             'cookfire for two.', 'to be believed about Teague', kind='delver'),
     notable('danny-oyelaran', 'Danny Oyelaran', 'Danny', 'he/him', 24, 'the-landing', 'climber', 'The Landing\'s '
             'newest, a rabbit-eared Therian at 31% of F.', 'to rank up before the rules change again', staff=False),
     notable('sister-pia', 'Sister Pia', 'Pia', 'she/her', 40, 'the-landing', 'climber and Keeper', 'A mouthless Hollow '
             'who talks on a slate and knows Darla is hiding something.', 'someone to ask Darla about Teague',
             staff=False),
     notable('osk', 'Osk Lindqvist', 'Osk', 'she/her', 47, 'osks-kitchen', 'cook', 'A native Cook whose food tastes to '
             'climbers. She knows every arrival who has eaten at her counter and what they could afford.',
             'to be paid what her cooking is worth'),
     notable('cobb', 'Cobb', 'Cobb', 'he/him', 62, 'the-gate-arch', 'cage operator', 'The operator in the leather cap who '
             'calls the floors. He has seen everyone go up, and knows who came back.', 'a quiet shift'),
     notable('ivo-sallis', 'Ivo Sallis', 'Ivo', 'he/him', 44, 'sallis-counting-house', 'lender', 'Lends Talents to '
             'arrivals against what they will be worth, at terms that are fair for a week.', 'the engineer\'s debt'),
     notable('greer-brask', 'Greer Brask', 'Greer', 'she/her', 36, 'brask-and-daughters', 'armorer', 'The eldest Brask '
             'daughter, who grades blades on the ladder and hates doing it.', 'the old way of pricing back')],
)


# Hollin, on Varrow --------------------------------------------------------------------------------

VARROW_NAMES = {'groups': {
    'varrow': {
        'feminine': ['Marra', 'Ide', 'Tamsin', 'Abelone', 'Maud', 'Aveline', 'Orla', 'Berit', 'Nell', 'Gunnild',
                     'Elsbet', 'Wenna', 'Hild', 'Joan', 'Agnes', 'Sibbe'],
        'masculine': ['Aldo', 'Coll', 'Hask', 'Edmund', 'Gil', 'Pim', 'Tobe', 'Wat', 'Oswy', 'Rafe', 'Hennet', 'Jory',
                      'Dunstan', 'Hobb', 'Lambert', 'Osric'],
        'neutral': ['Wren', 'Linnet', 'Ash'],
        'family': ['Corve', 'Fenwick', 'Ashby', 'Cooper', 'Hode', 'Long', 'Hale', 'Miller', 'Thatcher', 'Reeve',
                   'Brook', 'Wainwright', 'Pask', 'Gedge', 'Hallam', 'Dunn']}}}

hollin_hoods = [
    hood('hollin-town', 'Hollin', 'The market town at the ford, just as the beta drew it: the green with its Waystone '
         'and well, thatched roofs, the stone bridge, the mill and its wheel, and Goodwife Marra on her bench.',
         ['town', 'beta', 'watched'], LAT + 0.02, LON, 'low', ([1, 2], [2, 3], [3, 5]),
         ['cottage', 'room-over-shop'], 'high', ['on-foot']),
    hood('the-stair-landing', 'the landing', 'The hillside above Hollin where the Stair opens onto Varrow under a pale '
         'sky, with steps down to the road.', ['arrival', 'hillside'], LAT + 0.023, LON - 0.004, 'low', None,
         ['none'], 'medium', ['on-foot']),
    hood('the-close', 'the Close', 'Saint Aurel\'s hill across the valley: the white cathedral, the cloister, the '
         'sisters\' house, the guesthouse, the old cemetery with its hives, and down by the river the Pens.',
         ['church', 'white', 'watched'], LAT + 0.024, LON + 0.006, 'mid', None, ['cell'], 'medium', ['on-foot']),
    hood('the-keep', 'Varrow Keep', 'The Margrave\'s hill: the Keep\'s ward and hall, the solar, the manor wing, the '
         'lower barracks, the east wall-walk and the Cairn tower, and the bone-cellar under it all.',
         ['lordly', 'gray', 'guarded'], LAT + 0.017, LON - 0.006, 'high', None, ['barracks', 'manor-room'], 'medium',
         ['on-foot', 'horse']),
    hood('the-valley-road', 'the valley road', 'Eight miles of road between hawthorns from the Keep to the valley '
         'head, with Burners\' Wood off to the east two miles short of the Wall.', ['road', 'hawthorn', 'woods'],
         LAT + 0.06, LON, 'low', None, ['cottage'], 'low', ['on-foot', 'horse', 'mule']),
    hood('the-reachwall', 'the Reachwall', 'Thirty feet of fitted stone across the valley head with a rampart walk '
         'three abreast and towers every quarter mile, the badly patched breach by the north tower, and the ditch '
         'below. Past it, the Reach.', ['wall', 'border', 'dangerous'], LAT + 0.135, LON, 'low', None,
         ['barracks'], 'low', ['on-foot']),
]

hollin_places = [
    place('the-green', 'Hollin green', 'square', 'hollin-town', 'The green with the Waystone in the middle and the '
          'well and bucket at the bottom of the hill road. A board on a post by the well, in fresh black paint that '
          'was never in any build: NO MARKED BEYOND THE FORD BY ORDER OF THE CLOSE.',
          ['central', 'waystone', 'notices'], 'free', 'outdoor', ['solo', 'friends', 'family'], ALL_DAY,
          spots=['the Waystone', 'the well and bucket', 'the notice board', 'the Keep road']),
    place('the-ford', 'the ford', 'trail', 'hollin-town', 'Stepping stones across the river below the mill, and the '
          'Close\'s line: no Marked beyond it.', ['river', 'border', 'bounty'], 'free', 'outdoor', ['solo'], ALL_DAY,
          spots=['the stepping stones', 'the deep pool below', 'the far bank']),
    place('the-mill', 'the mill', 'workshop', 'hollin-town', 'The water mill and its wheel by the ford, and Goodwife '
          'Marra\'s stone cottage beside it, where she shells peas on the bench and sends climbers after rats in the '
          'dry cellar her husband built.', ['mill', 'tutorial', 'hidden'], 'free', 'mixed',
          ['solo', 'friends'], ALL_DAY, spots=['Marra\'s bench', 'the mill cellar door', 'the mill wall', 'the wheel']),
    place('the-stone-bridge', 'the stone bridge', 'landmark', 'hollin-town', 'The old bridge on the Keep road, where '
          'the Keep\'s riders and the Close\'s wardens pass each other without speaking.', ['bridge', 'road'], 'free',
          'outdoor', ['solo'], ALL_DAY),
    place('the-bell-and-bushel', 'the Bell and Bushel', 'tavern', 'hollin-town', 'Hollin\'s alehouse: small beer, '
          'bread, a fire, the Keep\'s men on one side of the room and the Close\'s lay brothers on the other.',
          ['ale', 'rumors', 'rooms'], '$', 'indoor', ['solo', 'friends'], ('afternoon', 'evening', 'late'),
          cuisine='alehouse', spots=['the Keep side', 'the Close side', 'the fire']),
    place('the-landing-steps', 'the landing steps', 'landmark', 'the-stair-landing', 'Where the Stair opens out of '
          'the floor\'s wall onto the hillside above Hollin. Below lies the beta, almost exactly. A Close acolyte '
          'sweeps the steps and watches who comes up.', ['arrival', 'stair', 'watched'], 'free', 'outdoor',
          ['solo', 'friends'], EVERY, spots=['the top step', 'the view of the valley', 'the road down']),
    place('saint-aurel', 'Saint Aurel', 'temple', 'the-close', 'The white cathedral, its spires the beta\'s pride. In '
          'the nave hang the Scales: a black iron beam and two bronze pans big enough to stand in, over a brass arc '
          'with a sun at one end and a cracked wall at the other. One does not stand in the pan shod.',
          ['cathedral', 'the-scales', 'weighing'], 'free', 'indoor', ['solo', 'family'], ALL_DAY,
          spots=['the Scales', 'the front pew', 'the nave', 'the door behind the Scales']),
    place('the-guesthouse', 'the guesthouse', 'inn', 'the-close', 'Whitewashed cells across the cloister with tin '
          'sun-discs over the doors and windows on the herb garden. No bolts on the doors; boots outside them.',
          ['cells', 'watched'], 'free', 'indoor', ['solo'], NIGHT, spots=['Hask\'s six-foot bed', 'the herb garden']),
    place('the-infirmary', 'the infirmary', 'temple', 'the-close', 'Brother Coll\'s rooms: basins, willow bark, clean '
          'linen and a Keeper\'s Mend.', ['healing', 'mend'], 'free', 'indoor', ['solo'], ALL_DAY),
    place('the-sisters-house', 'the sisters\' house', 'temple', 'the-close', 'Where the vowed sisters live, and where '
          'Sister Maud still trims a dead giant\'s lamp.', ['sisters', 'vows'], 'free', 'indoor', ['solo'], ALL_DAY,
          spots=['Hask\'s lamp', 'the basins']),
    place('the-old-cemetery', 'the old cemetery', 'garden', 'the-close', 'Sister Abelone\'s hives among the old graves, '
          'a prayer over each at Lauds. Her honey is the only food on Varrow that tastes to a climber.',
          ['hives', 'honey', 'graves'], 'free', 'outdoor', ['solo'], ('morning', 'afternoon')),
    place('the-pens', 'the Pens', 'landmark', 'the-close', 'The old tannery on the river, where the Close holds Marked '
          'found beyond the ford, and in autumn the wanting, until the cage goes down in spring.',
          ['prison', 'river', 'cage-trade'], 'free', 'mixed', ['solo'], EVERY, spots=['the gate', 'the river door']),
    place('the-keep-hall', 'the Margrave\'s hall', 'landmark', 'the-keep', 'The Keep\'s great hall under the black stag '
          'on silver, gray-and-blue livery, the Margrave\'s chair with the Muster board and his old gauntlet behind '
          'it, and a gray lurcher on the hearth.', ['hall', 'lord', 'muster'], 'free', 'indoor', ['solo', 'coworkers'],
          ALL_DAY, spots=['the Muster board', 'the Margrave\'s chair', 'the hearth']),
    place('the-solar', 'the Margrave\'s solar', 'landmark', 'the-keep', 'His private room up the solar stair: a fire, '
          'a good table, lunch, and his dead wife\'s harp that nobody plays.', ['private', 'lunch', 'harp'], 'free',
          'indoor', ['solo', 'date'], ('afternoon', 'evening'), spots=['Aveline\'s harp', 'the table', 'the window']),
    place('the-keep-chapel', 'the Keep chapel', 'temple', 'the-keep', 'A small chapel in the manor wing with a side '
          'door by the solar.', ['chapel', 'quiet'], 'free', 'indoor', ['solo'], EVERY),
    place('the-lower-barracks', 'the lower barracks', 'inn', 'the-keep', 'A long low room of wool, boot grease and '
          'twenty men, arrow-slit light, and in one corner a bunk nobody takes.', ['barracks', 'soldiers'], 'free',
          'indoor', ['solo', 'coworkers'], NIGHT, spots=['Teague\'s old bunk', 'the aisle', 'the arrow slits']),
    place('the-cairn-tower', 'the Cairn tower', 'landmark', 'the-keep', 'The tower on the Keep\'s east wall-walk, his '
          'lordship\'s ground, with only the one stair up. From the top: the valley head, the Wall, and the beacons on '
          'the Reach.', ['view', 'private'], 'free', 'outdoor', ['solo', 'date'], ('afternoon', 'evening')),
    place('the-bone-cellar', 'the bone-cellar', 'landmark', 'the-keep', 'The catacombs under the Keep. In the beta a '
          'stair here let climbers up off the floor. It is locked, and the Margrave keeps the key.',
          ['catacombs', 'stair', 'secret'], 'free', 'indoor', ['solo'], EVERY, spots=['the stair', 'the bone shelves']),
    place('burners-wood', 'Burners\' Wood', 'trail', 'the-valley-road', 'Woods two miles short of the Wall, with charcoal '
          'clearings where a cart can wait off the road and nobody on the rampart can see.', ['woods', 'charcoal',
          'ambush'], 'free', 'outdoor', ['solo'], ALL_DAY, spots=['the burners\' clearing', 'the cart track']),
    place('the-rampart', 'the rampart walk', 'landmark', 'the-reachwall', 'Three abreast along the top of the Wall, horns '
          'in every tower. At dusk you can see the beacons on the Reach ridges.', ['wall', 'watch', 'horns'], 'free',
          'outdoor', ['solo', 'coworkers'], EVERY, spots=['the north tower', 'the gate tower', 'the horn']),
    place('the-patch', 'the patch', 'workshop', 'the-reachwall', 'The breach by the north tower, rebuilt badly in rubble '
          'and timber three winters ago, the color of a healed burn. Orla\'s plumb line and the earth ramp for '
          'hauling stone.', ['repair', 'labor', 'weak-point'], 'free', 'outdoor', ['coworkers'], ALL_DAY,
          spots=['the earth ramp', 'the timber shoring', 'Orla\'s line']),
    place('the-north-tower-chapel', 'the north tower chapel', 'temple', 'the-reachwall', 'A chapel in the north tower '
          'where a gift\'s sister keeps his lamp.', ['chapel', 'lamp'], 'free', 'indoor', ['solo'], EVERY),
    place('the-drill-ground', 'the drill ground', 'venue', 'the-reachwall', 'Beaten earth below the tower where Captain '
          'Hode drills the company: sticks first, blunted blades after.', ['drill', 'training'], 'free', 'outdoor',
          ['coworkers'], ('morning', 'afternoon')),
    place('the-ditch', 'the ditch', 'trail', 'the-reachwall', 'The ditch below the patch, where the giants stand when '
          'they come to talk, a little more than their own height from the rampart.', ['border', 'parley',
          'giants'], 'free', 'outdoor', ['solo'], ('evening', 'late')),
    place('the-wall-kitchen', 'the Wall kitchen', 'restaurant', 'the-reachwall', 'The company\'s cookhouse under the '
          'north tower: porridge, salt pork, small beer, and whatever the sisters send down.',
          ['company', 'mess'], 'free', 'indoor', ['coworkers'], EVERY, cuisine='camp fare',
          spots=['the long bench', 'the fire']),
    place('the-landing-alehouse', 'the landing alehouse', 'tavern', 'the-stair-landing', 'A two-table alehouse by the '
          'cage where porters wait for Cobb, and the Close\'s men watch who comes up.',
          ['porters', 'watchers'], '$', 'indoor', ['solo', 'friends'], ALL_DAY, cuisine='alehouse',
          spots=['the window on the cage', 'the bar']),
    place('the-mile-inn', 'the mile inn', 'inn', 'the-valley-road', 'A posting inn halfway up the valley road with '
          'a stable, a fire and a landlady who knows every rider of the Keep.',
          ['rooms', 'riders', 'stable'], '$', 'indoor', ['solo', 'friends'], EVERY, cuisine='alehouse',
          spots=['the settle by the fire', 'the stable yard']),
]

hollin_careers = [
    career('miller', 'Miller', 'grain', 'early', 'staff', '$', 'Grinding at the mill by the ford.', ['the wheel', 'flour',
           'the cellar']),
    career('wall-soldier', 'Wall soldier', 'wall', 'rotating', 'rota', '$', 'A season on the Reachwall in the '
           'Margrave\'s company: stone, drill and the horns at dusk.', ['the Wall', 'the Reach', 'the patch']),
    career('mason', 'Mason', 'wall', 'early', 'staff', '$$', 'Laying stone at the patch under Orla\'s line.',
           ['stone', 'the patch', 'the cold coming']),
    career('warden', 'Warden of the Close', 'church', 'rotating', 'rota', '$', 'A halberd and a white tabard with the '
           'gold sun.', ['the ford', 'the Marked', 'orders']),
    career('lay-brother', 'Lay brother', 'church', 'early', 'staff', '$', 'Working the Close\'s fields, kitchens and '
           'gates.', ['the Close', 'chores', 'gossip']),
    career('keep-servant', 'Keep servant', 'household', 'early', 'staff', '$', 'Serving in the Margrave\'s household.',
           ['the Keep', 'the solar', 'the hall']),
    career('charcoal-burner', 'Charcoal burner', 'woods', 'rotating', 'staff', '$', 'Tending the kilns in Burners\' '
           'Wood.', ['the kilns', 'smoke', 'the road']),
    career('farmhand', 'Farmhand', 'farm', 'early', 'staff', '$', 'Working the valley\'s fields.', ['harvest',
           'the weighing', 'mud']),
]

hollin_employers = [
    employer('house-corve', 'House Corve', 'household', 'the-keep', 'medium', 'The Margrave\'s household and his Wall '
             'company.', ['wall-soldier', 'mason', 'keep-servant']),
    employer('the-close-church', 'the Close of Saint Aurel', 'church', 'the-close', 'medium', 'Varrow\'s church.',
             ['warden', 'lay-brother']),
    employer('hollin-mill', 'the Hollin mill', 'grain', 'hollin-town', 'small', 'The mill by the ford.',
             ['miller', 'farmhand']),
]

hollin = city(
    'hollin', 'Hollin',
    'Varrow\'s market town at the ford, one floor up from the Concourse, almost exactly as BABEL\'s beta drew it: the '
    'mill, the stone bridge, the green with its Waystone and well. Saint Aurel\'s white cathedral stands on one hill '
    'and Varrow Keep on the other, and eight miles up the valley the Reachwall holds back the Reach. The Close weighs '
    'the big and bans the Marked beyond the ford.',
    'Varrow', ['Varrow', 'Hollin'], LAT + 0.02, LON, {'walk': 4.5, 'horse': 10},
    hollin_hoods, hollin_places, hollin_careers, hollin_employers,
    [{'id': 'the-valley', 'name': 'The Keep and the Close', 'neighborhoods': ['the-keep', 'the-close',
      'the-reachwall'], 'sectors': ['household', 'church', 'wall'], 'summary': 'Most of Varrow\'s wages come from the '
      'Margrave or the Close.', 'source': SRC}],
    [{'id': 'on-foot', 'name': 'On foot', 'kind': 'walk', 'summary': 'Hollin is a quarter hour end to end; the Keep '
      'and the Close are each a stiff climb; the Wall is eight miles.', 'source': SRC},
     {'id': 'horse', 'name': 'Horse', 'kind': 'horse', 'summary': 'The Keep\'s riders, and a roan for a guest the '
      'Margrave likes.', 'source': SRC},
     {'id': 'mule', 'name': 'Mule', 'kind': 'horse', 'summary': 'The Close\'s sisters ride white mules.',
      'source': SRC}],
    {'summary': 'Varrow\'s valley under a real-looking sky: mild summers, a wet autumn, and the first frost that '
     'brings the Reach down and the Close\'s weighing.', 'months': months(
         [40, 43, 50, 57, 64, 70, 74, 73, 66, 57, 48, 41], [28, 30, 35, 40, 46, 51, 55, 54, 49, 42, 35, 30],
         [12, 10, 11, 10, 10, 9, 8, 9, 10, 12, 13, 13],
         ['Hard cold on the Wall.', 'Snow on the Reach.', 'Mud.', 'Lambing.', 'The fields green.', 'Long days.',
          'The warmest month.', 'Lammas: the Close reads the names of its kept.', 'Harvest.',
          'The first frost, and the weighing.', 'The cage goes quiet until spring.', 'Bitter on the rampart.']),
     'source': SRC},
    [{'id': 'lammas', 'name': 'Lammas', 'months': [8], 'neighborhood': 'the-close', 'summary': 'The Close reads out '
      'the names of its kept.', 'source': SRC},
     {'id': 'the-weighing', 'name': 'The autumn weighing', 'months': [10], 'neighborhood': 'the-close',
      'summary': 'At the first frost the Close weighs Hollin\'s people. Those found wanting go to the Pens.',
      'source': SRC},
     {'id': 'the-spring-cage', 'name': 'The spring cage', 'months': [4], 'neighborhood': 'the-stair-landing',
      'summary': 'The Pens empty down the Stair, and nobody in Hollin watches the cage go.', 'source': SRC}],
    [color('rats', 'Rats', 'saying', 'Rats is what Hollin says about the Marked when the Close is listening.',
           ['the-mill']),
     color('the-gift', 'The gift', 'custom', 'A giant the Close weighs and keeps is its gift: a cell, a lamp, his name '
           'read at Lammas, a sister to tend him, and the Wall.', ['saint-aurel', 'the-sisters-house']),
     color('sun-stoles', 'Sun stoles', 'custom', 'The Close marks what it keeps with white stoles and the gold sun, so '
           'the Margrave\'s men know whose it is.', ['saint-aurel']),
     color('two-finger-sign', 'The two-finger sign', 'custom', 'Close folk make a sign across the chest with two '
           'fingers at anything big, Marked or ringed-eyed.', ['the-landing-steps']),
     color('hask', 'Brother Hask', 'legend', 'The last gift: a giant forty years on the Wall, who slept on the floor '
           'because the Close never made him a longer bed. He died last winter in his sleep.', ['the-guesthouse']),
     color('the-onion-game', 'The onion game', 'custom', 'A barracks game nobody explains to outsiders.',
           ['the-lower-barracks']),
     color('aldo', 'Aldo went in the river', 'rumor', 'The miller went in the river, Marra says, and that is all she '
           'says.', ['the-mill']),
     color('close-honey', 'Close honey', 'dish', 'Sister Abelone\'s honey, which gives a climber a little Resolve and '
           'actually tastes.', ['the-old-cemetery'])],
    VARROW_NAMES,
    [price('small-beer', 'Cup of small beer', 0.1, 0.2), price('bread', 'Brown bread', 0.1, 0.2),
     price('honey', 'Pot of Close honey', 2, 3), price('room', 'Room at the Bell and Bushel', 2, 3, 'night'),
     price('wall-wage', 'A Wall soldier\'s wage', 1, 2, 'day'), price('marked-bounty', 'Close bounty on a Marked', 1, 2,
                                                                         'head'),
     price('harper', 'A harper in the Keep', 3, 3, 'week'), price('mend', 'A Keeper\'s Mend at the infirmary', 0, 2)],
    [notable('goodwife-marra', 'Goodwife Marra', 'Marra', 'she/her', 61, 'the-mill', 'miller\'s widow', 'BABEL\'s '
             'tutorial quest-giver, who sends climbers after rats in her dead husband\'s mill cellar, and drops the '
             'script when she decides to trust you.', 'to get her rats onto the cage down'),
     notable('the-archdeacon', 'the Archdeacon', 'the Archdeacon', 'he/him', 300, 'saint-aurel', 'Archdeacon of Saint '
             'Aurel', 'A Seraph with ash-gray wings and pale fire at the pupils, calm and kind-voiced, whose spoken '
             'word is obeyed. He weighs the big, and keeps what he weighs.', 'a Nephil, weighed and kept',
             kind='seraph'),
     notable('sister-ide', 'Sister Ide', 'Ide', 'she/her', 30, 'the-sisters-house', 'vowed sister', 'Eleven years in '
             'vows, barefoot in white wool, light showing at her collarbones. She has waited all that time for a '
             'giant.', 'to finish the Consecration'),
     notable('brother-coll', 'Brother Coll', 'Coll', 'he/him', 68, 'the-infirmary', 'infirmarian', 'Old, round, '
             'talkative, a Keeper\'s Mend in his hands; pleased to be asked, and honest about who he will have to '
             'tell.', 'to see the Bishop come home'),
     notable('brother-tamsin', 'Brother Tamsin', 'Tamsin', 'he/him', 46, 'saint-aurel', 'warden captain', 'Leads the '
             'Close\'s wardens and reads lists somebody else wrote.', 'the Close\'s claims kept'),
     notable('sister-abelone', 'Sister Abelone', 'Abelone', 'she/her', 52, 'the-old-cemetery', 'beekeeper', 'Keeps the '
             'hives among the old graves. Unbearable when praised.', 'her honey praised'),
     notable('edmund-corve', 'the Margrave', 'Edmund', 'he/him', 63, 'the-keep-hall', 'Margrave of Varrow', 'Lean, '
             'one-armed, dry, with a gray lurcher at his feet. He owns the valley and the Close owns his soul, and he '
             'is tired of the arrangement.', 'the Wall under his own banner'),
     notable('oswy', 'Oswy', 'Oswy', 'he/him', 50, 'the-keep-hall', 'steward', 'Long and silent; sits outside doors.',
             'the household kept'),
     notable('hennet', 'Hennet', 'Hennet', 'they/them', 41, 'the-lower-barracks', 'cook', 'Stirs the barracks porridge '
             'with a paddle and shouts at anyone near the pot.', 'enough oats for the winter'),
     notable('berit-hode', 'Captain Berit Hode', 'Berit', 'she/her', 45, 'the-rampart', 'Wall captain', 'Commands the '
             'Margrave\'s Wall-work company with a flattened nose and calm eyes.', 'the patch rebuilt properly'),
     notable('gil-fenwick', 'Gil Fenwick', 'Gil', 'he/him', 54, 'the-rampart', 'Wall veteran', 'Heavy, gray-bearded, '
             'a face like a dropped pie. Stood a season with the last man with white-ringed eyes and buried six '
             'afterward.', 'one more season, then his sister\'s farm'),
     notable('orla', 'Orla', 'Orla', 'she/her', 58, 'the-patch', 'master mason', 'Laid the Wall\'s first courses as a '
             'girl and directs with her chin.', 'the patch laid right'),
     notable('pim', 'Pim', 'Pim', 'he/him', 19, 'the-lower-barracks', 'Wall soldier', 'Gangly, burn-scarred, believes '
             'everything Gil says.', 'a story worth telling', staff=False)],
)


# The Gilded Bazaar --------------------------------------------------------------------------------

BAZAAR_NAMES = {'groups': {
    'bazaar': {
        'feminine': ['Sabeen', 'Nell', 'Merrow', 'Yasmin', 'Odile', 'Cressida', 'Fenna', 'Leocadia', 'Iolanthe', 'Rue',
                     'Damaris', 'Saffi', 'Zelie', 'Honor'],
        'masculine': ['Okonkwo', 'Pell', 'Wick', 'Barnaby', 'Casimir', 'Tobias', 'Emeric', 'Haskel', 'Quill', 'Ravi',
                      'Sorley', 'Anselm', 'Fitch', 'Marek'],
        'neutral': ['Dot', 'Clove', 'Tinker', 'Marlo'],
        'family': ['Oro', 'Vale', 'the Wire', 'Copperhand', 'Saffron', 'Lessard', 'Marchetti', 'Ibekwe', 'Duquesne',
                   'Halloran', 'Steepwater', 'Mendoza', 'Achebe', 'Varga']}}}

bazaar_hoods = [
    hood('the-lantern-dome', 'under the lantern dome', 'The center of the floor under a dome hung with lanterns that '
         'brighten and dim twice in a Concourse day: salons, spice houses, and rooms let by the week.',
         ['wealthy', 'night', 'priced'], LAT + 0.05, LON, 'very-high', ([40, 60], [70, 100], [120, 180]),
         ['salon-room', 'townhouse'], 'high', ['on-foot', 'chairmen']),
    hood('the-spice-rows', 'the spice rows', 'Factors\' houses and warehouses that smell of clove and pepper, where '
         'the floor\'s money is made and Okonkwo Vale buys his drinks.', ['merchant', 'fragrant'], LAT + 0.052,
         LON + 0.003, 'high', ([30, 45], [50, 70], [80, 120]), ['townhouse', 'room-over-shop'], 'high',
         ['on-foot', 'chairmen']),
    hood('the-copper-steps', 'the Copper Steps', 'A broad flight of copper-shod steps down toward the shaft, with fence '
         'rows and paper sellers in the arcades under it, and behind them the toll gate onto the Stair.',
         ['fences', 'paper', 'gate'], LAT + 0.049, LON + 0.005, 'low', ([10, 15], [18, 24], [26, 36]),
         ['room-over-shop', 'garret'], 'high', ['on-foot']),
    hood('the-wharf', 'the freight wharf', 'Cranes and chain-winches on the shaft\'s edge, where cargo cages load for '
         'the floors above and below, and a night crew runs one Sabeen does not own.', ['docks', 'night', 'smuggling'],
         LAT + 0.047, LON + 0.008, 'low', ([8, 12], [14, 20], [22, 30]), ['bunkhouse', 'garret'], 'medium',
         ['on-foot']),
]

bazaar_places = [
    place('the-lantern-room', 'the Lantern Room', 'nightlife', 'the-lantern-dome', 'Sabeen Oro\'s salon: lamps under '
          'colored glass, low divans, hostesses and dancers on a polished floor, and private rooms off it, the Blue '
          'Room among them, at the girl\'s choice and a third to the house. Sabeen prices people the way the Bazaar '
          'prices everything, and her guests come to watch her do it.', ['salon', 'dancing', 'private-rooms'], '$$$$',
          'indoor', ['solo', 'date'], NIGHT, spots=['Sabeen\'s couch', 'the dancing floor', 'the Blue Room',
                                                    'the girls\' stair']),
    place('the-copper-scale', 'the Copper Scale', 'inn', 'the-lantern-dome', 'Rooms by the week up three flights: '
          'narrow beds with brass frames, a copper basin, one shuttered window on the street. The walls are thin and '
          'the neighbors hear everything.', ['rooms', 'thin-walls'], '$$$', 'indoor', ['solo', 'date'], NIGHT,
          spots=['room 3, top floor, street side', 'the stair', 'the landlady\'s hatch']),
    place('the-spice-exchange', 'the spice exchange', 'market', 'the-spice-rows', 'A hall of factors shouting prices for '
          'clove, pepper and things that are not spice, under a board that changes faster than anyone can read it.',
          ['market', 'spice', 'prices'], '$$$', 'indoor', ['solo', 'coworkers'], ALL_DAY,
          spots=['the price board', 'the factors\' gallery']),
    place('the-charm-sellers', 'the charm sellers', 'shopping', 'the-spice-rows', 'Bazaar charms by grade: copper rings '
          'that keep a night from having consequences, hush-beads that muffle words sent over a bond, luck knots. '
          'Graded on the ladder, priced to match.', ['charms', 'graded', 'contraceptive'], '$$$', 'indoor', ['solo'],
          ALL_DAY, spots=['the ring tray', 'the hush-beads']),
    place('the-fence-rows', 'the fence rows', 'market', 'the-copper-steps', 'Arcades under the Copper Steps where Pell '
          'the Wire and their cousins buy anything, sell anything, and trade in rumor most of all.',
          ['fences', 'rumors', 'stolen'], '$$', 'mixed', ['solo'], EVERY, spots=['Pell\'s table', 'the back arcade']),
    place('wicks-paper', 'Old Wick\'s paper', 'shopping', 'the-copper-steps', 'A paper seller under the Steps: maps of '
          'floors, letters, bills of sale, and the occasional hand-drawn route someone sold to get up the Stair.',
          ['maps', 'paper', 'routes'], '$$', 'indoor', ['solo'], ALL_DAY, spots=['the map drawer']),
    place('the-stair-gate', 'the Stair gate', 'landmark', 'the-copper-steps', 'An old iron cage of a toll booth behind '
          'the Copper Steps, onto the Stair. Two Talents up. Down is free, because nobody comes back to pay. The gate '
          'is Sabeen Oro\'s, and Pell\'s cousin keeps it.', ['gate', 'toll', 'stair'], '$', 'outdoor', ['solo'], EVERY,
          spots=['the toll window', 'the first flight up']),
    place('the-freight-wharf', 'the freight wharf', 'docks', 'the-wharf', 'Cranes, winches and cargo cages on the '
          'shaft\'s edge. After dome-dark a night crew loads an unlicensed cage for the floors below, and takes '
          'passengers for everything they have.', ['docks', 'smuggling', 'night-cage'], '$$', 'outdoor', ['solo'],
          EVERY, spots=['the night crew\'s cage', 'the foreman\'s lantern', 'the edge']),
    place('the-crier-post', 'the crier\'s post', 'landmark', 'the-copper-steps', 'Where notices go up for the floor and '
          'go down the chain to the others: sales, debts, and the Lantern Room\'s bounties.', ['news', 'bounties'],
          'free', 'outdoor', ['solo'], ALL_DAY),
    place('the-wharf-kitchen', 'the wharf kitchen', 'restaurant', 'the-wharf', 'A brazier, a pot and a plank bench '
          'where crane crews eat between cages, and the night crew eats before.',
          ['crews', 'night-cage'], '$', 'outdoor', ['coworkers'], EVERY, cuisine='rice and spiced meat',
          spots=['the plank bench', 'the brazier']),
]

bazaar_careers = [
    career('salon-hostess', 'Salon hostess', 'salon', 'evening', 'staff', '$$', 'Hostessing, dancing and private rooms at '
           'a salon, a third to the house.', ['the house cut', 'clients', 'the floor'], adult=True),
    career('runner', 'Runner', 'salon', 'rotating', 'freelance', '$$', 'Fetching people and debts down the Stair for a '
           'house.', ['the Stair', 'debts', 'fetching']),
    career('factor', 'Spice factor', 'merchant', 'office', 'staff', '$$$', 'Buying and selling spice and other things on '
           'the exchange.', ['prices', 'cargo', 'clients']),
    career('fence', 'Fence', 'criminal', 'evening', 'freelance', '$$', 'Buying and selling what nobody asks about.',
           ['rumors', 'stolen goods', 'cousins']),
    career('charm-maker', 'Charm maker', 'craft', 'shift-day', 'staff', '$$$', 'Making graded Bazaar charms.',
           ['grades', 'copper', 'customers']),
    career('wharf-hand', 'Wharf hand', 'docks', 'shift-night', 'staff', '$', 'Loading cargo cages on the shaft\'s edge.',
           ['the chains', 'the drop', 'the night crew']),
    career('room-letter', 'Room letter', 'lodging', 'evening', 'staff', '$$', 'Letting rooms by the week and hearing '
           'through the walls.', ['rooms', 'debts', 'thin walls']),
]

bazaar_employers = [
    employer('the-lantern-room-house', 'the Lantern Room', 'salon', 'the-lantern-dome', 'medium', 'Sabeen Oro\'s house.',
             ['salon-hostess', 'runner']),
    employer('the-exchange', 'the spice exchange', 'merchant', 'the-spice-rows', 'large', 'The factors\' hall.',
             ['factor']),
    employer('the-wharf-gangs', 'the freight wharf', 'docks', 'the-wharf', 'medium', 'The cargo cages.',
             ['wharf-hand']),
]

bazaar = city(
    'the-gilded-bazaar', 'the Gilded Bazaar',
    'The third floor up: a merchant city under a lantern dome that cycles twice in a Concourse day, so its nights are '
    'short and it never closes. Spice houses, salons, rooms by the week, fences under the Copper Steps, and a Stair '
    'gate one woman owns. BABEL parked its best vendors here; in the tower, everything and everyone has a price.',
    'Floor Three', ['the Bazaar', 'the Gilded Bazaar'], LAT + 0.05, LON, {'walk': 4.5},
    bazaar_hoods, bazaar_places, bazaar_careers, bazaar_employers,
    [{'id': 'the-trade', 'name': 'The trade', 'neighborhoods': ['the-lantern-dome', 'the-spice-rows'],
      'sectors': ['salon', 'merchant', 'craft'], 'summary': 'Money on the Bazaar is made selling what people want, and '
      'people.', 'source': SRC}],
    [{'id': 'on-foot', 'name': 'On foot', 'kind': 'walk', 'summary': 'The dome to the Copper Steps is a quarter hour.',
      'source': SRC},
     {'id': 'chairmen', 'name': 'Chairmen', 'kind': 'carriage', 'summary': 'Sedan chairs for those who pay not to walk.',
      'source': SRC}],
    {'summary': 'Under the lantern dome: warm, fragrant, never dark for long. The dome brightens and dims twice in a '
     'Concourse day.', 'months': months([76] * 12, [64] * 12, [1] * 12, ['Always open.'] * 12), 'source': SRC},
    [],
    [color('everything-has-a-price', 'Everything here has a price', 'saying', 'What Sabeen says, and the floor says '
           'after her.', ['the-lantern-room']),
     color('down-is-free', 'Down is free', 'saying', 'Two Talents up, down free at the gate, because nobody comes back '
           'to pay.', ['the-stair-gate']),
     color('two-sunsets', 'Two sunsets', 'custom', 'The Bazaar sees two dome-darks for every Concourse night, so a week '
           'here is half a week anywhere else.', ['the-lantern-room']),
     color('the-third', 'A third to the house', 'custom', 'The Lantern Room\'s cut, and the Bazaar\'s idea of fair.',
           ['the-lantern-room']),
     color('copper-chit', 'A copper chit', 'rumor', 'A chit stamped with a scale is Sabeen\'s favor. Keep one long '
           'enough and it becomes her debt.', ['the-lantern-room', 'the-fence-rows']),
     color('selling-the-turning', 'Selling the Turning', 'saying', 'Everybody\'s selling the Turning this week: any '
           'rumor about the new skin goes for good money under the Steps.', ['the-fence-rows'])],
    BAZAAR_NAMES,
    [price('day-wage', 'A wharf hand\'s day wage', 4, 6, 'day'), price('room-week', 'A week at the Copper Scale', 50, 70, 'week'), price('sword', 'A proper graded sword (E)', 50,
                                                                            70),
     price('charm-ring', 'A C-grade contraceptive charm ring', 15, 25), price('hush-bead', 'A hush-bead', 30, 60),
     price('toll-up', 'The Stair gate, going up', 2, 2), price('toll-down', 'The Stair gate, going down', 0, 0),
     price('private-booking', 'A private room at the Lantern Room', 150, 200, 'booking'),
     price('night-cage', 'Two seats on the night cage', 100, 200, 'everything'),
     price('map', 'A floor map from Old Wick', 5, 40), price('spice-meal', 'A spiced meal (it tastes)', 6, 10)],
    [notable('sabeen-oro', 'Sabeen Oro', 'Sabeen', 'she/her', 52, 'the-lantern-room', 'room-broker and salon keeper',
             'Keeps the Lantern Room and prices people the way the Bazaar prices everything. Calls everyone darling. '
             'Nobody will say whether she is Lilim.', 'to own whatever is most valuable on the Stair this week'),
     notable('merrow', 'Merrow', 'Merrow', 'she/her', 33, 'the-lantern-room', 'runner', 'Sabeen\'s runner, a sharp-faced '
             'climber from Salford in a brown coat with a copper scales pin. Owes the house more than she earns.',
             'out from under Sabeen', staff=False),
     notable('okonkwo-vale', 'Okonkwo Vale', 'Okonkwo', 'he/him', 56, 'the-spice-exchange', 'spice factor', 'A courteous, '
             'married Rank C factor who smells of clove and asks Sabeen for the new ones.', 'the new ones',
             staff=False),
     notable('pell-the-wire', 'Pell the Wire', 'Pell', 'they/them', 38, 'the-fence-rows', 'fence', 'A light-marked '
             'rat-line Therian who buys anything and sells everything, rumors first.', 'the best rumor on the floor',
             kind='therian'),
     notable('old-wick', 'Old Wick', 'Wick', 'they/them', 71, 'wicks-paper', 'paper seller', 'One-eyed, sells maps and '
             'paper, does not haggle with dogs.', 'a good blade'),
     notable('nell', 'Nell', 'Nell', 'she/her', 22, 'the-lantern-room', 'salon girl', 'Up from the Varrow cage trade, '
             'quick with gossip.', 'never to go back down', staff=False),
     notable('the-toll-keeper', 'the toll-keeper', 'the toll-keeper', 'they/them', 45, 'the-stair-gate', 'gate keeper',
             'Pell\'s cousin, in the iron toll booth behind the Copper Steps.', 'two Talents from everyone going up'),
     notable('the-night-foreman', 'the night foreman', 'the foreman', 'they/them', 50, 'the-freight-wharf', 'smugglers\' '
             'foreman', 'Runs the night cage down the chains and can smell copper on a passenger.',
             'the chains open and Sabeen out of them')],
)


# The other floors: the places on the travel map between towns ------------------------------------

floor_hoods = [
    hood(id, name, summary, vibe, LAT + offset, LON, 'low', None, ['none'], 'low', ['on-foot'])
    for id, name, summary, vibe, offset in [
        ('the-stair', 'the Stair', 'The shaft and its spiral stair between floors.', ['stair', 'shaft'], 0.03),
        ('varrow-floor', 'Varrow', 'Varrow, beyond Hollin\'s valley.', ['hills'], 0.02),
        ('the-marches', 'the Drowned Marches', 'The fen floor, two up.', ['fen', 'fog'], 0.04),
        ('the-high-floors', 'the high floors', 'The floors above the Bazaar.', ['unknown'], 0.07),
        ('the-low-floors', 'the low floors', 'The floors below the Concourse.', ['dark'], -0.02),
    ]]

floor_places = [
    place('the-reach', 'the Reach', 'trail', 'varrow-floor', 'Brown hills past the Reachwall with beacon cairns on the '
          'ridges, Long Cairn among them, and the giants\' fires.', ['hills', 'giants', 'beacons'], 'free', 'outdoor',
          ['solo'], EVERY, spots=['Long Cairn', 'the giants\' fire', 'the near ridge']),
    place('the-marches-landing', 'the Marches landing', 'landmark', 'the-marches', 'Wet stone, reed thatch and fog where '
          'the Stair opens onto the Drowned Marches, and a crier posting the notices that come down the chain.',
          ['landing', 'fog', 'notices'], 'free', 'outdoor', ['solo'], EVERY,
          spots=['the crier\'s board', 'the boat stage']),
    place('the-stilt-villages', 'the stilt villages', 'landmark', 'the-marches', 'Black plank causeways on stilts over '
          'brown water, lanterns on posts, reed beds higher than a man. Reed and nets for coin.',
          ['villages', 'causeways', 'reed'], '$', 'outdoor', ['solo'], EVERY,
          spots=['the causeway lanterns', 'the reed beds', 'the net sheds']),
    place('the-foundry-landing', 'the Foundry landing', 'landmark', 'the-high-floors', 'The last whole landing going up: '
          'the gate into the Foundry under an arch with chalk on it at knee height, and above it bolt holes where a '
          'whole span of the Stair fell into the shaft. The flight below is rotten.', ['landing', 'broken-span',
          'chalk'], 'free', 'outdoor', ['solo'], EVERY, spots=['the chalk on the arch', 'the broken span',
                                                              'the Foundry gate']),
    place('dry-hollow', 'Dry Hollow', 'landmark', 'the-high-floors', 'A boomtown in the beta, where guns work and spells '
          'misfire.', ['frontier', 'guns'], '$', 'outdoor', ['solo'], EVERY),
    place('hakuro', 'Hakuro', 'landmark', 'the-high-floors', 'A castle town under curfew in the beta.',
          ['curfew', 'castle'], '$', 'outdoor', ['solo'], EVERY),
    place('lumen-stack', 'Lumen Stack', 'landmark', 'the-high-floors', 'A neon arcology in the rain in the beta.',
          ['neon', 'rain'], '$$', 'outdoor', ['solo'], EVERY),
    place('st-agathes', 'St. Agathe\'s', 'landmark', 'the-low-floors', 'A hospital where it is always night. Never go '
          'down to St. Agathe\'s.', ['hospital', 'night', 'horror'], 'free', 'indoor', ['solo'], EVERY,
          spots=['the admissions desk', 'the wards', 'the stairwell']),
    place('the-catacombs', 'the Catacombs', 'landmark', 'the-low-floors', 'Bone galleries under a dead city, where the '
          'Margrave\'s cellar stair comes out.', ['bones', 'galleries'], 'free', 'indoor', ['solo'], EVERY),
    place('the-ashfields', 'the Ashfields', 'landmark', 'the-low-floors', 'A post-war wasteland in the beta, where guns '
          'work.', ['wasteland', 'guns'], 'free', 'outdoor', ['solo'], EVERY),
    place('the-undercroft', 'the Undercroft', 'landmark', 'the-low-floors', 'Dark-magic depths in the beta.',
          ['dark', 'magic'], 'free', 'indoor', ['solo'], EVERY),
]

floors = city(
    'babel-floors', 'the tower',
    'Between towns in the tower: the Stair\'s landings and the floors that are not yet built out as towns, from the '
    'Reach above Varrow\'s wall to the Undercroft four floors down.',
    'the tower', [], LAT + 0.03, LON, {'walk': 4.5},
    floor_hoods, floor_places, [], [], [], [{'id': 'on-foot', 'name': 'On foot', 'kind': 'walk', 'summary': 'Up and '
                                            'down the Stair, about half a day a floor.', 'source': SRC}],
    None, [], [], CONCOURSE_NAMES, [], [],
)
# The floors are the ways between towns, not a town: no street map (dungeon/townmap.py), and nowhere to live.
floors['town_map'] = {'style': 'none'}
floors['home'] = False


def main():
    for data in (concourse, hollin, bazaar, floors):
        (CITIES / f"{data['id']}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n',
                                                   encoding='utf-8')


if __name__ == '__main__':
    main()
