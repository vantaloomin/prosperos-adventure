"""Holiday calendars for Prospero Dungeon. Run `python scripts/world/holidays.py` to rewrite the shipped JSON.

Each holiday has one rule: a fixed date (`month`, `day`), the nth weekday of a month (`month`, `weekday` with
Monday 0, `nth` with -1 for the last), a number of days from Western Easter (`easter`), or a table of dates by year
(`dates`, "MM-DD" by year) for holidays on the lunar calendar or set by the sun. `kind` is `public` (most offices
and schools close), `observance` (widely marked, a normal working day) or `feast` (a church feast or quarter day of
the period).
"""
import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'dungeon' / 'world' / 'data' / 'holidays.json'
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)


def fixed(id, name, month, day, kind, summary):
    return {'id': id, 'name': name, 'kind': kind, 'month': month, 'day': day, 'summary': summary}


def nth(id, name, month, weekday, n, kind, summary):
    return {'id': id, 'name': name, 'kind': kind, 'month': month, 'weekday': weekday, 'nth': n, 'summary': summary}


def easter(id, name, offset, kind, summary):
    return {'id': id, 'name': name, 'kind': kind, 'easter': offset, 'summary': summary}


def table(id, name, days, kind, summary, shift=0):
    """A holiday by a table of dates ({year: date}), moved `shift` days (the day before Seollal is -1)."""
    dates = {str(year): (day + timedelta(days=shift)).strftime('%m-%d') for year, day in sorted(days.items())}
    return {'id': id, 'name': name, 'kind': kind, 'dates': dates, 'summary': summary}


# Lunar-calendar dates in Korea for 2024-2040, from the Korea Astronomy and Space Science Institute's lunar
# conversion tables (Korean Standard Time, so Seollal can fall a day after Chinese New Year, as in 2027).
YEARS = range(2024, 2041)
SEOLLAL = ('02-10 01-29 02-17 02-07 01-27 02-13 02-03 01-23 02-11 01-31 02-19 02-08 01-28 02-15 02-04 01-24 '
           '02-12').split()
BUDDHA = ('05-15 05-05 05-24 05-13 05-02 05-20 05-09 05-28 05-16 05-06 05-25 05-15 05-03 05-22 05-11 04-30 '
          '05-18').split()
CHUSEOK = ('09-17 10-06 09-25 09-15 10-03 09-22 09-12 10-01 09-19 09-08 09-27 09-16 10-04 09-24 09-13 10-02 '
           '09-21').split()


def lunar(days):
    return {year: date.fromisoformat(f'{year}-{day}') for year, day in zip(YEARS, days, strict=True)}


