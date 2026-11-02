# World data

[Back to the README](../../README.md) · [Architecture](architecture.md)

> This engine came from Prospero's Companion, where a companion was its main consumer. Milestone 0 removed the
> companion; the story, its persona and the townsfolk use the engine now, and the sections below that mention a
> companion describe parts the game will build on again.

The Dungeon ships static facts about cities so that everyday life is assembled from data
and the model only phrases it (PRD W1–W4). A townsperson's day, job, home and the weather are picked by
deterministic code from these records. The model never has to invent a
museum, an employer or a neighbourhood, and the same inputs always give the same choice.

The app ships each built-in world's towns, all `setting: original` and written for the Dungeon: **Kingswood**, the
Post-Reform logging town in Vanta's Vallarith where new stories start (`scripts/world/kingswood.py`), Haven for
Havenbrooke, and the Concourse, Hollin and the Gilded Bazaar for BABEL. Haddon Harbor, the modern Maine town from
Companion, is retired (`dungeon/world/data/retired`, `dungeon/world/retired.py`): a world already set there keeps it
as one of its own cities, and new worlds never see it. Every other city is the user's own or comes from a city pack. Cities can
be `real`, `fictional` or `original`, in any era.

The tests use copies of the cities that used to ship (real cities such as Baltimore and London, other eras such
as London in 1895 and New York in 1925, and fantasy towns such as Camelot and Grandport), in
`tests/fixtures/cities`. They are not package data and the app never loads them.

City lists (Settings > Cities and every city picker) shelve cities as **Real / Modern**, **Other Eras**,
**Fictional** and **Custom**. Custom holds the user's own cities. Any other city can name its shelf in
`category` (`real`, `other-eras` or `fictional`); otherwise it is worked out from `setting` and `era`: a real
city of today is Real / Modern, a real or original city in a past era (`victorian`, `frontier`, `medieval`,
`jazz-age`, `other`) is Other Eras, and the rest are Fictional. London 1895 is a `fictional` setting that names
`other-eras`, since it is real London with Holmes's places added. The summary from `GET /api/world/cities`
carries the result as `category`.

**Featured cities.** `dungeon/world/data/featured.json` names a release (`"0.8"`), a title, a short note and up
to four city ids, plus `new_cities`, the ones among them that first shipped in that release, and is edited at each
release. `GET /api/world/featured` returns the ones that load, in that order, with `new` true while the app's
major.minor version matches the release, and on each city `new` while that holds and it is in `new_cities`.
Settings > Cities shows them as a strip of cards above the shelves (hidden when the list is empty), with a New
badge on each city whose `new` is set; Quick start lists
them first under Featured.

