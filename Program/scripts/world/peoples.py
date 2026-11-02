"""The peoples of fantasy worlds: beastkin, fantasy humanoids and other peoples, each a kind (a lifespan and the words
that name it, world/data/lifespans.json) and a name group with its own naming scheme in the `peoples` name bank
(world/data/names.json). Run `python scripts/world/names.py`, which reads this file, to rewrite both.

No people has real-world names to draw on, so each naming scheme is a small phonology (the sounds its names are made
of and the endings a woman's or a man's name takes) or a way of making family names (a clan word, a title, a house),
drawn from a fixed seed so the lists only change when this file does. Every group has well over a hundred given names
and over a hundred family names (or titles, for peoples who go by them). Names that read as made up by a language
model (Elara, Kael, Ravencrest, Thessaly) and names from other people's books are left out, the same check
dungeon/world/naming.py runs on what a model writes.

A town draws on these through `names.also: ["peoples"]` and weighs each group in its `mix`, beside its own human
heritages: {"english": 6, "dwarf": 2, "wolf-kin": 1} is a town of mostly human folk with dwarves and wolf-kin.
"""
import json
import random
import re
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROGRAM))
from dungeon.world.naming import COINED_FAMILY, COINED_GIVEN  # noqa: E402

DATA = PROGRAM / 'dungeon' / 'world' / 'data'
GIVEN_NAMES = json.loads((DATA / 'given_names.json').read_text(encoding='utf-8'))
INVENTED = {word.casefold() for word in [*GIVEN_NAMES['invented']['given'], *GIVEN_NAMES['invented']['family']]}
# Other people's books and games, and names Vanta has asked to keep out (Voss, Maren, Thorne, Ostrec).
TAKEN = {word.casefold() for word in '''
    Baggins Took Brandybuck Proudfoot Underhill Gamgee Boffin Bolger Burrows Goodbody Hornblower Sackville
    Bracegirdle Chubb Grubb Brockhouse Greenhand Cotton Gardner Tunnelly Smallburrow Brownlock Sandyman Whitfoot
    Puddifoot Goldworthy Gimli Thorin Balin Dwalin Durin Gloin Oin Bombur Bifur Bofur Dori Nori Ori Fili Kili
    Legolas Galadriel Elrond Arwen Drizzt Zaknafein Menzoberranzan Bruenor Mordenkainen Elminster Tasslehoff
    Raistlin Asterion Shuten Ibaraki Sojobo Tarobo Akaza Muzan Voss Maren Thorne Ostrec Kitiara Tanis Caramon
    Grishnakh Gorbag Shagrat Ugluk Azog Bolg Uruk Ghash Lugbur Mauhur Snaga Gothmog Lurtz Thrall Grommash
    Durotan Garrosh Hellscream Saurfang Sylvanas Tyrande Illidan Malfurion Jaina Gul'dan Zuljin Kilrogg
    Puck Oberon Titania Mab Robin Goodfellow Pan Chiron Nessus Pholus Silenus Marsyas Lilith Asmodeus Mammon
'''.split()}
# Words no generated name may contain.
RUDE = re.compile(r'fuck|shit|cunt|nig|fag|rape|slut|cum|tit|anus|piss|dick|cock|porn|jew|wank|twat|kike|spic|'
                  r'chink|gook|kkk|nazi|hitl|poop|turd|semen|vagin|penis|whore|bitch|sex|ass$|^ass|arse|bum$|'
                  r'nonce|homo|dyke|tard|cripp|gyp|negr|coon|wog|paki|jap$|chav|pedo|incel', re.I)
CLUSTER = re.compile(r'[^aeiouy\s\'-]{4}|([a-z])\1\1|[aeiouy]{3}|ii|yy|^(gith|illith|ithil|drizz)', re.I)
WORD = re.compile(r"[A-Za-z][A-Za-z'’]*")
FEMININE, MASCULINE, NEUTRAL, FAMILY = 70, 70, 20, 110


def ok(name: str) -> bool:
    """A name a person could carry: no word reads as made up by a model or comes from someone else's book, no
    rude word, nothing unpronounceable."""
    if not 3 <= len(name) <= 30 or RUDE.search(name.replace(' ', '').replace('-', '')):
        return False
    for word in WORD.findall(name):
        folded = word.casefold()
        if folded in INVENTED or folded in TAKEN or COINED_GIVEN.search(word) or COINED_FAMILY.search(word):
            return False
        if len(word) > 2 and CLUSTER.search(re.sub('th|gh|sh|ch|ph|ck', 'T', word)):
            return False
    return True


def title(text: str) -> str:
    return '-'.join(part[:1].upper() + part[1:] for part in text.split('-'))


# Ways of making a name ---------------------------------------------------------------------------------------------

def sounds(onsets: str, vowels: str, codas: str, endings: str, syllables=(1, 2), bare=0.2):
    """A name made of a people's sounds: syllables (an onset and a vowel, sometimes a closing consonant), then one of
    the endings ("a", "ka", "ok"). `bare` is how often a name starts on its vowel."""
    onsets, vowels, codas, endings = onsets.split(), vowels.split(), codas.split(), endings.split()

    def make(rng: random.Random) -> str:
        root = ''
        for index in range(rng.choice(syllables)):
            onset = '' if index == 0 and rng.random() < bare else rng.choice(onsets)
            root += onset + rng.choice(vowels)
            if codas and rng.random() < 0.35:
                root += rng.choice(codas)
        ending = rng.choice(endings)
        if root[-1:] in 'aeiouy' and ending[:1] in 'aeiouy':
            root = root[:-1] or root
        return title(root + ending)
    return make