def equinox(year, base):
    """The day of the March (base 20.8431) or September (base 23.2488) equinox in Japan, by the Japanese
    almanac's formula for 1980-2099; the Cabinet confirms it each February."""
    return int(base + 0.242194 * (year - 1980) - (year - 1980) // 4)


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


VERNAL = {year: date(year, 3, equinox(year, 20.8431)) for year in YEARS}
AUTUMNAL = {year: date(year, 9, equinox(year, 23.2488)) for year in YEARS}
# A day between two holidays is a holiday too: in some years Respect for the Aged Day and the autumn equinox
# are two days apart, and the day between them makes a five-day "Silver Week".
SILVER_WEEK = {year: day - timedelta(days=1) for year, day in AUTUMNAL.items()
               if (day - nth_weekday(year, 9, 0, 3)).days == 2}


US = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'public', 'A slow day after the night before; most things closed.'),
    nth('mlk-day', 'Martin Luther King Jr. Day', 1, MON, 3, 'public', 'Federal holiday with days of service and '
        'marches; schools and government offices close.'),
    fixed('valentines-day', "Valentine's Day", 2, 14, 'observance', 'Restaurants book up; cards and flowers.'),
    nth('presidents-day', "Presidents' Day", 2, MON, 3, 'public', 'Federal holiday; government offices and many '
        'schools close, and stores run sales.'),
    fixed('st-patricks-day', "St. Patrick's Day", 3, 17, 'observance', 'Green beer, parades and crowded pubs.'),
    easter('easter', 'Easter Sunday', 0, 'observance', 'Church services, egg hunts and family brunch.'),
    nth('mothers-day', "Mother's Day", 5, SUN, 2, 'observance', 'Brunch reservations and calls home.'),
    nth('memorial-day', 'Memorial Day', 5, MON, -1, 'public', 'The unofficial start of summer: cookouts, beaches and '
        'remembrance of the war dead.'),
    nth('fathers-day', "Father's Day", 6, SUN, 3, 'observance', 'Cookouts and calls home.'),
    fixed('juneteenth', 'Juneteenth', 6, 19, 'public', 'Marks the end of slavery in the United States; festivals '
          'and cookouts.'),
    fixed('independence-day', 'Independence Day', 7, 4, 'public', 'Fireworks, cookouts and a day off.'),
    nth('labor-day', 'Labor Day', 9, MON, 1, 'public', 'The unofficial end of summer and a long weekend.'),
    fixed('halloween', 'Halloween', 10, 31, 'observance', 'Costumes, trick-or-treating and parties.'),
    fixed('veterans-day', 'Veterans Day', 11, 11, 'public', 'Federal holiday; government offices and banks close.'),
    nth('thanksgiving', 'Thanksgiving', 11, THU, 4, 'public', 'A big family meal, football and travel; most '
        'things close.'),
    fixed('christmas-eve', 'Christmas Eve', 12, 24, 'observance', 'Last-minute shopping and family gatherings; many '
          'offices close early.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'public', 'Presents and family; almost everything closes.'),
    fixed('new-years-eve', "New Year's Eve", 12, 31, 'observance', 'Parties and countdowns at midnight.'),
]

US_1880S = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'public', 'Calls on friends and an open house in the parlour.'),
    fixed('washingtons-birthday', "Washington's Birthday", 2, 22, 'public', 'Speeches, a ball and a day off for '
          'banks and offices.'),
    easter('easter', 'Easter Sunday', 0, 'observance', 'Church in new clothes and a big dinner after.'),
    fixed('decoration-day', 'Decoration Day', 5, 30, 'public', 'Veterans and townsfolk decorate soldiers\' graves '
          'with flowers, with a procession and speeches.'),
    fixed('independence-day', 'Independence Day', 7, 4, 'public', 'The biggest day of the year: parade, oration, '
          'races, a barbecue and fireworks.'),
    nth('thanksgiving', 'Thanksgiving Day', 11, THU, -1, 'public', 'Proclaimed each year for the last Thursday of '
        'November: church, turkey and a shooting match.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'public', 'Church, a tree, presents and a big dinner.'),
]

UK_VICTORIAN = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'observance', 'Not a holiday in England; Scots keep Hogmanay.'),
    fixed('lady-day', 'Lady Day', 3, 25, 'feast', 'A quarter day: rents fall due and servants\' terms change.'),
    easter('shrove-tuesday', 'Shrove Tuesday', -47, 'observance', 'Pancake day, with football in some towns.'),
    easter('good-friday', 'Good Friday', -2, 'public', 'Shops shut, hot cross buns and church.'),
    easter('easter', 'Easter Sunday', 0, 'observance', 'Church and a family dinner.'),
    easter('easter-monday', 'Easter Monday', 1, 'public', 'A bank holiday: excursion trains, fairs and Hampstead '
           'Heath crowded with day-trippers.'),
    fixed('queens-birthday', "The Queen's Birthday", 5, 24, 'observance', 'Flags, a royal salute and, in the '
          'colonies, a holiday.'),
    easter('whit-monday', 'Whit Monday', 50, 'public', 'A bank holiday: Whit walks, Sunday-school treats and '
           'excursions.'),
    fixed('midsummer-day', 'Midsummer Day', 6, 24, 'feast', 'A quarter day when rents fall due.'),
    nth('august-bank-holiday', 'August Bank Holiday', 8, MON, 1, 'public', 'The first Monday in August: seaside '
        'trips, crowded trains and fairs.'),
    fixed('michaelmas', 'Michaelmas', 9, 29, 'feast', 'A quarter day; goose for dinner and hiring fairs.'),
    fixed('bonfire-night', 'Guy Fawkes Night', 11, 5, 'observance', 'Bonfires, guys carried through the streets '
          'and fireworks.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'public', 'Church, a goose or a joint, plum pudding and family.'),
    fixed('boxing-day', 'Boxing Day', 12, 26, 'public', 'A bank holiday: Christmas boxes for tradesmen and '
          'servants, and the pantomime season opens.'),
]