Users can also build their own cities (see [Building a city](#building-a-city)). `GET /api/world/cities`
lists what a workspace actually has. Each city has neighbourhoods (with approximate centres, typical rents and
housing), places (attractions, museums, parks, venues, food, bars, shopping), colleges, major
employers, career hubs, transit, monthly climate and recurring annual events. A shared catalogue
of about 45 modern careers describes schedules and themes; a city whose `era` is not `modern`
(`victorian`, `medieval`, `fantasy`, `steampunk`, `frontier`, `jazz-age`, `future`, `other`) defines its own
careers. A career may say who did that work in its era (`worked_by`: `men` or `women`; left out, anyone). In a
city that keeps work by gender, townsfolk, circles and a companion's job changes only get the work of their side
(they/them people get any): `work_by_gender` turns it on or off, and left out the era decides (on for `victorian`,
`medieval`, `steampunk` and `frontier`, off otherwise; Ellerbrück turns it on, Grandport and Oz leave it off).
Each city also names its `currency` and `rent_period` (`month` or `week`); rents and climate
are optional, so a setting without money (Oz) or without weather data still works. A city may set its world's
default `intensity`: a `preset` (`restrained`, `mature` or `unflinching`) and the narrator's `voice` there (Kingswood:
unflinching and grim); left out, stories there are unflinching with no voice.

## Where the data lives

| Path | Holds |
| --- | --- |
| `dungeon/world/data/cities/<id>.json` | One city. Validated against `dungeon/world/schema.py` on load and in the tests. |
| `dungeon/world/data/careers.json` | Careers with sector, schedule pattern, pay band and themes. `adult: true` marks adult work: only chosen for adult companions (drafting, the character form with the adult side on), never rolled for townsfolk, circles or job changes (`catalog.everyday`). |
| `dungeon/world/data/names.json` | Name banks for residents, written by `scripts/world/names.py`. |
| `dungeon/world/data/given_names.json` | Popular given names by birth year, family names by culture and names that read as invented, written by `scripts/world/given_names.py` from `scripts/world/name_sources/`. |
| `dungeon/world/data/holidays.json` | Holiday calendars, written by `scripts/world/holidays.py`. |
| `dungeon/world/data/hobbies/` | Pastimes: `catalogue.json` (each pastime's words, eras, place, gear and fees) and one milestone bank per kind, checked by `tests/test_hobby_banks.py`. |
| `scripts/world/<city>.py` | The source each city's JSON is written from. Edit these, then rerun them. |

Nothing needs the network at run time. Every record names a source in its city's `sources` table
with kind, title, licence and retrieval date (`GET /api/world/cities/{id}/sources`). The current
records are curated from general knowledge and released as CC0; they are a snapshot for fiction,
not listings: businesses open and close, rents are rounded typical asking ranges and coordinates are
approximate. Each loaded city gets a `data_version` (a hash of its file) that generated results
carry, so an event can record exactly which data it was built from (PRD T7).

## Python API (for the life simulation)

```python
from dungeon.world import catalog, generators

data = catalog.city('kingswood')            # DomainError 404 for an unknown city
catalog.resolve('Kingswood')                # {'city': 'kingswood', 'neighborhood': None} or None
catalog.places(data, kind='museum', neighborhood='the-green', tag=None, good_for='date')
catalog.nearby(data, 'the-harbor', limit=4) # closest neighbourhoods
catalog.find(data, 'bluebird-diner') # any record by id

generators.conditions(data, day, seed)      # typical weather for the date, with a seeded rain chance
generators.annual_events(data, day)         # recurring events usually held that month
generators.holidays(data, start, end=None)  # holidays from start to end inclusive, each with its `date`
generators.commute(data, 'canton', 'towson', mode=None)
generators.outing(data, seed=..., day=..., day_part='evening', company='date',
                  neighborhood='fells-point', home='canton', budget='$$', kinds=None, exclude=[...])
generators.meal(data, seed=..., meal='brunch', neighborhood='hampden')
generators.job(data, 'registered-nurse', seed=..., home='canton', employer=None)  # employer: a record id
generators.schedule(career, seed)           # weekly routine blocks only
generators.home(data, seed=..., bedrooms='one_bedroom', budget=1400, vibe='arts', near='mount-vernon')
generators.facts(data, neighborhood='hampden')  # short lines to ground a prompt, including local colour
generators.local_color(data, seed=..., kinds=['dish'], day=..., count=3)  # dishes, sayings, customs, teams
generators.price(data, 'pint-of-beer', seed=...)  # one amount within the city's typical range

# People: the companion's social circle and anyone else in the city.
generators.circle(data, seed=..., size=6, home='canton', age=31, career='teacher', employer=None,
                  family=None, group=None)
generators.resident(data, seed=..., role='friend', career=None, age=None, near=None, employer=None,
                    family=None, group=None, local=True, pronouns=None)  # pronouns: whose side's work
generators.name(data, seed=..., pronouns=None, group=None, family=None)
```

**Seeds.** Choices come from SHA-256 of the seed, never from `random`, so they are identical on every
machine and Python version. Use a seed that is stable for the moment being simulated, such as the
routine slot key (`evening@2026-10-04`) plus the companion id, so a resumed batch picks the same
outing. Pass recently used place ids in `exclude` for variety.

**Results** are plain dictionaries. Every generator result includes `city`, `data_version`, `refs`
(ids of every record used) and `sources` (source ids those records cite), ready to store in an
event's generation inputs.

| Generator | Returns |
| --- | --- |
| `outing`, `meal` | `place` (full record), `neighborhood`, `day_part`, `company`, `weather` (when `day` is given), `travel` (a commute from `home` or `neighborhood`), plus `meal` for meals. `None` only when no place of the requested kinds exists. Constraints relax (day part, then company) rather than fail. Rain or extreme heat or cold strongly favours indoor places; seasonal places only appear in season. |
| `job` | Careers come from `catalog.careers_for(data)`: the shared ones for the city's era plus its own. Returns `career`, `employer` (`name`, `id`, `named`, `fit`), `neighborhood`, `schedule`, `commute` (when `home` is given). `fit` says how the employer was found: `employer` (a named employer for that career), `college` (students), `workplace` (a fitting place, such as a cafe for a barista or a tavern for a career in hospitality), `hub` (an unnamed workplace in a matching career hub) or `weak` (no matching sector in this city). Unnamed employers are described, never given invented names. |
| `schedule` | Routine blocks in the routine `schedule` shape: `work` (or `study`), `sleep`, `after-work` leisure when there is time, and `day-off` leisure. |
| `home` | `neighborhood`, `housing` type, `bedrooms`, `rent` within the neighbourhood's range and the budget (in the city's `currency` per `rent_period`), `rent_range`; both `null` where the setting has no rents. |
| `commute` | `mode`, `line` (transit name or `null`), `distance_km`, `minutes`; walking for short trips, a shared rail line, then a shared bus, then one change of line (`line` reads "A, then B", with `change: {at, name, lines}` and seven minutes added), then a car. All values are estimates. |
| `circle` | `family` (the companion's family name, given or chosen) and `people`, closest first: close friend, coworker, sibling, friend, parent, neighbor, friend, cousin, old classmate, friend, mentor, coworker (up to 12). Coworkers share the companion's `employer` (or `career` when only that is known; with neither there are no coworkers). Neighbors live in the `home` neighbourhood. Parents and siblings share the family name and heritage group; cousins do half the time. Relatives live out of town about 40% of the time. Ages sit around the companion's `age`. Names are unique within a circle. |
| `resident` | `id` (stable for the seed), `role`, `closeness` (`close`, `regular`, `occasional`), `name`, `age`, `local`, `home` (a `home` result), `job` (a `job` result with a commute from home, or `null` when retired at 67 or out of town), `schedule` (routine blocks like `job`'s; a simple retired day; `null` out of town) and `haunts` (up to three affordable cafes, bars, parks and the like near home). Feed `schedule` to the background simulation the same way as a companion's. |
| `name` | `given`, `family`, `full`, `pronouns` (`she/her`, `he/him` or `they/them`) and `group` (the heritage group drawn from). |
| `conditions` | `season`, `month`, `high_f`, `low_f`, `rain`, `note`, `typical: true` (monthly climate, not a forecast), or `None` for a city without a climate. |

**Names.** Each era has a bank of name groups (`GET /api/world/names`): modern American heritages,
Victorian Britain, a West Riding mill town, medieval England and Wales, the 1880s territories, and a
plain storybook set for fantasy. Cities can also pick banks for Edo Japan (`edo-japan`), Qing China
(`qing-china`), the Ottoman Empire (`ottoman`), ancient Rome (`ancient-rome`) and Mughal India
(`mughal-india`). Most of a resident's family names come from the same group as the
given name; one in five come from any group in the city. Real cities weight the groups by rough
local estimates in their `names.mix` (Miami leans Hispanic and Caribbean, Baltimore Black American).
A city may set `names` to pick another `bank`, weight groups with `mix`, or add its own `groups`
(`{"feminine": […], "masculine": […], "neutral": […], "family": […]}`); a city with its own groups and no
`mix` uses only those. Weights for groups a bank lacks are ignored, so changing a city's era keeps working. The modern bank includes `german` and
`french-canadian` (Québécois family names) groups; `anglo` stands for the city's local majority, so `{anglo: 1}`
gives Korean names in Jeju and Japanese names in Osaka. Pellmouth adds its own `portuguese` group this way.

**Names by birth year.** A group's `cultures` weights
(`{"us-black": 0.6, "local": 0.4}`) send the given name to what babies were actually called around the
person's birth year: `given_names.json` holds, per culture, the most popular names per birth year or
cohort, most popular first, and the generator samples a year up to three either side of
`present_year − age` and favours higher-ranked names. The present year is 2026 in modern and other
settings, 1895 for Victorian, 1890 for steampunk, 1885 for frontier, 1926 for the Jazz Age and 2077 for the future (`era_years`;
a city may set its own `names.year`); people born after the newest lists take the newest. Medieval and
fantasy settings have no birth-year lists and use their banks' own names. Victorian and frontier groups
take given names from England and Wales, Scotland, Ireland, Jewish diaspora, Italian, United States,
Mexican and German lists going back to the 1790s, but set `own_family` to keep their period family
names. The future mixes the modern groups from across the world rather than one country. `local` is the city's own country (`countries`
maps country names to cultures; the United States lists stand in elsewhere). A culture with its own
`surnames` (India, Korea, Mexico…) supplies the family name too, so a Korean given name never meets a
Japanese family name; a relative keeps the shared family name and draws from a culture that fits it. Polish and Russian
women take the feminine form (Kowalska, Ivanova).
Only family shares a family name. Someone drawn without one (`family` unset) never gets a name listed in
`avoid` or in the city data's `kin`: only the family name is drawn again, from the same seed, so their given
name and everyone else's name stay as they were. The life simulation's city (`dungeon/life/network.py`)
sets `kin` to the companion's family names and their relatives', so townsfolk, residents, newcomers and
friends of friends never share them; a circle's friends, coworkers and neighbors never share its `family`.
The world API's own city views (`/api/world/cities/...`) have no companion and show the plain draw.
The United States lists for 1880–2008 are the Social Security Administration's top 100 per year and sex
(`scripts/world/fetch_us_names.py`); 2009 onwards and every other culture (Black American and Hispanic
American trends, England and Wales, Ireland, Italy, Mexico, Spain, Germany, France, Poland, Russia,
China, Korea, Japan, Vietnam, the Philippines, India, Arabic-speaking countries, Nigeria, Ghana,
Jamaica, Haiti, Israel) were written from general knowledge of the published rankings because the
statistics offices are unreachable from the build machine, and are marked `estimate`, as are every
list before 1880. Most lists hold about 100 names per sex for each decade and 150 family names; their
tops follow published rankings where they could be read (Office for National Statistics, National Records
of Scotland and the Central Statistics Office Ireland through the CC0 `ukbabynames` data; INSEE's Fichier
des prénoms; national top lists for Spain, Italy, Poland, Korea, Japan and others; each file's `source`
line says which). Modern American family names follow the Census Bureau's 2000 surname table.

**Invented-sounding names.** `given_names.json` also lists names that read as made up by a language
model (Elara, Lyra, Kael, Vex, Voss, Thorne…; edit `name_sources/invented.txt`). No popular-name list
may contain one (validation fails), generators never produce one, and a pattern check also catches
the coined names a model reaches for that are not listed (Vaeryn, Kaelith, Duskmere, Ravencrest), while
any word found in a real list (Bronwyn, Mikael) passes.  `dungeon/world/naming.py`
checks model-written text for them: character drafting retries once naming the problem, then swaps
each one for an ordinary name; a name the user typed (or one in the world data) is always allowed. Chat
gets a short "names for anyone new" context section of ready-made names for the companion's city and a
spread of ages (`dungeon/world/newcomers.py`), so the model never has to invent one.

**Kinds and lifespans.** A name group may tie its people to a kind with `"kind": "elf"` (Grandport's `elven`
group does). Kinds and their average lifespans are in `lifespans.json` (Human 80, Elf 600, Half-elf 180, Doesn't age,
and the peoples of fantasy worlds below); a city may add a `kinds` block that changes a built-in kind's lifespan there
(`{"elf": {"lifespan": 750}}`) or adds a kind of its own (`{"cyclops": {"label": "Cyclops", "lifespan": 110,
"words": ["cyclops"]}}`). A lifespan is a whole number from 40 to 5000, or null for a kind that doesn't age; a bad
entry, or a group naming an unknown kind, is dropped with a note and the city still loads. Real ages stay as they
are; rules about how far through life someone is read their life age (`dungeon/world/lifespans.py`): their real
age through childhood, then adulthood stretched to their kind's lifespan, so an elf of 300 is 48 in human terms and
is seeded, retires, dates and passes away like it. A city file can only change how long adulthood lasts.

**The peoples of fantasy worlds.** `scripts/world/peoples.py` (run through `scripts/world/names.py`) writes 77
peoples into `lifespans.json` and the `peoples` name bank: beastkin (wolf-, dog-, fox-, coyote- and jackal-kin; cat-,
lynx-, lion-, tiger-, leopard- and panther-kin; naga, lamia, viper- and constrictor-kin; horse-, zebra-, donkey- and
unicorn-kin; cow-kin, bull-kin, minotaurs and buffalo-kin; rabbit- and hare-kin; deer-, elk-, stag- and moose-kin;
bear-kin; hawk-, owl-, corvid-, songbird- and waterfowl-kin; dragon- and wyrm-kin), fantasy humanoids (high, wood,
dark and sea elves, dwarves, orcs and half-orcs, goblins and hobgoblins, halflings and gnomes, ogres, trolls, giants
and half-giants, tieflings, succubi and incubi, the demon-blooded, merfolk and sea-kin) and other peoples (oni, tengu,
kappa, mind-eaters, centaurs, satyrs, dryads, fae, lizardfolk, kobolds, gnolls, the celestial- and djinn-blooded,
dhampirs, insectfolk, spider-kin, fungal folk and clockwork folk). Each kind carries `folk` and `type`
(Beastkin, Canids), which group it in the Kind picker. Each people has its own naming scheme, made from a small set
of sounds and endings or from clan words and titles and drawn from a fixed seed: at least 160 given names and 110
family names (titles for orcs, lizardfolk, mind-eaters and clockwork folk), with no name that reads as made up by a
model. Illithids and mind flayers are another company's creatures, so the people who eat minds are mind-eaters.

**How many people of each kind.** A kind in the city's `kinds` block can carry a `share`: the fraction of the
town's seeded townsfolk and residents of that kind, from 0 to 1 (`{"dwarf": {"share": 0.1}, "wolf-kin": {"share":
0.05}}`; a built-in kind can be listed with only a share). Humans are the rest; shares that add up past 1 are scaled
down, so nobody is human. A kind listed without a share gets 10% when no kind in the block has one (never more than
30% for all of them together), and none when another kind there does, so `"share": 0` and a missing share both mean
none in a block that sets shares (Haven's hidden folk are listed with `"share": 0`). Each person's kind is rolled
from their seed first, then their name group is drawn by `names.mix` weights from the groups tied to that kind, or
from the kind's own `groups` list, else from the `peoples` bank's group for that kind, else from the human groups;
their family name comes from their own kind's groups too. A kind may also weigh its own `pronouns` (`{"she": 0.8,
"he": 0.15, "they": 0.05}`); others keep the town's usual mix. A city with no `kinds` block draws from the whole mix
as before (Kingswood's halflings and half-elves come from its kind-tied name groups), and a city of other peoples alone can take `"bank": "peoples"` and weigh its groups in its mix. This is
the same format as Prospero's Companion's kinds by share. The narrator's scene line names anyone who isn't human
("Half-elf").

**Local colour.** Each city lists things locals eat, drink, say, root for and do (`local_color`, with
`kind` dish, drink, saying, custom, team, shop, legend, rumor or other), with the places they are easiest to find and
the seasons they belong to. `local_color` picks a few for a seed, in season on `day`, so the model can
mention crab feasts or a ventanita coffee without inventing them. Legends and rumours come back with
`hearsay: true` and reach prompts as "Local legend (hearsay locals tell, not confirmed fact): …", never as fact.

**A town's own townsfolk.** A city may add an optional `townsfolk` block with `quirks` and `goals` of its own
(Pellmouth's people keep the tide table pinned by the door); each is drawn five times as often as a single shared
one. Residents' and regulars' jobs follow the town: a career counts more when the city lists it, when its
employers hire for it (by employer size), when a career hub matches its sector and when fitting places exist, so a
quarry town has quarry workers rather than stockbrokers. Staff titles depend on the place as well as its kind (a
soda jerk only at a soda fountain, a floorwalker only at a department store, a ticket taker at a paid attraction).
A career can `need` a place kind or an employer that hires it (casino dealers need a casino).

**Prices.** Each city with money lists typical prices for everyday things (`prices`: coffee, a pint,
a fare, a week's groceries, a night's lodging) as `low`–`high` ranges in its own currency, with a
`per` note where needed. Historical settings use their own units (shillings with pence noted,
silver pennies, 1880s dollars, groschen). `facts()` includes them and `price()` picks one amount, so
the model never has to guess what something costs. Oz has no money and no prices.

**Holidays.** Each city keeps a shared calendar chosen from its era and country (`catalog.calendar_id`):
`us` for modern US cities, `uk` for modern United Kingdom cities (England and Wales), `south-korea` and `japan` for
modern cities there, `us-1920s` for Jazz Age US cities, `us-1880s` for the frontier, `uk-victorian` for Victorian
and steampunk England, `medieval-england` for medieval settings, and none otherwise (Oz has none). A city may name
another `calendar`, `'none'`, or add its own `holidays`. A holiday has one rule: `month` and `day`, a
`month`, `weekday` (Monday 0) and `nth` (-1 for the last), `easter` (days from Western Easter), or `dates` (a "MM-DD" date per year, for lunar holidays such as Seollal,
Chuseok and Buddha's Birthday, and Japan's equinox days; listed 2024-2040, after which they drop out rather
than guess).
`kind` is `public` (most offices and schools close), `observance` (widely marked, a working day) or
`feast` (a church feast or quarter day). Moved "observed" weekdays (substitute days off) are not included.

**Roads between towns.** `"home": false` marks a city that is somewhere to pass through, not to live: a world's
Road, Havenbrooke's "away from Haven" or BABEL's tower floors. The pickers for where someone lives (a new persona or
world, and moving home) leave it out; they pick a world first, then one of its towns (dungeon/worlds.py
`somewhere_new`, `somewhere-new:<world>`).

**Notables.** A city may name people who live in it (`notables`), such as a pack's characters: `id`,
`name`, optional `given` (what people call them), `pronouns`, `age`, the `place` they belong to, `role`,
`staff` (works there and keeps shifts, or only visits), `about` (who they are, one or two sentences),
optional `temperament` and `source`. They join that place's townsfolk after the seeded ones, keyed the
same way, and live by the same rules: days, goals, quirks and flaws are drawn from their key, while the
name, age, role and temperament are the city's. The companion meets them like anyone else, and what it
knows of them always includes `about`. A pack's notable placed
somewhere the city lacks is left out with a note. Notables stay in town for good unless `can_leave` is true, when
they can move away or retire like anyone else and a newcomer takes over their role.

**The town changes hands** (`dungeon/world/turnover.py`). Each spot a townsperson fills is held by one person
after another: from 19 October 2026 on, people move away, take other jobs, retire (staff, from their sixties) and,
with People can pass away on, pass away, at seeded yearly chances that follow their age, Life's big turns and Loss.
A newcomer takes the spot a few weeks later, keyed by the spot's number plus 1000 for each holder before them
(`town:<city>:<place>:1003`), so a key still names one person for good and someone who left is still found. Who is
at a place or on a street depends on the day; nothing is stored. The user's own townsperson and townsfolk who
became companions never leave. The paper reports departures, arrivals and town couples' babies.

Weather here is climate, not a forecast; a life event built from climate must not be presented as today's
weather.

### The composer's world source

`dungeon/world/source.py` provides `CatalogWorld`, the default world source the app passes to the
life engine (`dungeon/life/world.py`). It answers the composer's place kinds (`park`, `cafe`,
`waterfront`, `college` and so on) from this data, in a stable order. A character's `home_city` may
be a city id (`baltimore`) or free text that `catalog.resolve` recognises.
`places(city, kinds, *, day_part=None, day=None)` leaves out places closed at that part of the day
(`morning`, `afternoon`, `evening`, `late`) or out of season on that date. User cities and packs are
included. With `near=` (a neighborhood id, or the character's `location` text such as "Fells Point,
Baltimore"), everyday kinds (`cafe`, `restaurant`, `bar`, `market`, `grocery`, `library`, `gym`,
`park`) keep to places within 3 km of that neighborhood, or the nearest three, closest first, when fewer than two
are that close. Museums, venues, beaches and attractions stay city-wide.

### City changes

Cities change a little over time (`dungeon/world/changes.py`): a new cafe opens, a restaurant shuts for a
remodel, road works dig up a neighbourhood's main street, a favourite spot closes for good. Each month a city
gets at most one change of each kind (opening, closing, renovation, road works), decided by seeds from the city
id and the month, starting in October 2026 (a city visited on earlier dates, such as London in 1895, looks
back one year). The same city therefore changes the same way on every run and nothing has to be stored. People
hear of a change a few days before it happens (two weeks before a closing). Wording and new-place names come
from `dungeon/world/data/changes.json`, written by `scripts/world/changes.py`, in four styles chosen by era:
modern, Victorian (also steampunk), medieval (also fantasy), frontier and Jazz Age. A new place copies the hours,
setting and price level of one of the city's places of its kind and is tagged `new`.

In a real city, seeds only close or renovate places that opened through a change: the shipped places are real
businesses, and saying one closed would be a false claim about it. The user can still close any place there.
A closing never leaves a neighbourhood without somewhere to eat or drink.

`CatalogWorld.find(city, day)` returns the city as it stands that day, and `places(..., day=)` uses it, so every
generator sees the change: a closed place drops out of outings and haunts, a new one can be picked, and
neighbourhoods under road works carry `works`, which adds the works' delay to a `commute` by road (and lists
them under `works`). Changes are dated, so events composed before a change keep the place they happened at.
`CatalogWorld.changes(city, day)` lists every change heard of by that day.

The workspace keeps what a seed can't know (tables `world_changes` and `world_change_dismissals`): changes the
user adds and seeded changes the user dismisses (they never happen). Chat context gets one section, "Changes
around your city", with up to six recent, current or coming changes.

## HTTP API

Reads are `GET`s and need no workspace header. The [builder](#building-a-city) endpoints write and
need `x-dungeon-client: workspace`. Every `{id}` may be a built-in city or one of the user's.

| Endpoint | Returns |
| --- | --- |
| `/api/world/cities` | City summaries with record counts and `data_version` |
| `/api/world/cities/{id}` | The whole city record |
| `/api/world/cities/{id}/sources` | Source, licence and retrieval date for each cited source |
| `/api/world/cities/{id}/places?kind=&neighborhood=&tag=&good_for=` | Matching places |
| `/api/world/cities/{id}/conditions?day=YYYY-MM-DD&seed=` | `{"conditions": … \| null, "annual_events": […], "holidays": […]}` |
| `/api/world/cities/{id}/local-color?seed=&day=&kind=&count=` | All local colour, or a seeded pick when `seed` is given |
| `/api/world/cities/{id}/prices?item=&seed=` | `{"currency", "prices"}`, or one `price` with an `amount` when `item` and `seed` are given |
| `/api/world/cities/{id}/holidays?start=&end=` | `{"calendar": id \| null, "holidays": [… with "date"]}` (at most 400 days) |
| `/api/world/cities/{id}/careers` | Careers this city offers |
| `/api/world/cities/{id}/commute?from=&to=&mode=&day=` | A commute estimate; with `day`, road works that day add their delay |
| `/api/world/cities/{id}/changes?day=&days=60` | `{"day", "changes": [… with "active"]}`: changes heard of by `day` (the city's today by default) that start, run or end within `days` of it |
| `POST /api/world/cities/{id}/changes` | Add a change: `kind` (`opening`, `closing`, `renovation`, `roadworks`), `starts_on`, `ends_on` (renovation and road works), `place_id` (closing, renovation), `neighborhood` (opening, road works), `name` and `place_kind` (opening), optional `summary` and `delay`. The companion's upcoming plans from that day are recomposed |
| `DELETE /api/world/cities/{id}/changes/{change_id}` | Delete a change you added, or dismiss a seeded one |
| `/api/world/cities/{id}/generate/outing?seed=&day=&day_part=&company=&neighborhood=&home=&budget=&kind=&exclude=` | `{"outing": …}`; with `day`, from the city as it stands that day |
| `/api/world/cities/{id}/generate/meal?seed=&meal=&…` | `{"outing": …}` with `meal` |
| `/api/world/cities/{id}/generate/home?seed=&bedrooms=&budget=&vibe=&near=` | A home |
| `/api/world/cities/{id}/generate/job?career=&seed=&home=&employer=` | `employer` puts the job at that record |
| `/api/world/cities/{id}/generate/circle?seed=&size=&home=&age=&career=&employer=&family=&group=` | A social circle |
| `/api/world/cities/{id}/generate/resident?seed=&role=&career=&age=&near=&employer=&family=&group=&local=` | One person |
| `/api/world/names` | The name banks and each era's default |
| `/api/world/careers` | The career catalogue |
| `/api/world/resolve?text=` | `{"match": {"city", "neighborhood"} \| null}` for a free-text location |

## Building a city

Users' own cities are stored in the workspace database (`world_cities`), so backups carry them.
They are validated by the same schema as built-in cities and work with every generator and with
the life composer. The minimum is one source, one neighbourhood and one place.

In the app, **Settings → Cities** lists built-in, pack and user cities. From there you can start a
new city from the template, open a city file someone shared, copy any city, edit or delete your own
(as JSON, with **Check** before **Save**), save a public city as a file, and reload the pack folders.

| Endpoint | Does |
| --- | --- |
| `GET /api/world/template` | The smallest valid city, to start from scratch |
| `POST /api/world/validate` (body: a city) | `{"valid": true, …}`, or 422 with `detail` naming what is wrong |
| `POST /api/world/cities` (body: a city) | Saves a new city. 409 if the id is taken or belongs to a built-in city. |
| `POST /api/world/cities/{id}/copy` `{"id", "name"}` | Copies any city (built-in or the user's) as a new city of the user's |
| `PUT /api/world/cities/{id}` `{"definition", "expected_revision"}` | Replaces a user city; 409 when the revision is stale |
| `DELETE /api/world/cities/{id}` | Deletes a user city; 409 while the persona lives in that city |

**Forgiving loading.** User cities and packs are mended before validation (`dungeon/world/mend.py`)
so one slightly wrong word never stops a city loading; built-in cities are not, and their tests keep
them exact. What it does:

- Place kinds, college types, transit kinds, local colour kinds and source kinds are open lists. A new
  one (`bowling-alley`, `film-school`) is kept as written in id form. A place of a new kind turns up
  in general outings, townsfolk and dates but not where a specific kind is asked for (meals look for
  restaurants and cafes), so words that plainly mean a known kind are read as it: `diner` is a
  `restaurant`, `pub` a `bar`, `Metro` a `subway`.
- A career an employer names that the app lacks is added as the city's own career, named from its id.
- Words for the closed lists the generators reason about (cost, day parts, seasons, who a place is good
  for, setting, era, schedule, size) are read as the nearest known word (`cheap` is `$`, `Autumn` is
  `fall`, `night` is `late`, `all` is every value), and left out of a list when nothing is near.
- Ids are put in id form (`Echo Park` → `echo-park`), fields the app does not use are ignored, missing
  fields get defaults, unknown sources cite the first source, references to missing transit lines or
  places are dropped, and a place whose neighbourhood is not in the city (by id or name) is left out.

Each change is a sentence in `import_notes` on the save, check and pack responses (and in
`python -m dungeon.world.check` output as `adjusted:`), and Settings shows them after a save. The
saved definition is the mended one. Only a file that is not JSON or lacks a neighbourhood, a place or
an id still fails.

Built-in cities cannot be changed or deleted, only copied. A user city's `data_version` is a hash
of its content, so editing it changes the version later events record.

## City packs

A city pack is one city JSON file (the same schema) dropped into a pack folder. Packs load at start,
read-only like built-in cities (copy one to edit it), and can be personal or private: a pack marked
`"distribution": "private"` is meant for its owner only, such as fan cities of settings owned by
others. Pack folders:

- `Program/private-cities/` in the checkout (gitignored, so packs there are never committed)
- `city-packs/` in the workspace data directory (`%LOCALAPPDATA%\ProsperoDungeon\city-packs` on Windows, `~/Library/Application Support/ProsperoDungeon/city-packs` on macOS)
- or the folders in `DUNGEON_CITY_PACKS` (separated by `;` on Windows, `:` elsewhere), instead of both

`GET /api/world/packs` lists the folders, the packs loaded and any file that failed validation with
the reason; `POST /api/world/packs/reload` rereads them without restarting. A pack cannot reuse a
built-in city's id.

A city of your own that stops validating (saved under an older app's rules, or edited by hand in the
database) is left out of every list rather than failing them all, and is logged once.
`GET /api/world/broken-cities` returns each one with the reason and its saved definition; Settings >
Cities shows them with Save as file and Delete.

**Checking a city file.** `python -m dungeon.world.check [FILE_OR_FOLDER ...]` validates files
exactly as the app loads them (mending all but the built-in cities), and with no arguments checks the built-in cities and every pack
folder. Errors mean the file will not load. Warnings point out thin spots that make days there
repetitive: neighbourhoods with fewer than two places or nowhere to eat, no employers or career
hubs, or no climate. `--json` prints the results for tools. It exits 1 when any file has errors,
and CI runs it.

## Credits for settings in the test cities

**Grandport** (`tests/fixtures/cities/grandport.json`; the app no longer ships it) is set in **Neokosmos**, a world
by **Oak** (https://quietoak.github.io/NeokosmosWiki/). The Neokosmos wiki is licensed CC BY-NC-SA 4.0;
Prospero's Dungeon includes Grandport with Oak's permission (given 2026-10-10). The city, its people and
its lore are Oak's, not part of the app's AGPL-3.0 code, and are not relicensed by being shipped here.
Records citing `wiki` come from the wiki; records citing `inferred` were filled in for the app in the
setting's voice. Oak's characters appear in town as `notables`.

## Adding or refreshing a built-in city

1. Copy `scripts/world/kingswood.py`, keep its source records, and fill in the city.
2. Run it to write `dungeon/world/data/cities/<id>.json`, then `python -m pytest tests/test_world.py`.
   The tests validate every reference, check every career gets a job and every generated schedule
   is a valid character routine.
3. Only add places you know are open, and prefer long-running institutions to new openings.