def morae(units: str, endings: str, count=(2, 3)):
    """A Japanese-sounding name: two or three morae and an ending (Hana-ko, Tetsu-maru)."""
    units, endings = units.split(), endings.split()

    def make(rng: random.Random) -> str:
        return title(''.join(rng.choice(units) for _ in range(rng.choice(count))) + rng.choice(endings))
    return make


def compound(firsts: str, seconds: str):
    """A family name of two plain words, as many clans and herds are called (Longstride, Ferngate)."""
    firsts, seconds = firsts.split(), seconds.split()

    def make(rng: random.Random) -> str:
        first, second = rng.choice(firsts), rng.choice(seconds)
        return '' if first.casefold() == second.casefold() else title(first.lower() + second.lower())
    return make


def pattern(text: str, **lists: str):
    """A title or a family name made from a pattern: pattern('the {adj}', adj='Unbowed Scarred') says "the Unbowed"."""
    pools = {key: words.replace('_', ' ').split('|') if '|' in words else words.split() for key, words in lists.items()}

    def make(rng: random.Random) -> str:
        return text.format(**{key: rng.choice(pool).replace('_', ' ') for key, pool in pools.items()})
    return make


def either(*choices):
    """One of several ways of making a name, each as often as its weight: either((3, a), (1, b))."""
    def make(rng: random.Random) -> str:
        return rng.choices([made for _, made in choices], weights=[weight for weight, _ in choices])[0](rng)
    return make


def words(text: str):
    """A name from a fixed list (virtue names, flowers): each used once."""
    pool = text.split()

    def make(rng: random.Random) -> str:
        return rng.choice(pool)
    return make


def drawn(make, count: int, rng: random.Random, used: set[str]) -> list[str]:
    found = []
    for _ in range(count * 400):
        name = make(rng).strip()
        if name and name.casefold() not in used and ok(name):
            used.add(name.casefold())
            found.append(name)
            if len(found) == count:
                return found
    raise ValueError(f'Only {len(found)} of {count} names could be made: widen the scheme.')


# Naming schemes ----------------------------------------------------------------------------------------------------

def scheme(feminine, masculine, neutral, family) -> dict:
    return {'feminine': feminine, 'masculine': masculine, 'neutral': neutral, 'family': family}


def voiced(onsets, vowels, codas, feminine, masculine, neutral, family, syllables=(1, 2), bare=0.2) -> dict:
    """A scheme from one set of sounds with endings for women's, men's and anyone's names."""
    return scheme(*(sounds(onsets, vowels, codas, ending, syllables, bare) for ending in (feminine, masculine, neutral)),
                  family)


def sexless(onsets, vowels, codas, endings, family, syllables=(1, 2), bare=0.2) -> dict:
    """A scheme for a people whose names say nothing about sex (fungal folk, clockwork folk)."""
    made = sounds(onsets, vowels, codas, endings, syllables, bare)
    return scheme(made, made, made, family)


ORC_TITLES = either(
    (2, pattern('the {adj}', adj='Unbowed Scarred Red Grey Old Loud Quiet Lame Tall Patient Hungry Burnt Blind '
                             'One-Eyed Laughing Last Bitter Cold Gentle Lucky Slow Stubborn Toothless Grim-Jawed '
                             'Twice-Hanged Unburied Pale Broken-Nosed Left-Handed Bald Wakeful')),
    (3, pattern('{noun}-{doer}', noun='Skull Bone Shield Tusk Ear Throat Horse Wall Oath Spear Gate Bridge Chain Knee '
                                      'Elk Boar Tooth Neck Helm Axe',
                doer='Breaker Taker Eater Splitter Biter Burner Cleaver Keeper Crusher Hunter Gnawer Sunderer Mender')),
    (1, pattern('{count}-{thing}', count='Two Three Four Five Six Seven Eight Nine Ten Twelve',
                thing='Scars Fingers Winters Wives Kills Teeth Rivers')),
)