US_1920S = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'public', 'Hangovers from the night before, calls on family and '
          'a quiet city until noon.'),
    fixed('lincolns-birthday', "Lincoln's Birthday", 2, 12, 'observance', 'A legal holiday in New York and much of '
          'the North: banks and schools close there, flags fly and veterans of the Union march.'),
    fixed('valentines-day', "Valentine's Day", 2, 14, 'observance', 'Penny cards and lace valentines, boxes of '
          'chocolates and a dance or two.'),
    fixed('washingtons-birthday', "Washington's Birthday", 2, 22, 'public', 'Banks, offices and schools close; '
          'cherry pie, store sales and patriotic speeches.'),
    fixed('st-patricks-day', "St. Patrick's Day", 3, 17, 'observance', 'The parade up Fifth Avenue and green '
          'carnations, with Prohibition doing little to keep anyone dry.'),
    easter('easter', 'Easter Sunday', 0, 'observance', 'Church in new spring hats, then the Easter Parade along '
           'the avenue to see and be seen.'),
    nth('mothers-day', "Mother's Day", 5, SUN, 2, 'observance', 'A white carnation worn for mother, a card home '
        'and Sunday dinner.'),
    fixed('decoration-day', 'Decoration Day', 5, 30, 'public', 'Graves decorated with flowers and flags for the '
          'dead of the Civil War and the Great War; parades, then the first trips to the shore.'),
    fixed('independence-day', 'Independence Day', 7, 4, 'public', 'Firecrackers, parades, picnics, ball games and '
          'packed beaches.'),
    nth('labor-day', 'Labor Day', 9, MON, 1, 'public', 'Union parades and picnics, and the end of straw-hat season.'),
    fixed('columbus-day', 'Columbus Day', 10, 12, 'public', 'A state holiday in New York, Massachusetts and most '
          'of the Northeast; Italian societies march with bands and banners.'),
    fixed('halloween', "Hallowe'en", 10, 31, 'observance', 'Masquerade parties, bobbing for apples, fortune games '
          'and boys up to pranks after dark.'),
    fixed('armistice-day', 'Armistice Day', 11, 11, 'public', 'Two minutes of silence at the eleventh hour, then '
          'parades of Great War veterans; a legal holiday in most states.'),
    nth('thanksgiving', 'Thanksgiving Day', 11, THU, -1, 'public', 'The last Thursday of November: turkey, family, '
        'the big college football games and the department-store parade.'),
    fixed('christmas-eve', 'Christmas Eve', 12, 24, 'observance', 'Last shopping at the department stores, carols '
          'and midnight Mass.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'public', 'Church, a tree with electric lights, presents and a big '
          'dinner; almost everything closes.'),
    fixed('new-years-eve', "New Year's Eve", 12, 31, 'observance', 'Times Square crowds, noisemakers, hotel '
          'ballrooms and speakeasies packed until dawn.'),
]

