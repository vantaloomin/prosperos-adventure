"""Haven, New York, in the autumn of 2009: the town and campus of Vanta's Havenbrooke world. Run
`python scripts/world/haven.py` to rewrite it."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'dungeon' / 'world' / 'data' / 'cities' / 'haven.json'
SRC = 'curated-2026-10'


def place(id, name, kind, hood, summary, tags, cost, setting, good_for, parts, cuisine='', spots=(), seasons=()):
    return {'id': id, 'name': name, 'kind': kind, 'neighborhood': hood, 'summary': summary, 'tags': list(tags),
            'cost': cost, 'setting': setting, 'good_for': list(good_for), 'day_parts': list(parts),
            'seasons': list(seasons), 'cuisine': cuisine, 'spots': list(spots), 'source': SRC}


ALL_DAY = ('morning', 'afternoon', 'evening')
DAY = ('morning', 'afternoon')
NIGHT = ('evening', 'late')
ALWAYS = ('morning', 'afternoon', 'evening', 'late')
STUDENTS = ('solo', 'friends', 'date')

RENT_LOW = {'studio': [425, 550], 'one_bedroom': [525, 675], 'two_bedroom': [650, 850]}
RENT_MID = {'studio': [525, 650], 'one_bedroom': [625, 800], 'two_bedroom': [775, 1000]}
RENT_HIGH = {'studio': [650, 800], 'one_bedroom': [800, 1050], 'two_bedroom': [1000, 1400]}


def hood(id, name, summary, vibe, lat, lon, tier, rent, housing, walk, transit):
    return {'id': id, 'name': name, 'summary': summary, 'vibe': vibe, 'lat': lat, 'lon': lon, 'rent_tier': tier,
            'rent': rent, 'housing': housing, 'walkability': walk, 'transit': transit, 'source': SRC}


neighborhoods = [
    hood('campus', 'Havenbrooke campus', 'The university on the east bank: teaching halls round the Quad, Lantern '
         'Way running from the gates to Morrowe Commons, the dorms on the ridge and Ironroot Woods to the west. Three '
         'ley lines meet under it.', ['campus', 'students', 'ley-lines', 'walkable'], 42.712, -76.408, 'mid', RENT_MID,
         ['dorm', 'suite'], 'high', ['campus-shuttle', 'on-foot']),
    hood('greek-row', 'Greek Row', 'The north edge of campus and the lane off Lantern Way where the fraternity and '
         'sorority houses stand, each with its own wards, rules and history.', ['greek', 'parties', 'old-houses'],
         42.716, -76.405, 'mid', RENT_MID, ['greek-house'], 'high', ['campus-shuttle', 'on-foot']),
    hood('downtown', 'Downtown Haven', 'The west bank: Main Street, Chapel Street and the central plaza, brick '
         'storefronts from the 1880s, the pub, the diner, the bookshop and the cafe everyone uses as an office.',
         ['downtown', 'walkable', 'historic', 'shops'], 42.708, -76.418, 'mid', RENT_MID,
         ['apartment-over-shop', 'walk-up'], 'high', ['haven-transit', 'campus-shuttle', 'on-foot']),
    hood('mill-district', 'the Mill District', 'The old paper mills south along the river: studios, galleries, '
         'loading docks turned into patios, a tattoo shop and the club in the unmarked warehouse.',
         ['artsy', 'nightlife', 'industrial', 'river'], 42.701, -76.415, 'low', RENT_LOW, ['loft', 'warehouse-studio'],
         'medium', ['haven-transit', 'on-foot']),
    hood('west-haven', 'West Haven', 'Run-down Victorians and Craftsman houses on Elm, Birch and Sycamore, rented to '
         'students in groups of four to eight. Cheap, loud, and the plumbing is a rumor.',
         ['students', 'parties', 'cheap', 'old-houses'], 42.711, -76.426, 'low', RENT_LOW,
         ['shared-house', 'walk-up'], 'medium', ['haven-transit', 'on-foot']),
    hood('chapel-hill', 'Chapel Hill', 'Historic houses climbing the east side between downtown and campus, where '
         'faculty live behind porches and good hedges.', ['quiet', 'historic', 'faculty'], 42.709, -76.410, 'high',
         RENT_HIGH, ['victorian-house', 'carriage-house'], 'medium', ['campus-shuttle', 'on-foot']),
    hood('crane-ridge', 'Crane Ridge', "The wooded northern ridge above West Haven, most of it behind the Crane "
         "family's fence. The road up has one gas station and a tavern that closes early.",
         ['wooded', 'private', 'watched'], 42.722, -76.428, 'high', RENT_HIGH, ['estate', 'cottage'], 'low',
         ['car']),
]

places = [
    # Campus: teaching
    place('aldwright-hall', 'Aldwright Hall', 'landmark', 'campus', 'Esoteric Sciences in the oldest building '
          'on campus: dark brick, cold stone floors, chalk dust and the smell of misfired spells. The third-floor '
          'windows never latch.', ['esoteric-sciences', 'classes', 'old'], 'free', 'indoor', ['solo', 'friends'], DAY,
          spots=['the echoing stairwell', 'Room 312', 'the third-floor windows']),
    place('vespers-hall', 'Vespers Hall', 'landmark', 'campus', 'The ritual complex over the strongest ley '
          'node: candlelit chambers and spell rings cut into black stone that warms underfoot. Booked weeks ahead.',
          ['esoteric-sciences', 'ritual', 'ley-node'], 'free', 'indoor', ['solo', 'friends'], ALL_DAY,
          spots=['the great chamber', 'the second chamber', 'the outer ring']),
    place('old-observatory', 'the Old Observatory', 'landmark', 'campus', 'A stone tower from the founding with an '
          'open roof and locked lower floors. People go up to breathe.', ['quiet', 'views', 'old'], 'free', 'outdoor',
          STUDENTS, ALWAYS, spots=['the roof', 'the worn granite steps']),
    place('kaelen-hall', 'Kaelen Hall', 'landmark', 'campus', 'Interpersonal Dynamics in a converted 1920s '
          'sanatorium: a tall atrium, couches in every hallway, lavender and beeswax, and an ethics room that looks '
          'out on the cemetery.', ['interpersonal-dynamics', 'classes', 'seminars'], 'free', 'indoor',
          ['solo', 'friends'], DAY, spots=['the atrium', 'Room 204', 'the ethics seminar room', 'the third-floor clinic']),
    place('warden-hall', 'Warden Hall', 'landmark', 'campus', 'Military and Tactical Operations: squat '
          'concrete, gun oil from the armory, cameras in the training rooms and classes at seven in the morning.',
          ['mto', 'classes', 'federal', 'watched'], 'free', 'indoor', ['solo'], DAY,
          spots=['the armory desk', 'Training Room B', 'the briefing room']),
    place('thornewall', 'Thornewall', 'landmark', 'campus', 'Mundane Studies in nineties glass and industrial '
          'carpet, under a suppression field that hums. Witches get headaches; humans finally relax.',
          ['mundane-studies', 'classes', 'suppression-field'], 'free', 'indoor', ['solo', 'friends'], DAY,
          spots=['Lecture Hall 1', 'the Ashforth Computing Lab', 'the Oracle office in the basement']),
    place('mirren-studio', 'the Mirren Media Studio', 'landmark', 'campus', 'The communications studio: a '
          'small TV set, two edit bays and the WHAV-FM booth, with a sign that says ON AIR in red.',
          ['media', 'radio', 'classes'], 'free', 'indoor', ['solo', 'friends'], ALWAYS,
          spots=['the WHAV-FM booth', 'the edit bays', 'the green room']),
    place('bellweather-hall', 'Bellweather Hall', 'landmark', 'campus', 'Supernatural Physiology and '
          'Integration: red-brick Georgian with a modern wing, anatomy labs upstairs and a faint smell of '
          'preservative.', ['spi', 'classes', 'labs'], 'free', 'indoor', ['solo', 'friends'], ALL_DAY,
          spots=['the anatomy lab', 'the warded wing', 'the lecture theater']),
    place('farrow-house', 'Farrow House', 'landmark', 'campus', 'The supervised treatment house: a Victorian with a '
          'wraparound porch, walls that swallow sound and a stained-glass owl over the waiting room door.',
          ['spi', 'clinical-hours', 'quiet'], 'free', 'indoor', ['solo'], ALL_DAY,
          spots=['the porch', 'the waiting parlor', 'the quiet rooms']),
    place('chancellor-wynne-library', 'Chancellor Wynne Library', 'library', 'campus', 'The main library, whose '
          'shelves rearrange overnight to the course schedule. The basement archives need a sponsor and a blood '
          'signature.', ['study', 'quiet', 'archives'], 'free', 'indoor', ['solo', 'friends'], ALWAYS,
          spots=['the reading room', 'the basement archives', 'the carrels on four']),
    # Campus: facilities
    place('verdant-grove', 'the Verdant Grove', 'garden', 'campus', 'Four linked ritual greenhouses, warm and humid all '
          'year, and an outdoor garden for plants too charged to keep inside. The Enchanters\' Guild workshop is at '
          'the back.', ['plants', 'dryads', 'work'], 'free', 'mixed', ['solo', 'friends'], ALL_DAY,
          spots=['the fern house', 'the enchanters\' workshop', 'the outdoor beds']),
    place('stitch-hall', 'Stitch Hall Ateliers', 'workshop', 'campus', 'Fashion studios: fabric to the ceiling, rows '
          'of industrial machines and long mirrors, private ateliers upstairs.', ['fashion', 'design', 'work'], 'free',
          'indoor', ['solo', 'friends'], ALWAYS, spots=['the shared studio', 'the upstairs ateliers']),
    place('evermere', 'Evermere Health Pavilion', 'landmark', 'campus', 'Six floors of human and supernatural '
          'medicine that never close: lycan rooms, fae springs in the sub-basement and consent-warded feeding suites.',
          ['health', 'feeding-suites', 'emergency'], '$', 'indoor', ['solo'], ALWAYS,
          spots=['the front desk', 'the third-floor lycan rooms', 'the fourth-floor feeding suites']),
    place('crestfall-arena', 'Crestfall Arena', 'stadium', 'campus', 'The athletic complex, reinforced for lycan '
          'sparring and aerial fae training. The auxiliary studio is empty at four in the morning.',
          ['sport', 'training', 'crows'], 'free', 'indoor', ['solo', 'friends'], ALWAYS,
          spots=['the main floor', 'the auxiliary studio', 'the north practice fields']),
    place('morrowe-commons', 'Morrowe Commons', 'restaurant', 'campus', 'Four floors of lounges, food counters, '
          'music rooms and club space under a ward that keeps aura pressure off humans. The bakery opens at six.',
          ['dining-hall', 'social', 'clubs'], '$', 'indoor', ['solo', 'friends', 'date'], ALWAYS, 'dining hall',
          spots=['the main dining floor', 'the bakery counter', 'the conference wing', 'the music rooms']),
    place('commons-coffee', 'the Commons coffee bar', 'cafe', 'campus', 'The coffee counter on the ground floor of '
          'Morrowe, with a line at 7:55 and tables nobody gives up after 9.', ['coffee', 'study'], '$', 'indoor',
          STUDENTS, ALL_DAY, 'coffee'),
    place('caldwell-fountain', 'Caldwell Fountain Court', 'square', 'campus', 'A plaza round a fountain three degrees '
          'colder than the air, with a faint pull that draws confessions out of tired people.',
          ['outdoors', 'confessions', 'meeting-point'], 'free', 'outdoor', STUDENTS, ALL_DAY,
          spots=['the fountain rim', 'the benches under the lindens']),
    place('ridgewalk-chapel', 'Ridgewalk Chapel', 'temple', 'campus', 'A small white clapboard chapel at the western '
          'edge of campus: twelve pews, always unlocked, one candle that someone keeps lit.', ['quiet', 'chapel'],
          'free', 'indoor', ['solo', 'date'], ALWAYS),
    place('the-quad', 'the Quad and Lantern Way', 'park', 'campus', 'Four acres of green under old oaks, and the '
          'gas-lamp path from the gates to Morrowe that everyone calls the runway.', ['outdoors', 'people-watching'],
          'free', 'outdoor', STUDENTS, ALWAYS, spots=['Lantern Way', 'the big oak', 'the front gates']),
    place('ironroot-woods', 'Ironroot Woods', 'trail', 'campus', 'A mile of old-growth forest on the west edge of '
          'campus. The trails are kept by day; after dusk the lycans run and the witches gather.',
          ['woods', 'night', 'lycans'], 'free', 'outdoor', ['solo', 'friends', 'date'], ALWAYS,
          spots=['the creek', 'the training clearing', 'the unmarked paths']),
    # Off the trails (dungeon/hexes.py): the hex crawl's stand-in for wherever a walk past Ironroot or the Riverwalk ends.
    place('the-back-woods', 'the back woods', 'trail', 'campus', 'Off the kept trails, in the woods and hills that run '
          'west and south of Haven: second-growth forest, old stone walls, hunting stands and no signal.',
          ['woods', 'wild', 'remote'], 'free', 'outdoor', ['solo', 'friends'], ALWAYS,
          spots=['a stone wall in the trees', 'a deer track', 'a rise with a view of the lake']),
    place('old-cemetery', 'the Old Cemetery', 'landmark', 'campus', 'Granite stones behind an overgrown iron fence, '
          'older than the university, where some headstones are not where they were last week.',
          ['quiet', 'eerie', 'couples'], 'free', 'outdoor', ['solo', 'date'], ALWAYS),
    # Campus: housing
    place('nexus-housing', 'Nexus Housing', 'landmark', 'campus', 'Upperclass suites with kitchens over a secondary '
          'ley node: magic works better, sleep is worse. The third floor is three units round a shared common room.',
          ['home', 'ley-node', 'suites'], 'free', 'indoor', ['solo', 'friends', 'date'], ALWAYS,
          spots=['the third-floor common room', 'Unit A', 'Unit B', 'Unit C', 'the lobby', 'the stairwell']),
    place('north-dorm-ridge', 'North Dorm Ridge', 'landmark', 'campus', 'Three brutalist towers with reinforced doors '
          'and air tuned for demon heat and vampire chill. Humans are told to take the stairs.',
          ['dorms', 'supernatural-majority'], 'free', 'indoor', ['solo', 'friends'], ALWAYS),
    place('east-quad', 'the East Residential Quad', 'landmark', 'campus', 'Three brick dorms round a courtyard used '
          'for spell tests, frisbee and breakups, in that order through the day.', ['dorms', 'freshmen'], 'free',
          'mixed', ['solo', 'friends'], ALWAYS),
    # Greek Row
    place('alpha-gamma-house', 'Alpha Gamma House', 'landmark', 'greek-row', 'A gray three-story Victorian with black '
          'trim, a basement nobody outside the pack sees on a full moon, and couches that make human guests feel '
          'strange.', ['lycans', 'fraternity', 'parties'], 'free', 'indoor', ['friends'], ALWAYS,
          spots=['the common room', 'the porch', 'the basement door']),
    place('hex-house', 'Sigma Theta Hex House', 'landmark', 'greek-row', 'An ivy-covered federal mansion with black '
          'shutters, sage and iron in the air, and everything above the grand staircase for sisters only.',
          ['witches', 'sorority', 'wards'], 'free', 'indoor', ['friends'], ALWAYS,
          spots=['the front parlor', 'the grand staircase', 'the ritual room']),
    place('nox-house', 'Phi Sigma Nox House', 'landmark', 'greek-row', 'The vampire-led house: a brick Georgian with '
          'heavy curtains, a wine cellar and parties that start after the dining halls close.',
          ['vampires', 'fraternity', 'old-money'], 'free', 'indoor', ['friends'], NIGHT),
    place('ember-house', 'Omicron Phi Ember House', 'landmark', 'greek-row', 'The demonkin house: warm, loud, '
          'scented, and very careful about who it lets upstairs.', ['demonkin', 'fraternity', 'parties'], 'free',
          'indoor', ['friends'], NIGHT),
    place('row-snack-bar', 'the Row snack bar', 'cafe', 'greek-row', 'A sandwich window at the end of Greek Row that '
          'stays open until two on weekends and sells more coffee than food.', ['late-night', 'cheap'], '$', 'mixed',
          STUDENTS, ALWAYS, 'sandwiches'),
    # Downtown
    place('stag-and-thistle', 'the Stag & Thistle', 'bar', 'downtown', 'The pub on a Main Street corner: forty taps, '
          'scotch eggs and shepherd\'s pie, faculty in the back booths and students in the front. The owner has never '
          'been wrong about an ID.', ['pub', 'beer', 'faculty'], '$$', 'indoor', STUDENTS, NIGHT, 'pub food',
          spots=['the back booths', 'the front windows', 'the bar']),
    place('midnight-gas', 'Midnight Gas', 'restaurant', 'downtown', 'The 24-hour diner on North Main: neon, cracked '
          'vinyl booths, stewed coffee and pancakes at three in the morning.', ['diner', 'late-night', 'cheap'], '$',
          'indoor', STUDENTS, ALWAYS, 'diner', spots=['the corner booth', 'the counter']),
    place('pale-press', 'Pale Press Coffee', 'cafe', 'downtown', 'A cafe in an old print shop on Prescott Alley: '
          'brick, big windows and espresso. No glamours, no charms, no spellwork, by house rule.',
          ['coffee', 'magic-neutral', 'study'], '$', 'indoor', STUDENTS, ALL_DAY, 'coffee',
          spots=['the window bar', 'the back room with the old press']),
    place('drothes-bookery', "Drothe's Bookery", 'shopping', 'downtown', 'A two-story used bookshop on Bell Street: '
          'five-dollar paperbacks downstairs, occult texts upstairs at whatever price Drothe names.',
          ['books', 'occult', 'browsing'], '$', 'indoor', ['solo', 'date'], ALL_DAY,
          spots=['the narrow stairs', 'the occult room', 'behind the register']),
    place('harpers', "Harper's", 'restaurant', 'downtown', 'The good restaurant at Main and Chapel: white cloths, '
          'hurricane candles, a long wine list and the best bread in the Finger Lakes.', ['fine-dining', 'dates'],
          '$$$', 'indoor', ['date', 'family'], ['evening'], 'new american'),
    place('saturday-market', 'the Haven Saturday Market', 'market', 'downtown', 'The farmers market in the central '
          'plaza, moved into the old meeting hall for winter: produce, cheese, honey and dryad-made preserves.',
          ['market', 'saturdays', 'local'], '$', 'mixed', ['solo', 'friends', 'family'], ['morning'],
          spots=['the dryad co-op stall', 'the Saturday bakery', 'the cheese table']),
    place('main-street-pizza', 'Bianchi\'s Pizza', 'restaurant', 'downtown', 'A slice counter on Main with a '
          'two-slices-and-a-soda special and a jukebox that only takes quarters.', ['pizza', 'cheap'], '$', 'indoor',
          STUDENTS, ('afternoon', 'evening', 'late'), 'pizza'),
    place('haven-cinema', 'the Strand', 'venue', 'downtown', 'A single-screen 1920s movie house showing one new '
          'release and a midnight cult film on Fridays.', ['movies', 'dates'], '$', 'indoor', STUDENTS, NIGHT),
    place('haven-bus-stop', 'the Main Street bus shelter', 'square', 'downtown', 'Where the Haven Transit buses '
          'and the twice-daily shuttle to Ithaca stop, opposite the bank clock.', ['transit'], 'free', 'outdoor',
          ['solo'], ALWAYS),
    place('pharmacy', 'Kessel Drugs', 'shopping', 'downtown', 'The pharmacy and general store on Chapel Street: '
          'prescriptions, cold medicine, condoms, phone cards and a photo counter.', ['pharmacy', 'errands'], '$',
          'indoor', ['solo'], ALL_DAY),
    # Mill District
    place('velvet-spire', 'the Velvet Spire', 'nightlife', 'mill-district', 'The supernatural-friendly club in an '
          'unmarked three-story warehouse: DJs below, private booths in the middle, and a members-only top floor.',
          ['club', 'dancing', 'feeding'], '$$', 'indoor', ['friends', 'date'], ['late'],
          spots=['the main floor', 'the middle-floor booths', 'the stairs to the top floor']),
    place('arrow-and-ink', 'Arrow & Ink', 'shopping', 'mill-district', 'A tattoo and piercing shop on Foundry Lane, '
          'lamp-lit, with enchanted ink for clients the owner trusts.', ['tattoos', 'enchanted-ink'], '$$', 'indoor',
          ['solo', 'friends'], ('afternoon', 'evening')),
    place('ironworks-collective', 'the Ironworks Collective', 'workshop', 'mill-district', 'Eighteen artisan studios '
          'on Old Foundry Row, renting bench space with charm infusion included.', ['art', 'studios', 'charms'],
          '$', 'indoor', ['solo', 'friends'], ALL_DAY),
    place('foundry-taproom', 'the Foundry Taproom', 'bar', 'mill-district', 'A brewpub in an old loading dock with a '
          'patio over the river and a band most Thursdays.', ['beer', 'live-music', 'river'], '$$', 'mixed',
          STUDENTS, NIGHT, 'bar food'),
    # West Haven
    place('elm-street-houses', 'the Elm Street houses', 'landmark', 'west-haven', 'Student rentals on Elm with sagging '
          'porches, red cups on the lawn and the party everyone talks about the next morning.',
          ['parties', 'students', 'houses'], 'free', 'mixed', ['friends'], NIGHT),
    place('birch-street', 'Birch Street', 'landmark', 'west-haven', 'Where Delta Nu Iris and Delta Omicron Theta keep '
          'their houses, a block apart and not speaking.', ['sorority', 'houses'], 'free', 'outdoor', ['friends'],
          ALWAYS),
    place('west-haven-deli', 'Sal\'s Corner Deli', 'cafe', 'west-haven', 'A corner store and deli on Sycamore with '
          'hero sandwiches, cheap beer and a cashier who has seen everything.', ['deli', 'beer', 'cheap'], '$',
          'indoor', ['solo', 'friends'], ALWAYS, 'deli'),
    place('laundromat', 'the Sycamore Laundromat', 'shopping', 'west-haven', 'Coin washers, a broken change machine '
          'and the best place in Haven to overhear a breakup.', ['errands'], '$', 'indoor', ['solo'], ALL_DAY),
    # Chapel Hill
    place('chapel-hill-bakery', 'Linden Street Bakery', 'cafe', 'chapel-hill', 'A faculty-heavy bakery with scones, '
          'quiet tables and a bulletin board of house-sitting jobs.', ['bakery', 'quiet', 'faculty'], '$', 'indoor',
          ['solo', 'date', 'family'], DAY, 'bakery'),
    place('riverwalk', 'the Riverwalk', 'trail', 'chapel-hill', 'Three miles of path along the east bank from '
          'downtown past the mills into the hills, with benches, lamps and small docks. Nobody clears the ice.',
          ['river', 'walks', 'running'], 'free', 'outdoor', ['solo', 'date', 'friends'], ALWAYS,
          spots=['the footbridge', 'the small docks', 'the bench with the view of the ridge']),
    # Crane Ridge
    place('crane-hill', 'Crane Hill', 'landmark', 'crane-ridge', "The Crane family's fenced and gated estate on the "
          'ridge, home to a line of vampires since 1819. Visitors are expected or turned away.',
          ['vampires', 'estate', 'private'], 'free', 'mixed', ['solo'], NIGHT,
          spots=['the gatehouse', "the steward's office", 'the long drive']),
    place('ridge-tavern', 'the Ridge Road Tavern', 'tavern', 'crane-ridge', 'A low roadhouse at the foot of the '
          "ridge where the Cranes' staff drink and students do not, mostly.", ['locals', 'quiet'], '$', 'indoor',
          ['solo', 'friends'], ('afternoon', 'evening'), 'bar food'),
]

careers = [
    ('enchanter', 'Licensed enchanter', 'craft', 'flexible', 'freelance', '$$', 'Making and selling charms that carry '
     'a DED compliance mark, from a stall, a studio or a dorm room.', ['charms', 'licensing', 'customers'], 22),
    ('campus-security', 'Campus security officer', 'security', 'rotating', 'rota', '$$', "Patrolling Havenbrooke under "
     "MTO-trained supervisors and writing up whatever the Dean's office will want in the morning.",
     ['patrols', 'incident reports', 'students'], 21),
    ('ward-technician', 'Ward technician', 'esoteric', 'shift-day', 'staff', '$$', 'Testing, patching and certifying '
     'building wards for the university and the town.', ['wards', 'inspections', 'old buildings'], 21),
    ('dining-hall-worker', 'Dining hall worker', 'food', 'early', 'rota', '$', 'Line, dish pit and bakery shifts at '
     'Morrowe Commons, mostly students on work-study.', ['work-study', 'early mornings', 'regulars'], 18),
]
careers = [{'id': c[0], 'name': c[1], 'sector': c[2], 'schedule': c[3], 'employment': c[4], 'pay': c[5],
            'summary': c[6], 'themes': c[7], 'eras': ['modern'], 'ages': [c[8], 70]} for c in careers]

employers = [
    ('havenbrooke-university', 'Havenbrooke University', 'education', 'campus', 'large', 'The university and the '
     "town's largest employer: faculty, clinics, dining, grounds and security.",
     ['professor', 'graduate-student', 'campus-security', 'dining-hall-worker', 'ward-technician', 'social-worker']),
    ('evermere-health', 'Evermere Health Pavilion', 'health', 'campus', 'medium', 'The campus hospital, open all '
     'hours.', ['registered-nurse', 'night-nurse', 'physician-resident', 'pharmacist']),
    ('enchanters-guild', "the Student Enchanters' Guild", 'craft', 'campus', 'small', 'The guild workshop at the '
     'Verdant Grove, which takes student commissions.', ['enchanter']),
    ('midnight-gas-diner', 'Midnight Gas', 'food', 'downtown', 'small', 'The all-night diner.',
     ['line-cook', 'server']),
    ('stag-and-thistle-pub', 'the Stag & Thistle', 'food', 'downtown', 'small', 'The pub on Main.',
     ['bartender', 'server', 'line-cook']),
    ('pale-press-cafe', 'Pale Press Coffee', 'food', 'downtown', 'small', 'The magic-neutral cafe.', ['barista']),
    ('velvet-spire-club', 'the Velvet Spire', 'nightlife', 'mill-district', 'small', 'The club in the warehouse.',
     ['bartender', 'performer']),
    ('crane-estate', 'the Crane estate', 'household', 'crane-ridge', 'small', 'Groundskeepers, drivers and house '
     'staff for the family on the ridge, paid well and told little.', ['event-planner', 'accountant']),
    ('haven-oracle', 'the Oracle', 'media', 'campus', 'small', 'The student paper, in the Thornewall basement.',
     ['journalist', 'graphic-designer']),
]
employers = [{'id': e[0], 'name': e[1], 'sector': e[2], 'neighborhood': e[3], 'size': e[4], 'summary': e[5],
              'careers': e[6], 'source': SRC} for e in employers]

career_hubs = [
    {'id': 'the-university', 'name': 'The university', 'neighborhoods': ['campus', 'greek-row'],
     'sectors': ['education', 'health', 'craft', 'security', 'esoteric', 'media'], 'summary': 'Most paychecks in Haven '
     'come from Havenbrooke, one way or another.', 'source': SRC},
    {'id': 'main-and-mills', 'name': 'Main Street and the mills', 'neighborhoods': ['downtown', 'mill-district'],
     'sectors': ['food', 'retail', 'nightlife', 'craft'], 'summary': 'Bars, cafes, shops and studios, mostly staffed by '
     'students.', 'source': SRC},
]

months = [
    (30, 15, 16, 'Lake-effect snow and a gray sky for weeks.'), (32, 16, 14, 'The coldest stretch; the Riverwalk '
    'is ice.'), (41, 24, 14, 'Mud and slush; spring term drags.'), (54, 35, 13, 'Rain and the first green.'),
    (66, 45, 13, 'Finals, then the town empties.'), (75, 54, 12, 'Warm and wet; the lakes fill with summer people.'),
    (80, 59, 11, 'The warmest month, thunderstorms most afternoons.'), (78, 57, 11, 'Move-in heat at the end of the '
    'month.'), (70, 50, 11, 'Clear and cool; the term settles in.'), (58, 40, 12, 'Peak color in the first two weeks, '
    'then wind and rain.'), (46, 32, 14, 'Dark at five; first snow.'), (35, 22, 16, 'Snow on the ground for finals.')]

names = {'mix': {'anglo': 6, 'german': 1, 'irish': 1.5, 'italian': 1, 'east-asian': 0.6, 'hispanic': 0.6, 'black-american': 0.8,
                 'jewish': 0.4, 'south-asian': 0.3, 'slavic': 0.4},
         'year': 2009}

notables = [
    {'id': 'delia-okonkwo', 'name': 'Delia Okonkwo', 'given': 'Delia', 'pronouns': 'she/her', 'age': 49,
     'place': 'pale-press', 'role': 'cafe owner', 'staff': True, 'about': 'A witch from an old Boston lineage who '
     'opened Pale Press so nobody would have to perform in it. She asks you to leave once, politely.',
     'wants': 'to keep one room in Haven where nobody uses anything on anybody', 'source': SRC},
    {'id': 'bex-kavanagh', 'name': 'Betsari Kavanagh', 'given': 'Bex', 'pronouns': 'she/her', 'age': 40,
     'place': 'arrow-and-ink', 'role': 'tattooist', 'staff': True, 'about': 'An Appalachian-trained witch who tattoos '
     'by day and does enchanted ink for people she trusts. Funny, blunt and impossible to rush.',
     'wants': 'one client this month who actually knows what they are asking for', 'source': SRC},
    {'id': 'drothe', 'name': 'Drothe', 'given': 'Drothe', 'pronouns': 'they/them', 'age': 80,
     'place': 'drothes-bookery', 'role': 'bookseller', 'staff': True, 'about': 'The keeper of the bookshop on Bell '
     'Street, a witch nobody can classify. Prices change with their mood and with who is asking.',
     'wants': 'to see which students come upstairs this term, and for what', 'source': SRC},
    {'id': 'gideon-vale', 'name': 'Gideon Vale', 'given': 'Mr. Vale', 'pronouns': 'he/him', 'age': 62,
     'place': 'crane-hill', 'role': 'steward to the Crane family', 'staff': True, 'about': 'A mundane human who has '
     'run the Crane household for thirty years and is the only person Haven PD speaks to about the ridge.',
     'wants': 'to keep the family out of the papers through one more election', 'source': SRC},
    {'id': 'mireille-thorne-ashford', 'name': 'Mireille Thorne-Ashford', 'given': 'Professor Thorne-Ashford',
     'pronouns': 'she/her', 'age': 55, 'place': 'aldwright-hall', 'role': 'incantation professor',
     'staff': True, 'about': 'Senior incantation faculty and advisor to Sigma Theta Hex. Exacting, unhurried, and '
     'more interested in why a working failed than in the student who failed it.',
     'wants': 'one student this year who can hold a working under real pressure', 'source': SRC},
    {'id': 'kasper-innes', 'name': 'Kasper Innes', 'given': 'Dr. Innes', 'pronouns': 'he/him', 'age': 70,
     'kind': 'fae', 'place': 'kaelen-hall', 'role': 'ethics professor', 'staff': True, 'about': 'Teaches IPD 340, the '
     'consent course every SPI and ES student has to pass. Gentle in the lecture hall and merciless in office hours.',
     'wants': 'to make someone in the back row say what they actually think', 'source': SRC},
    {'id': 'marcus-halbrook', 'name': 'Marcus Halbrook', 'given': 'Colonel Halbrook', 'pronouns': 'he/him', 'age': 58,
     'place': 'warden-hall', 'role': 'head of MTO', 'staff': True, 'about': 'A retired colonel, bitten in the line of '
     'duty, who runs MTO like a unit and starts every class at seven sharp.',
     'wants': 'a cohort that passes the federal review without anyone getting hurt', 'source': SRC},
    {'id': 'iolana-whitestone', 'name': 'Iolana Whitestone', 'given': 'Professor Whitestone', 'pronouns': 'she/her',
     'age': 68, 'place': 'bellweather-hall', 'role': 'clinical care professor', 'staff': True, 'about': 'A retired '
     'succubus diplomat who teaches SPI 220 and runs the clinical placements at Farrow House.',
     'wants': 'her students to stop being embarrassed by the word hunger', 'source': SRC},
    {'id': 'samuel-park', 'name': 'Samuel Park', 'given': 'Professor Park', 'pronouns': 'he/him', 'age': 55,
     'place': 'thornewall', 'role': 'computer science professor', 'staff': True, 'about': 'Heads computer science, '
     'runs the Ashforth lab and has opinions about everyone\'s variable names.',
     'wants': 'a student who can make the lab servers stop crashing during the full moon', 'source': SRC},
    {'id': 'imogen-shaw', 'name': 'Imogen Shaw', 'given': 'Professor Shaw', 'pronouns': 'she/her', 'age': 50,
     'place': 'mirren-studio', 'role': 'communications professor', 'staff': True, 'about': 'Teaches media and '
     'communications, ran a newsroom for fifteen years and still edits everything in red pen.',
     'wants': 'one honest story out of her seminar this term', 'source': SRC},
]

CITY = {
    'schema_version': 1, 'id': 'haven', 'name': 'Haven', 'setting': 'original', 'era': 'modern',
    'category': 'fictional',
    'basis': "Vanta's own world of Havenbrooke: modern fantasy in the real autumn of 2009, with supernatural peoples "
             'recognized under federal law since 1867. The town, the university and their people are written for '
             "Prospero's Dungeon.",
    'region': 'New York', 'country': 'US', 'timezone': 'America/New_York',
    'aliases': ['Haven, New York', 'Havenbrooke'],
    'summary': 'A Finger Lakes mill town of about 35,000 on the Haven River, and Havenbrooke University on the east '
               'bank, where five thousand students of every people study over three ley lines. Autumn 2009: '
               'recession outside the gates, flip phones inside them.',
    'lat': 42.71, 'lon': -76.415,
    'intensity': {'preset': 'unflinching',
                  'voice': 'intimate, wry and adult: a campus drama where comedy and hurt share a page, every '
                           'institution claims someone, and sex is written as part of who people are',
                  'drama': 'uneasy'},
    'currency': {'code': 'USD', 'symbol': '$', 'name': 'US dollars'}, 'rent_period': 'month',
    'speeds': {'walk': 4.5, 'car': 40, 'bus': 22},
    'sources': {SRC: {'kind': 'curated', 'title': "Haven written for Prospero's Dungeon from Vanta's Havenbrooke "
                      'material', 'license': "Vanta's own setting; all rights reserved", 'retrieved': '2026-10-22',
                      'note': 'Drawn from the Havenbrooke world and university documents. Prices are typical for '
                              'upstate New York in 2009. Every business and person named is fictional.'}},
    'neighborhoods': neighborhoods, 'places': places,
    'transit': [
        {'id': 'on-foot', 'name': 'On foot', 'kind': 'walk', 'summary': 'Campus is fifteen minutes end to end; '
         'downtown is a ten-minute walk over the footbridge.', 'source': SRC},
        {'id': 'campus-shuttle', 'name': 'The Havenbrooke shuttle', 'kind': 'bus', 'summary': 'A free loop from the '
         'gates to downtown every twenty minutes until midnight, and twice a day to Ithaca.', 'source': SRC},
        {'id': 'haven-transit', 'name': 'Haven Transit', 'kind': 'bus', 'summary': 'Two city bus lines, a dollar a '
         'ride, running until nine.', 'source': SRC},
        {'id': 'car', 'name': 'A car', 'kind': 'car', 'summary': 'Most students do not have one, and the ones who do '
         'are very popular on Friday.', 'source': SRC}],
    'careers': careers, 'employers': employers, 'career_hubs': career_hubs,
    'climate': {'summary': 'Upstate New York: long gray winters with lake-effect snow, a muddy spring, warm wet '
                           'summers and a short bright fall.',
                'months': [{'high_f': h, 'low_f': lo, 'rain_days': r, 'note': n} for h, lo, r, n in months],
                'source': SRC},
    'annual_events': [
        {'id': 'move-in', 'name': 'Move-in week', 'months': [8], 'neighborhood': 'campus', 'summary': 'Parents, '
         'minivans and housing letters; the dorms fill and the wards get their annual check.', 'source': SRC},
        {'id': 'autumn-equinox', 'name': 'The autumn equinox rites', 'months': [9], 'neighborhood': 'campus',
         'summary': 'The covens book every chamber in Vespers Hall; Sigma Theta Hex holds its rite in the largest.',
         'source': SRC},
        {'id': 'harvest-howl', 'name': 'The Harvest Howl', 'months': [10], 'neighborhood': 'campus',
         'summary': "Alpha Gamma's Halloween bonfire on the north practice fields, the biggest party of the fall.",
         'source': SRC},
        {'id': 'charm-exhibit', 'name': 'The winter charm exhibit', 'months': [12], 'neighborhood': 'campus',
         'summary': "The Enchanters' Guild shows the term's work at the Verdant Grove the week before finals.",
         'source': SRC},
        {'id': 'spring-show', 'name': 'The Creative Collective spring show', 'months': [4], 'neighborhood':
         'mill-district', 'summary': 'Student art, fashion and music in the Ironworks studios over one weekend.',
         'source': SRC},
        {'id': 'nsac-bracket', 'name': 'The NSAC sparring bracket', 'months': [2, 3], 'neighborhood': 'campus',
         'summary': 'Intercollegiate supernatural sparring at Crestfall Arena; the Crows have not won since 1998.',
         'source': SRC}],
    'local_color': [
        {'id': 'the-runway', 'name': 'The runway', 'kind': 'saying', 'summary': 'Lantern Way, because everyone sees '
         'everyone on it sooner or later.', 'places': ['the-quad'], 'source': SRC},
        {'id': 'fountain-confessions', 'name': 'Fountain confessions', 'kind': 'legend', 'summary': 'Most breakups '
         'and hookups on campus are said to start at Caldwell Fountain, which pulls the truth out of tired people.',
         'places': ['caldwell-fountain'], 'source': SRC},
        {'id': 'moving-headstones', 'name': 'The moving headstones', 'kind': 'legend', 'summary': 'Some stones in the '
         'Old Cemetery are a few feet from where they were last week, and a physics major once measured it.',
         'places': ['old-cemetery'], 'source': SRC},
        {'id': 'nexus-dreams', 'name': 'Nexus dreams', 'kind': 'rumor', 'summary': 'Everyone in Nexus Housing dreams '
         'harder and sleeps worse, and the housing office does not put that in the brochure.',
         'places': ['nexus-housing'], 'source': SRC},
        {'id': 'three-am-pancakes', 'name': 'Three a.m. pancakes', 'kind': 'dish', 'summary': 'A short stack and '
         'stewed coffee at Midnight Gas after anything at all.', 'places': ['midnight-gas'], 'source': SRC},
        {'id': 'crows', 'name': 'The Crestfall Crows', 'kind': 'team', 'summary': 'The university teams, loved '
         'loudly and expected to lose.', 'places': ['crestfall-arena'], 'source': SRC},
        {'id': 'mundie', 'name': '"Mundie"', 'kind': 'saying', 'summary': 'What some supernatural students call a '
         'non-magical human. Said to their face, it starts fights.', 'source': SRC},
        {'id': 'the-candle', 'name': "The chapel candle", 'kind': 'legend', 'summary': 'The candle in Ridgewalk Chapel '
         'has been burning since before anyone on staff was hired, and nobody has ever seen it lit.',
         'places': ['ridgewalk-chapel'], 'source': SRC}],
    'names': names,
    'prices': [
        {'id': 'coffee', 'item': 'Coffee', 'low': 1.5, 'high': 3.5, 'per': 'a cup', 'source': SRC},
        {'id': 'pint', 'item': 'Pint of beer', 'low': 3, 'high': 5, 'per': 'a pint', 'source': SRC},
        {'id': 'diner-meal', 'item': 'Diner meal', 'low': 6, 'high': 10, 'per': '', 'source': SRC},
        {'id': 'pizza-slice', 'item': 'Slice of pizza', 'low': 1.75, 'high': 2.5, 'per': '', 'source': SRC},
        {'id': 'dinner-out', 'item': "Dinner for two at Harper's", 'low': 70, 'high': 120, 'per': '', 'source': SRC},
        {'id': 'club-cover', 'item': 'Cover at the Velvet Spire', 'low': 10, 'high': 25, 'per': 'a night',
         'source': SRC},
        {'id': 'textbook', 'item': 'Textbook', 'low': 80, 'high': 150, 'per': '', 'source': SRC},
        {'id': 'paperback', 'item': "Paperback at Drothe's", 'low': 5, 'high': 5, 'per': '', 'source': SRC},
        {'id': 'gas', 'item': 'Gas', 'low': 2.4, 'high': 2.7, 'per': 'a gallon', 'source': SRC},
        {'id': 'bus-nyc', 'item': 'Bus to New York', 'low': 30, 'high': 50, 'per': 'one way', 'source': SRC},
        {'id': 'amtrak', 'item': 'Amtrak from Syracuse to New York', 'low': 50, 'high': 70, 'per': 'one way',
         'source': SRC},
        {'id': 'phone', 'item': 'iPhone 3GS', 'low': 199, 'high': 299, 'per': 'on a two-year contract', 'source': SRC},
        {'id': 'laptop', 'item': 'Laptop', 'low': 300, 'high': 1000, 'per': '', 'source': SRC},
        {'id': 'texts', 'item': 'Unlimited texting', 'low': 15, 'high': 20, 'per': 'a month', 'source': SRC},
        {'id': 'song', 'item': 'Song on iTunes', 'low': 0.99, 'high': 1.29, 'per': '', 'source': SRC},
        {'id': 'tattoo', 'item': 'Small tattoo at Arrow & Ink', 'low': 60, 'high': 150, 'per': '', 'source': SRC},
        {'id': 'charm', 'item': 'Licensed charm', 'low': 15, 'high': 80, 'per': '', 'source': SRC},
        {'id': 'day-wage', 'item': 'A work-study day', 'low': 50, 'high': 70, 'per': 'day', 'source': SRC}],
    'water': [{'kind': 'river', 'name': 'Haven River', 'width_km': 0.06,
               'points': [[42.73, -76.412], [42.718, -76.413], [42.708, -76.414], [42.698, -76.416]]}],
    'notables': notables,
    # The fae of Haven are named on the cast, never rolled into the townsfolk: every kind's share is 0.
    'kinds': {
        'fae': {'label': 'Fae', 'lifespan': 700, 'words': ['fae', 'fey', 'sidhe'], 'share': 0},
        'half-fae': {'label': 'Half-fae', 'lifespan': 200, 'words': ['half-fae', 'half fae'], 'share': 0},
        'kitsune': {'label': 'Kitsune', 'lifespan': 1000, 'words': ['kitsune', 'fox fae'], 'share': 0},
        'dryad': {'label': 'Dryad', 'lifespan': 400, 'words': ['dryad'], 'share': 0},
        'sylph': {'label': 'Sylph', 'lifespan': 500, 'words': ['sylph'], 'share': 0},
        'selkie': {'label': 'Selkie', 'lifespan': 250, 'words': ['selkie'], 'share': 0}},
}

if __name__ == '__main__':
    OUT.write_text(json.dumps(CITY, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