SCHEMES = {
    # Beastkin -------------------------------------------------------------------------------------------------------
    'canid': voiced('r g k s t h l b f v d', 'a u o e i', 'r n l s k',
                    'a ka ra sha ya ika esh unna', 'ak ul ar ok usk an ud', 'ri en o',
                    compound('Long Far Swift Grey Red Old Low High Cold Wide Deep Fen Hill Pine Burr Brush Den Track '
                             'Scent Rough Lean Quick Ridge Snow Wet Dry',
                             'run howl tooth fang paw track trail stride coat ear tail scent den jaw bark muzzle')),
    'feline': voiced('s sh m r p n z t l', 'a i e o', 'r n s',
                     'isha ira ena isa ou ani ee', 'ar en ash es ou um', 'i a',
                     compound('Sand Tall Still Gold Silk Soft Amber Spot Stripe Quiet Slow Sleek Long Dapple Tawny '
                              'Ember Cream Ash Smoke Velvet Hush Noon',
                              'paw claw tail whisker step eye pelt mane leap prowl purr coat')),
    'serpent': voiced('s sh z h v k n th', 'a i e', 's r',
                      'ssa sha ari isa eth ika', 'ash ir esh an ur ik', 'is a',
                      either((3, sounds('s sh z h v k n th r', 'a i e', 'sh s r', 'isk eth arsa ishan ess', (2,), 0.1)),
                             (1, compound('Coil Scale Sun Sand Still Cold Dust Stone Reed Silt Dune Basin',
                                          'coil scale skin sleeper fang tongue')))),
    'equine': voiced('b br d g h k m r t f c', 'a e o i', 'n r l nn',
                     'a anne ia elle wyn een', 'or an en ard ock ic', 'ry o',
                     compound('Far Swift Long Dapple Bay Roan Chestnut Fleet Steady Wide High Grey Dun Sorrel Piebald '
                              'Mud Barley Hay Spring',
                              'mane hoof stride run field gait flank canter')),
    'bovine': voiced('b m g d h t k r', 'o u a', 'r n m l rr',
                     'a ra unna olla ie', 'or uk on ar um og', 'o',
                     compound('Broad Great Low Stone Field Hay Plow Yoke Wide Deep Ox Clover Mire Moor Slow Brindle '
                              'Heavy Old Grass',
                              'horn hide hoof yoke field ford stall shoulder')),
    'minotaur': voiced('k t d m p l n st th r', 'a e o i', 'r n s',
                       'eia ene a issa ope', 'os on ios aros eon', 'is',
                       pattern('of the {adj} {place}', adj='Long Low Stone Ninth Red Deep Bronze Old Broken High '
                                                             'Salt Crooked Cold Wide Green Seventh',
                               place='Hall Gate Maze Turn Door Stair Wall Court Pillar Way Yard Cistern')),
    'lagomorph': voiced('p b f l n m t h w', 'i e a o', 'n l p',
                        'ie ette illa a ina', 'in kin pip on ick', 'y',
                        compound('Clover Bramble Burrow Warren Thistle Briar Hedge Fern Barley Meadow Dandelion Sorrel '
                                 'Moss Dew Pea Turnip Lettuce',
                                 'foot ear hop run dell bank leap whisker')),
    'cervid': voiced('b br c d f g l m r t', 'a e i o', 'n r ll ch',
                     'wen eth a ia en', 'ach an en or ic', 'el',
                     compound('High Wide Fern Moss Oak Birch Elder Bracken Glen Heather Rush Bog Hazel Holly Rowan '
                              'Larch Spruce Grove Thicket Dapple Copper Russet Bramble Frost',
                              'antler hart run brook leap tine hoof flank step')),
    'ursine': voiced('b br g gr h k t m', 'o u a e', 'r rn n l',
                     'a hild unn ga', 'orn ard un ulf og', 'e',
                     compound('Honey Den Oak Stone Old Broad Bramble Hill Cave Pine Berry Salmon Root Hollow Fell',
                              'paw claw den hide back maul belly shoulder')),
    'avian': voiced('k kr t tr sk pr w h ch l', 'i e a ee', 'k r l',
                    'ee ia ira ett illa', 'ik ek aw ar it', 'i',
                    compound('High Far Cliff Cloud Reed Marsh Pine Feather Quill Gale Crag Thermal Spire Dawn Bough Sky Rain Ridge Eyrie',
                             'wing feather flight call song talon beak plume glide')),
    'draconic': voiced('dr kr th v z sk r t g', 'a o i u', 'r k',
                       'ia ra esh ix ka', 'ax or ok ur ak', 'is',
                       sounds('dr kr th v z sk r t g b', 'a o i u', 'r', 'akar ovan uun irax esh orra', (1,), 0.1),
                       (1, 2), 0.1),
    # Fantasy humanoids ----------------------------------------------------------------------------------------------
    'high-elf': voiced('l m n s t v r c f d', 'e i a o ie', 'l n r s',
                       'iel ine enne ise ora ette', 'ien or ande ois enne ard', 'ian',
                       sounds('l m n s t v r c f d b', 'e i a o', 'l n r', 'andis eline oris erin ancourt evaux',
                              (1, 2), 0.1), (2, 3), 0.15),
    'wood-elf': voiced('b br c cw d f g gw l ll m r rh t', 'a e i o y', 'n r l dd',
                       'wen eth a is ys', 'an yn och ion ed', 'i',
                       compound('Fern Moss Rowan Alder Hazel Yew Birch Bracken Briar Holly Sorrel Acorn Lichen Willow Sloe Linden '
                                'Hawthorn Beech',
                                'glade dell brook leaf root bough copse thicket spring path')),
    'half-elf': voiced('l m n r s t d c b h', 'a e i o', 'n l r',
                       'ia elle ine wen a', 'an el in or ric', 'y',
                       sounds('l m n r s t d c b h w', 'a e i o', 'n l r', 'ley ford wyn ell ard ine', (1, 2), 0.1)),
    'dark-elf': voiced('z s v r k d m t l', 'i a e u', 'z r s k',
                       'iss ira ezza ith ane', 'ek ix ar uun iz', 'e',
                       sounds('z s v r k d m t l g', 'i a e u', 'z r k', 'ane ess orn iz uzz', (2,), 0.1), (2, 3), 0.15),
    'sea-elf': voiced('m n l w h s t k', 'a e o u i', 'n l',
                      'ella ina ua ena', 'ul en o ar am', 'i',
                      compound('Tide Salt Reef Kelp Pearl Shell Brine Foam Coral Deep Wave Current Shoal Gull Swell Spray Surf Lagoon',
                               'singer rider diver strand drift reach call swimmer glide')),
    'dwarf': voiced('b br d dr g gr k kr t th h m n', 'a o u i e', 'r n m k g d l rn rd',
                    'a hild dis run gret', 'in ak or im ur', 'i',
                    compound('Stone Deep Copper Coal Anvil Hammer Flint Granite Slate Ore Tin Gold Lode Bellows Chisel '
                             'Seam Quarry Basalt',
                             'beard delve hand fist shaft vein hewer brow back mattock')),
    'orc': voiced('g gr k kr z zh sh b d dr r t th m', 'a u o', 'g k r z sh rk zg',
                  'a ka sha ga', 'ak ug ash ok rog', 'o', ORC_TITLES),
    'half-orc': voiced('g k d b m r t h s', 'a o u e i', 'r n g k',
                       'a ena ka ra', 'ar ock en an', 'e',
                       sounds('g k d b m r t h s', 'a o u e', 'r n', 'ley ston ard wick ham ett', (1,), 0.1)),
    'goblin': voiced('sn sk gr n z p b k t g', 'i e a o', 'k z t b',
                     'ina ett ix a', 'ik it ub ok', 'i',
                     compound('Rag Nail Mud Rust Pot Grub Slip Quick Crook Pinch Soot Lint Tatter Gristle Snatch',
                              'nose fingers ears teeth knees foot grin chin elbow')),
    'hobgoblin': voiced('h k kr t d v r m g', 'a o e u', 'r k g',
                        'a ka ra eth', 'ak ur en ash orr', 'e',
                        either((2, sounds('h k kr t d v r m g', 'a o e u', 'r k', 'ak ur en ash ovar', (2,), 0.1)),
                               (1, pattern('of the {rank} {unit}', rank='First Second Third Fourth Fifth Sixth',
                                           unit='Shield Spear Banner Line Watch Cohort Wall')))),
    'halfling': voiced('b p m t d f h l w n', 'a o i e u', 'l n m',
                       'ie ella ina abel', 'o in kin by wick', 'y',
                       compound('Apple Bramble Honey Thistle Mill Brook Barley Bread Butter Pickle Plum Quince Pepper '
                                'Clover Kettle Hearth Hazel',
                                'bottom bank barrow field dale hedge wick ford cot stile')),
    'gnome': voiced('b f g n p t w z', 'i o e a u', 'n b k',
                    'ella ina li ett', 'o wick bin ock', 'i',
                    compound('Cog Spring Copper Gear Brass Tumble Fiddle Nimble Pebble Button Tinker Sprocket Ratchet Bobbin Thimble '
                             'Widget Fizzle',
                             'wick spindle bottle whistle nose pocket knock top socket')),
    'ogre': voiced('gr g b m d h', 'o u a', 'g m b',
                   'a umma ugga', 'og um ug', 'u',
                   compound('Gut Gristle Marrow Gravel Bog Muck Lump Club Stump Boulder Mud Rubble Peat Cudgel Slab Gob',
                            'gut belly fist back jaw tooth chin knuckle neck')),
    'troll': voiced('tr t sk k g h r st', 'o u a', 'r k g',
                    'a ja unn', 'urr ak olf', 'e',
                    compound('Bridge Moss Fell Scree Rime Bog Cave Root Crag Tarn Cairn Ford Gully Moor Lichen Peat Boulder Gorge',
                             'stone back hide gate under knuckle hump tooth')),
    'giant': voiced('th h b g sk st h r', 'o u a e i', 'r m nd ld',
                    'hild rid a dis', 'mund ald orm ar', 'i',
                    sounds('th h b g sk st r', 'o u a e', 'r', 'garth mund vald heim stad', (1, 2), 0.1)),
    'demon': voiced('m l z b v r s n k', 'a e i o', 'l r s',
                    'ith ara eth ixa ina ozza', 'oth ax el iel or as', 'is',
                    sounds('m l z b v r s n k g', 'a e i o', 'l r', 'oth el ozar uriel aster', (1, 2), 0.1),
                    (1, 2), 0.15),
    'merfolk': voiced('m n l w h s r', 'a e o u i', 'n l r',
                      'ella ina ua ena oa', 'ul en o ar am', 'i',
                      compound('Tide Salt Reef Kelp Pearl Shell Brine Foam Coral Deep Wave Current Shoal Gull Sand Wrack Ebb Eddy',
                               'fin tail scale crest gill pool fathom wake')),
    'sea-kin': voiced('r s sk m f k t h', 'o a e i u', 'n r',
                      'a ina e', 'an or en', 'o',
                      compound('Skerry Seal Grey Kelp Rock Cold North Haar Salt Ness Holm Voe Wrack Sound Geo Stack Firth Sker Tang '
                               'Ebb',
                               'coat skin shore strand ness wick holm sand rock')),
    # Other peoples --------------------------------------------------------------------------------------------------
    'oni': scheme(morae('a ka ki ku ko sa shi su ta to na ni no ha hi mo ra ri ru ro ga go za zu do ba bu', 'ko mi e yo ka'),
                  morae('a ka ki ku ko sa shi su ta to na ni no ha hi mo ra ri ru ro ga go za zu do ba bu', 'maru ji zo ki ta'),
                  morae('a ka ki ko sa shi ta na ha mo ra ri ga go', 'n'),
                  morae('a ka ki ku ko sa shi su ta to na ni ha hi ra ri ga go za', 'doji yama mon dake', (1, 2))),
    'tengu': scheme(morae('a ka ki ko sa su ta tsu na no ha fu ma mi ya yo ri ro wa', 'ne e mi ka'),
                    morae('a ka ki ko sa su ta tsu na no ha fu ma mi ya yo ri ro wa', 'bo kaze maru ichi'),
                    morae('a ka ki sa ta na ha ma ya', 'n'),
                    morae('a ka ki ko sa su ta na ha fu ma mi ya yo ri ro', 'yama dake mine bo', (1, 2))),
    'kappa': scheme(morae('a ka ki ku ko sa su ta te to na nu no ha hi mi mu ka ga ge go', 'ko e no ri'),
                    morae('a ka ki ku ko sa su ta te to na nu no ha hi mi mu ga ge go', 'ta suke zo hei'),
                    morae('a ka ku sa ta na nu ha mu', 'n'),
                    morae('a ka ki ku ko sa ta to na nu ha hi mi ka', 'gawa numa fuchi ike se', (1, 2))),
    'mind-eater': sexless('q kh zh v th l', 'u o i', 'q l r', 'uul oth ix eq ul',
                          pattern("of the {count} {what}", count='Third Fourth Fifth Sixth Seventh Ninth Tenth Hundredth '
                                                                 'Twelfth Last Deepest Coldest',
                                  what='Mind Thought Silence Hunger Dark Choir Pool Brood Dream Murmur'), (1, 2), 0.1),
    'centaur': voiced('k t d m p l n th r s', 'a e o i', 'r n s',
                      'eia ione a ippe', 'os on eus ios', 'is',
                      compound('Swift Long Far High Wide Open Grass Steppe Plain Dust Thunder Gallop Hill River Sage Bright Ford',
                               'hoof stride bow spear run field gait flank arrow')),
    'satyr': voiced('ph l m n t k d s', 'y a e i o', 'n s r',
                    'ippe ea ope ys', 'as on ys ias', 'o',
                    compound('Vine Wine Reed Pipe Goat Grape Ivy Laurel Fig Olive Myrtle Thyme Honey Pine Mint Barley Cypress',
                             'hoof horn leg pipe skin cup flute beard')),
    'dryad': voiced('l m n r s f v d', 'e a i o', 'l n r',
                    'ia ea ine essa', 'an us en', 'e',
                    pattern('of the {adj} {tree}', adj='Old Lone Split White Leaning Tall Burnt Twin Weeping Crooked',
                            tree='Oak Elm Yew Willow Rowan Alder Birch Linden Hazel Beech Cedar Maple')),
    'fae': scheme(compound('Thistle Bramble Dew Moth Hazel Rue Sorrel Nettle Clover Wren Bell Mallow Cowslip Tansy',
                           'down wing bell drop seed thorn petal'),
                  compound('Thistle Bramble Dew Moth Hazel Rue Sorrel Nettle Acorn Wren Sloe Bracken Burdock Rush',
                           'cap wing knot seed thorn stem burr'),
                  words('Hob Tansy Lob Pip Sloe Fennel Wisp Bramble Rue Sorrel Nettle Moth Dew Hazel Tumble Bryony '
                        'Yarrow Teasel Fumitory Cowslip Clary Henbane'),
                  pattern('of the {adj} {place}', adj='Green Grey Low Far Still Bright Lost Briar Rush Seventh',
                          place='Hill Mound Ring Wood Pool Glen Barrow Ford Dell Moor Stone')),
    'lizardfolk': voiced('s ss k t h r z sh', 'a i e o', 'k s sh',
                         'ssa sa ika esh', 'ak ss ik esk', 'i',
                         pattern('{verb}-{how}', verb='Swims Waits Hunts Basks Watches Runs Strikes Sleeps Climbs Wades '
                                                      'Burrows Listens',
                                 how='Deep Long Still Far Low Slow Twice Alone First Quiet Late')),
    'kobold': voiced('k sk sn t d p g', 'i e a o', 'k p t',
                     'ka ika ip ee', 'ik ok ap ek', 'i',
                     compound('Deep Stone Ore Cinder Tunnel Lamp Coal Dirt Scale Shale Grit Pebble Trap Wick Soot Flint Copper Rubble',
                              'claw tail digger snout eye scale pick crawl lamp')),
    'gnoll': voiced('gh g k kh r z d b', 'a o u', 'r k g',
                    'a ra gha', 'ar uk orr', 'u',
                    compound('Carrion Bone Dust Hide Marrow Gut Dry Red Grin Scab Tick Flea Rib Scrub Thorn Sand Gristle',
                             'jaw grin back tooth hunter howl hackle cackle')),
    'celestial': voiced('s l m n r t d v', 'a e i o', 'l n r',
                        'iel ina ah ise ette', 'iel ael on as is', 'i',
                        sounds('s l m n r t d v b c', 'a e i o', 'l n', 'ant ois enne aine', (1, 2), 0.1), (2, 3), 0.15),
    'dhampir': voiced('v d dr m r s st z b k', 'a e i o u', 'n r l',
                      'ana ica ena ia', 'an or ic in ko', 'a',
                      sounds('v d dr m r s st z b k p', 'a e i o u', 'n r', 'escu ov ich ar ovic esku', (1, 2), 0.1),
                      (1, 2), 0.1),
    'djinn': voiced('h k s z r m n f d b', 'a i u aa', 'r m n f',
                    'ira a ina ya', 'ar im an ad', 'i',
                    sounds('h k s z r m n f d b', 'a i u', 'r m', 'ari ani adi amir', (1, 2), 0.1), (1, 2), 0.1),
    'insect': sexless('k t ch z tr kl', 'i e a', 'k t ch', 'ik ek ak itt ech',
                      pattern('{order} of {hive}', order='First Second Third Fourth Fifth Sixth Seventh Eighth '
                                                         'Ninth Tenth Eleventh Twelfth',
                              hive='Tikra Chekka Zetri Kalla Trikket Kezzi Tekti Zekka Akkit Ketra Klekka')),
    'spider': voiced('s sh l n v th r', 'i a e', 'l',
                     'ila essa ina', 'il es ith', 'i',
                     compound('Silk Web Thread Spindle Loom Dew Cellar Rafter Corner Eaves Gossamer Bristle Attic Lace Warp Hatch',
                              'spinner leg fang knot line weft step strand hold')),
    'fungal': sexless('m l p b r g d n', 'o u a e', 'm l p', 'u ul om ella oop',
                      compound('Spore Cap Gill Mold Root Loam Damp Rot Moss Puff Mire Bark Cellar Log Dark Cave Humus Fairy',
                               'cap ring stalk patch gill bed spore fruit')),
    'clockwork': sexless('t k p b r tk ck', 'o i e a', 'k ck n', 'ock ick en o',
                         pattern('{order} {make}', order='First Second Third Fourth Fifth Sixth Seventh Eighth Ninth '
                                                          'Tenth Eleventh Twelfth',
                                 make='Pattern Casting Winding Mark Series Make Model Spring Forging Escapement Mainspring')),
}