UK = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'public', 'A bank holiday: a slow, hungover day, a walk and the '
          'football.'),
    fixed('valentines-day', "Valentine's Day", 2, 14, 'observance', 'Restaurants book up; cards, roses and set '
          'menus.'),
    easter('pancake-day', 'Pancake Day (Shrove Tuesday)', -47, 'observance', 'Pancakes with lemon and sugar, and '
           'pancake races in some towns.'),
    easter('mothering-sunday', 'Mothering Sunday', -21, 'observance', 'Flowers, cards and Sunday lunch out with '
           'mum; pubs and restaurants are full.'),
    fixed('st-patricks-day', "St Patrick's Day", 3, 17, 'observance', 'Guinness, parades and crowded Irish pubs.'),
    easter('good-friday', 'Good Friday', -2, 'public', 'A bank holiday: hot cross buns and the start of a four-day '
           'weekend.'),
    easter('easter', 'Easter Sunday', 0, 'observance', 'Chocolate eggs, egg hunts, church for some and a roast '
           'lunch.'),
    easter('easter-monday', 'Easter Monday', 1, 'public', 'A bank holiday in England and Wales: garden centres, '
           'DIY and day trips.'),
    fixed('st-georges-day', "St George's Day", 4, 23, 'observance', "England's saint's day: a few flags and the "
          'odd pub event, and an ordinary working day.'),
    nth('early-may-bank-holiday', 'Early May bank holiday', 5, MON, 1, 'public', 'A long weekend: May Day fairs, '
        'morris dancing and the first barbecues.'),
    nth('spring-bank-holiday', 'Spring bank holiday', 5, MON, -1, 'public', 'A long weekend at the end of May: '
        'traffic to the coast and half-term for schools.'),
    nth('fathers-day', "Father's Day", 6, SUN, 3, 'observance', 'Cards, a pub lunch and socks.'),
    nth('summer-bank-holiday', 'Summer bank holiday', 8, MON, -1, 'public', "The last long weekend of summer in "
        'England and Wales: festivals, Notting Hill Carnival in London and packed beaches.'),
    fixed('halloween', 'Halloween', 10, 31, 'observance', 'Costumes, trick-or-treating and fancy-dress parties.'),
    fixed('bonfire-night', 'Bonfire Night', 11, 5, 'observance', 'Guy Fawkes Night: bonfires, fireworks displays '
          'in the parks, sparklers and toffee apples.'),
    fixed('armistice-day', 'Armistice Day', 11, 11, 'observance', "Two minutes' silence at 11 a.m. and poppies "
          'on coats.'),
    nth('remembrance-sunday', 'Remembrance Sunday', 11, SUN, 2, 'observance', 'Wreaths laid at the Cenotaph and war '
        "memorials, and two minutes' silence at eleven."),
    fixed('christmas-eve', 'Christmas Eve', 12, 24, 'observance', 'Last-minute shopping, the pub with friends from '
          'home and midnight Mass.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'public', "Presents, crackers, turkey, the King's speech at three "
          'and almost everything shut, trains included.'),
    fixed('boxing-day', 'Boxing Day', 12, 26, 'public', 'A bank holiday: leftovers, the sales, football and a long '
          'walk.'),
    fixed('new-years-eve', "New Year's Eve", 12, 31, 'observance', 'Parties, the fireworks over the river at '
          'midnight and Auld Lang Syne.'),
]

SOUTH_KOREA = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'public', 'Sinjeong: watching the first sunrise of the year from '
          'a beach or peak, and tteokguk.'),
    table('seollal-eve', 'Seollal holiday', lunar(SEOLLAL), 'public', 'The day before Lunar New Year: the great '
          'traffic jam out of the cities and cooking jeon at home.', shift=-1),
    table('seollal', 'Seollal (Lunar New Year)', lunar(SEOLLAL), 'public', 'Ancestral rites, tteokguk, deep bows '
          'to elders for sebae money and games of yut; most shops close.'),
    table('seollal-after', 'Seollal holiday', lunar(SEOLLAL), 'public', 'The last day of the New Year holiday: '
          'visiting the other side of the family and the drive home.', shift=1),
    fixed('valentines-day', "Valentine's Day", 2, 14, 'observance', 'Women give men chocolate; cafes and '
          'convenience stores are stacked with gift boxes.'),
    fixed('samiljeol', 'Samiljeol (Independence Movement Day)', 3, 1, 'public', 'Marks the 1919 independence '
          'protests: flags on balconies and ceremonies.'),
    fixed('white-day', 'White Day', 3, 14, 'observance', 'Men return the favour with candy, flowers and dinner.'),
    fixed('black-day', 'Black Day', 4, 14, 'observance', 'Singles without a valentine meet for black-bean '
          'jajangmyeon, half joking.'),
    fixed('workers-day', "Workers' Day", 5, 1, 'observance', 'Many companies give the day off; schools and '
          'government offices stay open.'),
    fixed('childrens-day', "Children's Day", 5, 5, 'public', 'Parks, zoos and amusement parks packed with '
          'families; presents for the kids.'),
    fixed('parents-day', "Parents' Day", 5, 8, 'observance', 'Red carnations pinned on parents, a meal out and '
          'an envelope of money.'),
    table('buddhas-birthday', "Buddha's Birthday", lunar(BUDDHA), 'public', 'Lanterns strung through temple '
          'courtyards and the streets; free temple bibimbap.'),
    fixed('teachers-day', "Teachers' Day", 5, 15, 'observance', 'Students thank teachers with carnations and '
          'letters.'),
    fixed('memorial-day', 'Memorial Day', 6, 6, 'public', 'Hyeonchungil: a siren at 10 a.m. and a minute of '
          'silence for the war dead; flags at half-mast.'),
    fixed('constitution-day', 'Constitution Day', 7, 17, 'observance', 'Jeheonjeol, marking the 1948 '
          'constitution: flags out, ceremonies.'),
    fixed('liberation-day', 'Liberation Day', 8, 15, 'public', 'Gwangbokjeol, the end of Japanese rule in 1945: '
          'flags, ceremonies and bells.'),
    table('chuseok-eve', 'Chuseok holiday', lunar(CHUSEOK), 'public', 'The day before Chuseok: the exodus to '
          'hometowns, and songpyeon made together.', shift=-1),
    table('chuseok', 'Chuseok', lunar(CHUSEOK), 'public', 'The harvest moon festival: ancestral rites, tending '
          'family graves, songpyeon and family gift sets.'),
    table('chuseok-after', 'Chuseok holiday', lunar(CHUSEOK), 'public', 'The last day of the Chuseok holiday and '
          'the long drive back.', shift=1),
    fixed('gaecheonjeol', 'Gaecheonjeol (National Foundation Day)', 10, 3, 'public', 'The legendary founding of '
          'Gojoseon by Dangun; a quiet day off.'),
    fixed('hangul-day', 'Hangul Day', 10, 9, 'public', 'Celebrates the Korean alphabet: exhibitions and a day '
          'off.'),
    fixed('halloween', 'Halloween', 10, 31, 'observance', 'Costume parties in the clubbing districts.'),
    fixed('pepero-day', 'Pepero Day', 11, 11, 'observance', 'Boxes of chocolate-dipped Pepero sticks traded '
          'between friends and couples.'),
    fixed('christmas-eve', 'Christmas Eve', 12, 24, 'observance', 'A couples\' night: booked-out restaurants, '
          'cakes and lit-up streets.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'public', 'A day off spent as a couple or with friends more than '
          'family; church for some.'),
    fixed('new-years-eve', "New Year's Eve", 12, 31, 'observance', 'The Bosingak bell rung at midnight, and '
          'countdowns.'),
]