# The peoples ------------------------------------------------------------------------------------------------------

BEASTKIN, HUMANOID, OTHER = 'Beastkin', 'Fantasy humanoids', 'Other peoples'

# (kind, label, lifespan in years (None: doesn't age), words that name them, folk, type, scheme)
PEOPLES = [
    ('wolf-kin', 'Wolf-kin', 70, ['wolf-kin', 'wolfkin', 'wolf-folk', 'wolffolk'], BEASTKIN, 'Canids', 'canid'),
    ('dog-kin', 'Dog-kin', 65, ['dog-kin', 'dogkin', 'dog-folk', 'dogfolk'], BEASTKIN, 'Canids', 'canid'),
    ('fox-kin', 'Fox-kin', 90, ['fox-kin', 'foxkin', 'fox-folk', 'foxfolk', 'kitsune'], BEASTKIN, 'Canids', 'canid'),
    ('coyote-kin', 'Coyote-kin', 65, ['coyote-kin', 'coyote-folk'], BEASTKIN, 'Canids', 'canid'),
    ('jackal-kin', 'Jackal-kin', 65, ['jackal-kin', 'jackal-folk', 'jackalfolk'], BEASTKIN, 'Canids', 'canid'),
    ('cat-kin', 'Cat-kin', 75, ['cat-kin', 'cat-folk', 'catfolk'], BEASTKIN, 'Felines', 'feline'),
    ('lynx-kin', 'Lynx-kin', 75, ['lynx-kin', 'lynx-folk'], BEASTKIN, 'Felines', 'feline'),
    ('lion-kin', 'Lion-kin', 80, ['lion-kin', 'lion-folk', 'lionfolk'], BEASTKIN, 'Felines', 'feline'),
    ('tiger-kin', 'Tiger-kin', 80, ['tiger-kin', 'tiger-folk', 'tigerfolk'], BEASTKIN, 'Felines', 'feline'),
    ('leopard-kin', 'Leopard-kin', 75, ['leopard-kin', 'leopard-folk'], BEASTKIN, 'Felines', 'feline'),
    ('panther-kin', 'Panther-kin', 75, ['panther-kin', 'panther-folk'], BEASTKIN, 'Felines', 'feline'),
    ('naga', 'Naga', 300, ['naga', 'nagas'], BEASTKIN, 'Serpents', 'serpent'),
    ('lamia', 'Lamia', 300, ['lamia', 'lamiae'], BEASTKIN, 'Serpents', 'serpent'),
    ('viper-kin', 'Viper-kin', 110, ['viper-kin', 'viper-folk', 'snake-kin', 'snakefolk'], BEASTKIN, 'Serpents',
     'serpent'),
    ('constrictor-kin', 'Constrictor-kin', 130, ['constrictor-kin', 'python-kin', 'boa-kin'], BEASTKIN, 'Serpents',
     'serpent'),
    ('horse-kin', 'Horse-kin', 85, ['horse-kin', 'horse-folk', 'horsefolk'], BEASTKIN, 'Equines', 'equine'),
    ('zebra-kin', 'Zebra-kin', 80, ['zebra-kin', 'zebra-folk'], BEASTKIN, 'Equines', 'equine'),
    ('donkey-kin', 'Donkey-kin', 95, ['donkey-kin', 'donkey-folk', 'mule-kin'], BEASTKIN, 'Equines', 'equine'),
    ('unicorn-kin', 'Unicorn-kin', 400, ['unicorn-kin', 'unicorn-folk'], BEASTKIN, 'Equines', 'equine'),
    ('cow-kin', 'Cow-kin', 85, ['cow-kin', 'cow-folk', 'cowfolk'], BEASTKIN, 'Bovines', 'bovine'),
    ('bull-kin', 'Bull-kin', 85, ['bull-kin', 'bull-folk', 'bullfolk'], BEASTKIN, 'Bovines', 'bovine'),
    ('minotaur', 'Minotaur', 120, ['minotaur', 'minotaurs'], BEASTKIN, 'Bovines', 'minotaur'),
    ('buffalo-kin', 'Buffalo-kin', 90, ['buffalo-kin', 'bison-kin', 'buffalo-folk'], BEASTKIN, 'Bovines', 'bovine'),
    ('rabbit-kin', 'Rabbit-kin', 60, ['rabbit-kin', 'rabbit-folk', 'rabbitfolk', 'bunnyfolk'], BEASTKIN, 'Lagomorphs',
     'lagomorph'),
    ('hare-kin', 'Hare-kin', 65, ['hare-kin', 'hare-folk', 'harefolk'], BEASTKIN, 'Lagomorphs', 'lagomorph'),
    ('deer-kin', 'Deer-kin', 80, ['deer-kin', 'deer-folk', 'deerfolk'], BEASTKIN, 'Cervids', 'cervid'),
    ('elk-kin', 'Elk-kin', 85, ['elk-kin', 'elk-folk'], BEASTKIN, 'Cervids', 'cervid'),
    ('stag-kin', 'Stag-kin', 85, ['stag-kin', 'stag-folk'], BEASTKIN, 'Cervids', 'cervid'),
    ('moose-kin', 'Moose-kin', 90, ['moose-kin', 'moose-folk'], BEASTKIN, 'Cervids', 'cervid'),
    ('bear-kin', 'Bear-kin', 100, ['bear-kin', 'bearkin', 'bear-folk', 'bearfolk'], BEASTKIN, 'Ursines', 'ursine'),
    ('hawk-kin', 'Hawk-kin', 70, ['hawk-kin', 'hawk-folk', 'hawkfolk'], BEASTKIN, 'Avians', 'avian'),
    ('owl-kin', 'Owl-kin', 90, ['owl-kin', 'owl-folk', 'owlfolk'], BEASTKIN, 'Avians', 'avian'),
    ('corvid-kin', 'Corvid-kin', 80, ['corvid-kin', 'crow-kin', 'raven-kin', 'crowfolk'], BEASTKIN, 'Avians', 'avian'),
    ('songbird-kin', 'Songbird-kin', 60, ['songbird-kin', 'bird-folk', 'birdfolk'], BEASTKIN, 'Avians', 'avian'),
    ('waterfowl-kin', 'Waterfowl-kin', 70, ['waterfowl-kin', 'duck-kin', 'swan-kin', 'goose-kin'], BEASTKIN, 'Avians',
     'avian'),
    ('dragon-kin', 'Dragon-kin', 300, ['dragon-kin', 'dragonkin', 'dragonborn'], BEASTKIN, 'Draconic', 'draconic'),
    ('wyrm-kin', 'Wyrm-kin', 500, ['wyrm-kin', 'wyrmkin'], BEASTKIN, 'Draconic', 'draconic'),
    ('high-elf', 'High elf', 750, ['high elf', 'high-elf', 'high elven'], HUMANOID, 'Elves', 'high-elf'),
    ('wood-elf', 'Wood elf', 500, ['wood elf', 'wood-elf', 'wood elven'], HUMANOID, 'Elves', 'wood-elf'),
    ('dark-elf', 'Dark elf', 600, ['dark elf', 'dark-elf', 'dark elven', 'drow'], HUMANOID, 'Elves', 'dark-elf'),
    ('sea-elf', 'Sea elf', 600, ['sea elf', 'sea-elf', 'sea elven'], HUMANOID, 'Elves', 'sea-elf'),
    ('dwarf', 'Dwarf', 300, ['dwarf', 'dwarven', 'dwarvish'], HUMANOID, 'Dwarves', 'dwarf'),
    ('orc', 'Orc', 55, ['orc', 'orcish'], HUMANOID, 'Orcs', 'orc'),
    ('half-orc', 'Half-orc', 75, ['half-orc', 'half orc'], HUMANOID, 'Orcs', 'half-orc'),
    ('goblin', 'Goblin', 50, ['goblin', 'goblins'], HUMANOID, 'Goblins', 'goblin'),
    ('hobgoblin', 'Hobgoblin', 70, ['hobgoblin', 'hobgoblins'], HUMANOID, 'Goblins', 'hobgoblin'),
    ('halfling', 'Halfling', 110, ['halfling', 'hobbit'], HUMANOID, 'Halflings and gnomes', 'halfling'),
    ('gnome', 'Gnome', 400, ['gnome', 'gnomish'], HUMANOID, 'Halflings and gnomes', 'gnome'),
    ('ogre', 'Ogre', 60, ['ogre', 'ogress', 'ogrish'], HUMANOID, 'Giant-kin', 'ogre'),
    ('troll', 'Troll', 200, ['troll', 'trollish'], HUMANOID, 'Giant-kin', 'troll'),
    ('giant', 'Giant', 400, ['giant-kin', 'giantess', 'true giant'], HUMANOID, 'Giant-kin', 'giant'),
    ('half-giant', 'Half-giant', 120, ['half-giant', 'half giant'], HUMANOID, 'Giant-kin', 'giant'),
    ('tiefling', 'Tiefling', 100, ['tiefling', 'tieflings'], HUMANOID, 'Fiends', 'demon'),
    ('succubus', 'Succubus or incubus', 1000, ['succubus', 'incubus', 'succubi', 'incubi'], HUMANOID, 'Fiends',
     'demon'),
    ('demon-blooded', 'Demon-blooded', 120, ['demon-blooded', 'demonblooded', 'cambion'], HUMANOID, 'Fiends', 'demon'),
    ('merfolk', 'Merfolk', 250, ['merfolk', 'mermaid', 'merman', 'merrow'], HUMANOID, 'Merfolk and sea-kin', 'merfolk'),
    ('sea-kin', 'Sea-kin', 150, ['sea-kin', 'seafolk', 'selkie'], HUMANOID, 'Merfolk and sea-kin', 'sea-kin'),
    ('oni', 'Oni', 500, ['oni'], OTHER, 'Yokai', 'oni'),
    ('tengu', 'Tengu', 400, ['tengu'], OTHER, 'Yokai', 'tengu'),
    ('kappa', 'Kappa', 200, ['kappa'], OTHER, 'Yokai', 'kappa'),
    ('mind-eater', 'Mind-eater', 250, ['mind-eater', 'mind eater', 'mind-eaters'], OTHER, 'Aberrations', 'mind-eater'),
    ('centaur', 'Centaur', 120, ['centaur', 'centaurs'], OTHER, 'Fey and wild folk', 'centaur'),
    ('satyr', 'Satyr', 150, ['satyr', 'faun'], OTHER, 'Fey and wild folk', 'satyr'),
    ('dryad', 'Dryad', 1000, ['dryad', 'dryads'], OTHER, 'Fey and wild folk', 'dryad'),
    ('fae', 'Fae', None, ['fae', 'faerie', 'fairy', 'pixie'], OTHER, 'Fey and wild folk', 'fae'),
    ('lizardfolk', 'Lizardfolk', 60, ['lizardfolk', 'lizard-folk', 'lizardman', 'lizard-kin'], OTHER, 'Scaled folk',
     'lizardfolk'),
    ('kobold', 'Kobold', 120, ['kobold', 'kobolds'], OTHER, 'Scaled folk', 'kobold'),
    ('gnoll', 'Gnoll', 45, ['gnoll', 'gnolls'], OTHER, 'Beast-headed folk', 'gnoll'),
    ('celestial-blooded', 'Celestial-blooded', 160, ['celestial-blooded', 'angel-blooded'], OTHER, 'Planetouched',
     'celestial'),
    ('dhampir', 'Dhampir', 300, ['dhampir', 'dhampyr'], OTHER, 'Planetouched', 'dhampir'),
    ('djinn-blooded', 'Djinn-blooded', 200, ['djinn-blooded', 'jinn-blooded', 'genie-blooded'], OTHER, 'Planetouched',
     'djinn'),
    ('insectfolk', 'Insectfolk', 40, ['insectfolk', 'insect-kin', 'antfolk', 'beetle-kin'], OTHER, 'Crawling folk',
     'insect'),
    ('spider-kin', 'Spider-kin', 80, ['spider-kin', 'spiderfolk', 'spider-folk'], OTHER, 'Crawling folk', 'spider'),
    ('fungal-folk', 'Fungal folk', 60, ['fungal folk', 'fungus folk', 'mushroom folk'], OTHER, 'Crawling folk',
     'fungal'),
    ('clockwork-folk', 'Clockwork folk', None, ['clockwork folk', 'clockwork person', 'automaton'], OTHER, 'Made folk',
     'clockwork'),
]