JAPAN = [
    fixed('new-years-day', "New Year's Day", 1, 1, 'public', "Ganjitsu: the first shrine visit, osechi boxes, "
          "nengajo cards in the post and offices shut."),
    fixed('new-year-2', 'New Year holiday', 1, 2, 'public', 'Offices and banks stay shut; department stores open '
          'with fukubukuro lucky bags.'),
    fixed('new-year-3', 'New Year holiday', 1, 3, 'public', 'The last day of the New Year break: Hakone Ekiden on '
          'TV and the trip back to the city.'),
    nth('coming-of-age-day', 'Coming of Age Day', 1, MON, 2, 'public', 'Twenty-year-olds in furisode and suits at '
        'city ceremonies, then out drinking.'),
    fixed('setsubun', 'Setsubun', 2, 3, 'observance', 'Beans thrown to drive out demons and an ehomaki roll eaten '
          'in silence facing the lucky direction.'),
    fixed('national-foundation-day', 'National Foundation Day', 2, 11, 'public', 'Kenkoku Kinen no Hi: a quiet '
          'day off.'),
    fixed('valentines-day', "Valentine's Day", 2, 14, 'observance', 'Women give chocolate: honmei for a crush, '
          'giri for coworkers.'),
    fixed('emperors-birthday', "Emperor's Birthday", 2, 23, 'public', 'A day off; the palace opens for the '
          "Emperor's greeting."),
    fixed('hinamatsuri', 'Hinamatsuri', 3, 3, 'observance', "Girls' Day: tiered doll displays, chirashi sushi and "
          'pink amazake.'),
    fixed('white-day', 'White Day', 3, 14, 'observance', 'A month after Valentine\'s, men return gifts, '
          'supposedly three times the value.'),
    table('vernal-equinox-day', 'Vernal Equinox Day', VERNAL, 'public', "Shunbun no Hi: family graves visited for "
          'higan, and the first cherry blossom forecasts.'),
    fixed('showa-day', 'Showa Day', 4, 29, 'public', 'Golden Week begins: trains and airports fill.'),
    fixed('constitution-memorial-day', 'Constitution Memorial Day', 5, 3, 'public', 'Golden Week: crowded resorts, '
          'festivals and queues everywhere.'),
    fixed('greenery-day', 'Greenery Day', 5, 4, 'public', 'Golden Week: parks and gardens full.'),
    fixed('childrens-day', "Children's Day", 5, 5, 'public', 'The end of Golden Week: koinobori carp streamers and '
          'kashiwa mochi.'),
    fixed('tanabata', 'Tanabata', 7, 7, 'observance', 'Wishes written on paper strips hung on bamboo, for the '
          'star-crossed lovers.'),
    nth('marine-day', 'Marine Day', 7, MON, 3, 'public', 'Umi no Hi: the beaches open and summer starts in '
        'earnest.'),
    fixed('mountain-day', 'Mountain Day', 8, 11, 'public', 'Yama no Hi: a day off at the start of the Obon '
          'season.'),
    fixed('obon', 'Obon', 8, 13, 'observance', 'Ancestors welcomed home for four days: trips to hometowns, bon '
          'odori dances and lanterns; many businesses close for the week.'),
    nth('respect-for-the-aged-day', 'Respect for the Aged Day', 9, MON, 3, 'public', 'Keiro no Hi: visits and '
        'gifts for grandparents.'),
    table('citizens-holiday', "Citizens' Holiday", SILVER_WEEK, 'public', 'A day off sandwiched between two '
          'holidays, making a five-day Silver Week.'),
    table('autumnal-equinox-day', 'Autumnal Equinox Day', AUTUMNAL, 'public', 'Shubun no Hi: graves tended for '
          'autumn higan and ohagi rice cakes.'),
    nth('sports-day', 'Sports Day', 10, MON, 2, 'public', 'Supotsu no Hi: school and neighbourhood sports days, '
        'relays and tug-of-war.'),
    fixed('halloween', 'Halloween', 10, 31, 'observance', 'Costumed crowds in the nightlife districts and on the '
          'trains.'),
    fixed('culture-day', 'Culture Day', 11, 3, 'public', 'Bunka no Hi: museums, school culture festivals and '
          'awards.'),
    fixed('shichi-go-san', 'Shichi-Go-San', 11, 15, 'observance', 'Children of three, five and seven dressed up '
          'for shrine visits and photos, with chitose-ame candy.'),
    fixed('labour-thanksgiving-day', 'Labour Thanksgiving Day', 11, 23, 'public', 'Kinro Kansha no Hi: a day off '
          'and the first year-end parties.'),
    fixed('christmas-eve', 'Christmas Eve', 12, 24, 'observance', 'The date night of the year: illuminations, '
          'booked restaurants, Christmas cake and fried chicken.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'observance', 'An ordinary working day; the decorations come down '
          'for the New Year pine.'),
    fixed('new-years-eve', "New Year's Eve", 12, 31, 'public', 'Omisoka: offices shut from the 29th, toshikoshi '
          'soba, Kohaku on TV and temple bells rung 108 times at midnight.'),
]