# The kinds that were there before the peoples, kept first and as they were (the elf of the old city files, and the
# half-elf a human and an elf have together).
CORE = {
    'human': {'label': 'Human', 'lifespan': 80, 'words': []},
    'elf': {'label': 'Elf', 'lifespan': 600, 'words': ['elf', 'elven', 'elvish'], 'folk': HUMANOID, 'type': 'Elves'},
    'half-elf': {'label': 'Half-elf', 'lifespan': 180, 'words': ['half-elf', 'half elf', 'half-elven'],
                 'folk': HUMANOID, 'type': 'Elves'},
}
AGELESS = {'ageless': {'label': "Doesn't age", 'lifespan': None, 'words': ['immortal', 'ageless', 'vampire']}}
BLENDS = [{'parents': ['elf', 'human'], 'child': 'half-elf'}, {'parents': ['human', 'orc'], 'child': 'half-orc'},
          {'parents': ['giant', 'human'], 'child': 'half-giant'}]


def kinds() -> dict[str, dict]:
    """Every kind: the old ones, then each people's ({label, lifespan, words, folk, type})."""
    found = dict(CORE)
    for kind, label, lifespan, named, folk, kind_type, _scheme in PEOPLES:
        found[kind] = {'label': label, 'lifespan': lifespan, 'words': named, 'folk': folk, 'type': kind_type}
    return found | AGELESS


def lifespans() -> dict:
    return {'kinds': kinds(), 'blends': BLENDS}


# The old kinds that have names of their own here too.
CORE_SCHEMES = {'elf': 'high-elf', 'half-elf': 'half-elf'}


def bank() -> dict[str, dict]:
    """The `peoples` name bank: a group for each people, named like its kind and tied to it."""
    groups = {}
    named = [(kind, key) for kind, key in CORE_SCHEMES.items()] + [(people[0], people[-1]) for people in PEOPLES]
    for kind, key in named:
        made, rng, used = SCHEMES[key], random.Random(f'peoples:{kind}'), set()
        group = {field: drawn(made[field], count, rng, used if field != 'family' else set())
                 for field, count in (('feminine', FEMININE), ('masculine', MASCULINE), ('neutral', NEUTRAL),
                                      ('family', FAMILY))}
        groups[kind] = group | {'cultures': {}, 'kind': kind}
    return groups


if __name__ == '__main__':
    for key, group in bank().items():
        print(key, ', '.join(random.Random(key).sample([f'{given} {family}' for given, family in
                                                        zip(group['feminine'] + group['masculine'],
                                                            group['family'] * 2)], 4)))