MEDIEVAL = [
    fixed('twelfth-night', 'Twelfth Night', 1, 5, 'feast', 'The last night of Christmas: a bean in the cake makes a '
          'king for the evening.'),
    fixed('epiphany', 'Epiphany', 1, 6, 'feast', 'The end of the twelve days of Christmas.'),
    nth('plough-monday', 'Plough Monday', 1, MON, 2, 'observance', 'Ploughboys drag a decorated plough round the '
        'town begging for pennies before work starts again.'),
    fixed('candlemas', 'Candlemas', 2, 2, 'feast', 'Candles blessed in church and carried in procession.'),
    easter('shrove-tuesday', 'Shrove Tuesday', -47, 'feast', 'Feasting, cock-throwing and football before Lent.'),
    easter('ash-wednesday', 'Ash Wednesday', -46, 'feast', 'Lent begins: no meat until Easter.'),
    fixed('lady-day', 'Lady Day', 3, 25, 'feast', 'The Annunciation and the start of the year; a quarter day.'),
    easter('palm-sunday', 'Palm Sunday', -7, 'feast', 'Procession with yew and willow for palms.'),
    easter('good-friday', 'Good Friday', -2, 'feast', 'Creeping to the cross; a day of fasting.'),
    easter('easter', 'Easter Day', 0, 'feast', 'Lent ends: meat, eggs and ale, and a day free of work.'),
    easter('hock-monday', 'Hock Monday', 8, 'observance', 'The women of the town rope the men and let them go for a '
           'forfeit; the men return the favour next day.'),
    fixed('may-day', 'May Day', 5, 1, 'observance', 'Bringing in the may at dawn, a maypole and dancing.'),
    easter('ascension', 'Ascension Day', 39, 'feast', 'Beating the bounds of the parish.'),
    easter('whitsun', 'Whitsunday (Pentecost)', 49, 'feast', 'A great feast; the king holds court and church ales '
           'are brewed.'),
    fixed('midsummer-eve', "St John's Eve", 6, 23, 'feast', 'Bonfires on the hills and watch fires in the town.'),
    fixed('lammas', 'Lammas', 8, 1, 'feast', 'Loaf-mass: bread from the first wheat blessed in church.'),
    fixed('michaelmas', 'Michaelmas', 9, 29, 'feast', 'Rents and reeves\' accounts due, and a goose for dinner.'),
    fixed('all-hallows', 'All Hallows', 11, 1, 'feast', 'Bells rung for the dead through the night before.'),
    fixed('martinmas', 'Martinmas', 11, 11, 'feast', 'Beasts slaughtered and salted for winter; a feast of fresh '
          'meat.'),
    fixed('christmas', 'Christmas Day', 12, 25, 'feast', 'Twelve days of feasting, games and no work in the fields.'),
]

HOLIDAYS = {
    'schema_version': 1,
    'source': {'kind': 'curated', 'title': 'Holiday calendars written for Prospero Dungeon', 'license': 'CC0-1.0',
               'retrieved': '2026-10-05',
               'note': 'Public holidays and observances from general knowledge. Moved weekend dates ("observed" '
                       'and substitute days) are not included. Korean lunar holidays follow KASI tables and '
                       "Japan's equinox days the almanac formula, for 2024-2040."},
    'calendars': {
        'us': {'name': 'United States (current)', 'holidays': US},
        'uk': {'name': 'United Kingdom (England and Wales, current)', 'holidays': UK},
        'south-korea': {'name': 'South Korea (current)', 'holidays': SOUTH_KOREA},
        'japan': {'name': 'Japan (current)', 'holidays': JAPAN},
        'us-1920s': {'name': 'United States in the 1920s', 'holidays': US_1920S},
        'us-1880s': {'name': 'United States in the 1880s', 'holidays': US_1880S},
        'uk-victorian': {'name': 'England in the 1890s', 'holidays': UK_VICTORIAN},
        'medieval-england': {'name': 'Medieval England', 'holidays': MEDIEVAL},
    },
}

if __name__ == '__main__':
    OUT.write_text(json.dumps(HOLIDAYS, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
