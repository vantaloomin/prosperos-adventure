"""The playtest scenarios: the milestones' "done when" lists (docs/roadmap.md), played as a player would.

Each is a function of a `Play` (playtest.py). Lines are what a player types; `expect` adds checks.
"""
import json


def town(play):
    """M1: a premade in Kingswood, talking to people, the Heartwood contract, and what the character knows."""
    play.start('agna-holt')
    play.say('I take a seat near the fire and look around the room, taking in who is drinking here tonight.',
             {'no_roll': True})
    play.say('"Evening," I say to whoever is behind the bar. "Ale, and whatever you hear about this contract on '
             'the green."')
    play.say('I ask the barkeep who in town would know the most about the Heartwood, and why the guild pays double.')
    play.people()
    play.move('the-green')
    play.say('I read the notice posted on the green, all of it, and check who has signed so far.')
    play.move('guild-factor')
    play.say('I tell the factor I want to sign on for the Heartwood crews, and ask what the grey-fletched arrows '
             'mean.')
    play.say('I lean on him: "Somebody is threatening your crews. Tell me what you know or find another sword."',
             {'roll': True})
    play.journal()
    play.say('OOC: what quests does my character know about right now?', {'no_roll': True})


def shop(play):
    """M1: inventory and the one shop: the counter, buying in the window and in the story, haggling, selling."""
    play.start('tobin-pell')
    play.move('pell-provisions')
    play.gear()
    play.say('I look over the shelves and ask what a coil of rope and a lantern would cost me.', {'no_roll': True})
    play.say('I haggle hard over the lantern, reminding the keeper I am family and that the Guild pays late.',
             {'roll': True})
    play.gear()
    play.say('I buy the lantern and two loaves of bread.')
    play.gear()
    play.buy('rope')
    play.say('I try to haggle again on the rope, since it went so well last time.')
    play.say('I sell my ledger book back over the counter.')
    play.gear()
    play.say('I pocket a candle from the shelf while the keeper is turned away.', {'roll': True})
    play.gear()
    play.journal()


def heartwood(play):
    """M1: into the dangerous place, a fight, getting hurt, and going back to try again with new dice."""
    play.start('agna-holt')
    play.move('border-stones')
    play.say('I wait by the border stones a while and watch the far bank for any sign of the wardens.')
    play.move('the-heartwood')
    for line in ('I push on into the Heartwood along the old trail, sword unwrapped and ready.',
                 'I go deeper, looking for the oldest trees, the ones the guild means to fell.',
                 'I keep going, marking the bark with my knife so I can find my way back.',
                 'I press on toward the hum in the ground.'):
        view = play.say(line)
        if view and (view.get('fight') or {}).get('fight'):
            break
    for line in ('I go for the nearest one with my sword, low and fast.',
                 'I hack at it again, putting my weight behind the swing.',
                 'I keep fighting, aiming for the throat.',
                 'I swing again.',
                 'I fight on.'):
        view = play.say(line)
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    play.journal()
    draft = play.back(3)
    play.say(draft)
    play.say('I turn back toward the stones before it gets worse.')


def brawl(play):
    """M1: starting a fight with a named person in town, morale and the defeat table, and death with going back."""
    play.start('tobin-pell')
    play.move('the-sawpit')
    play.say('I look around for the biggest logger in the place.')
    play.say('I throw my drink in his face and punch him.', {'fight': True})
    for line in ('I punch him again.', 'I kick at his knee.', 'I try to bite his ear.', 'I keep swinging.',
                 'I swing wildly.', 'I keep at it.'):
        view = play.say(line)
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    play.say('I pick myself up and check what I have left.')
    play.gear()
    play.say('I bandage my cuts as best I can.')
    play.say('I find somewhere quiet to sleep it off.')
    play.journal()


def road(play):
    """M2: travel with fog of war, road encounters, food, rest in the open and in town, wounds mending."""
    play.start('lirien-of-the-ford')
    play.say('OOC: where can my character travel from here?', {'no_roll': True})
    play.say('I set out for Convila along the forest road.', {'place': None})
    play.gear()
    play.say('I look around Convila and ask who is buying salt.')
    play.say('We make camp outside the town walls for the night, no fire, and I keep a watch.')
    play.say('I set out for the Abandoned Keep.')
    play.say('I make camp in the ruins for the night.')
    play.say('I search the ruins of the keep for anything worth carrying.')
    play.say('I take everything I found.')
    play.gear()
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        # Dead at the keep: go back to before the keep so the road home still plays.
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'Abandoned Keep' in line['text']))
        play.say('I think better of it and stay in Convila another night.')
    play.say('I set out for Kingswood.')
    play.say('I rest for three days at the Wayhouse.')
    play.journal()


def director(play):
    """M2: days passing so factions, beats, Life Cards, jobs and the director move; looking for work; an oath."""
    play.start('agna-holt', hand='firm')
    play.say('I ask around the Felled Oak who is hiring, anything that pays.')
    play.say('I swear to the barkeep I will find out who leaves the arrows on the bunks, on my life, within three '
             'days.')
    for day in range(4):
        play.say('I sleep the night at the bunkhouses.')
        play.say('I spend the day felling trees in the stump fields and come back at dusk.')
    play.say('I go to the shrine and ask Mother Rook what lies under the Heartwood.')
    play.journal()
    play.people()


def chapters(play):
    """M3: chapters closing at scene breaks and by hand, "Previously" openers, bookmarks, the branch tree, playing
    from a chapter, and the notebook."""
    play.start('agna-holt')
    play.say('I take a seat at the bar and ask the keeper what the town makes of the wardens.')
    play.say('I ask who in town has actually seen a warden, and where.')
    play.move('the-green')  # a new place is a scene break
    play.say('I read the contract notice and look for a crew boss to talk to.')
    play.attempt('End the chapter as "The notice"', 'POST', '/api/story/chapters/close', {'title': 'The notice'})
    play.say("I head to the guild factor's office to ask about signing on.")  # opens a chapter with "Previously"
    mark = play.lines()[-1]
    play.attempt('Bookmark that line', 'POST', '/api/story/bookmarks', {'message_id': mark['id'], 'name': 'Signing'})
    play.say('I sign my name in the ledger and ask when the first crew goes.')
    play.say('I sleep the night at the bunkhouses.')  # a rest is a scene break
    play.say('I get up, eat, and walk out to look at the stump fields.')
    listed = play.chapters().get('chapters') or []
    if len(listed) < 3:
        play.flag(f'Expected at least three chapters after a move, a hand-closed chapter and a rest; got {len(listed)}.')
    if listed and not any(chapter.get('title') == 'The notice' for chapter in listed):
        play.flag('The chapter named by hand did not keep its name.')
    if len(listed) >= 2:
        read = play.attempt('Read chapter 2', 'GET', f"/api/story/chapters/{listed[1]['id']}")
        play.write(f"- chapter 2 has {len((read or {}).get('lines') or [])} lines\n")
        play.attempt('Play from chapter 2', 'POST', f"/api/story/chapters/{listed[1]['id']}/back")
        play.say('I read the contract notice again, slowly this time, and count the names.')
    bookmarks = play.chapters().get('bookmarks') or []
    if bookmarks:
        play.attempt('Go to the bookmark', 'POST', f"/api/story/bookmarks/{bookmarks[0]['id']}/go")
        play.chapters()
    else:
        play.flag('The bookmark is not listed.')
    play.attempt('Write in the notebook', 'POST', '/api/story/notebook', {'text': 'Corin knows more than he says.'})
    notes = play.attempt('Read the notebook', 'GET', '/api/story/notebook') or {}
    if not notes.get('notes'):
        play.flag('The notebook note is not there.')


def ironman(play):
    """M3: Ironman, chosen at the start: no going back, telling a line again still allowed."""
    play.start('agna-holt', ironman=True)
    play.say('I ask the keeper for a room and a hot meal.')
    play.say('I ask him what the arrows on the bunks mean.')
    first = play.lines()[0]
    play.attempt('Go back in Ironman', 'POST', '/api/story/back', {'message_id': first['id']}, expect_refusal=True)
    play.attempt('Tell the last line again', 'POST', '/api/story/retry')
    if not play.chapters().get('ironman'):
        play.flag('The campaign does not say it is Ironman.')


def gm_view(play):
    """M3: the GM view: the whole record with hidden truth, Behind the story, feelings set by hand, asking again for
    one fact, adopted details and the director's seeds and beats."""
    play.start('lirien-of-the-ford', table={'gm_view': True})
    play.say('I take a corner table at the Felled Oak and watch the room.')
    play.say('That woman in the good cloak by the cellar door: I watch her closely. Who is she waiting for?')
    play.say('I go over, sit across from her and ask her plainly what she wants in Kingswood.')
    play.say('I ask the keeper what he knows of the woman in the cloak.')
    people = play.gm().get('people') or []
    if people:
        play.attempt(f"Set {people[0].get('name')}'s trust by hand", 'PATCH',
                     f"/api/story/gm/people/{people[0].get('key')}", {'trust': 3, 'fear': 1})
    journal = play.journal()
    pulled = [entry for entry in journal.get('entries') or [] if entry.get('source') == 'narrator']
    if pulled:
        play.attempt(f"Ask again for the fact \"{pulled[0].get('text')}\"", 'POST',
                     f"/api/story/journal/{pulled[0]['id']}/regenerate")
    else:
        play.flag('No fact pulled from the story to ask again for.')
    play.write(f"- journal entries with the GM view on: {len(journal.get('entries') or [])}\n")
    for line in ('I go to the shrine and ask Mother Rook about the old trees.',
                 'I ask her what the wardens would do if one tree past the stones fell.',
                 'I leave and walk to the border stones at dusk, looking for anything left there.',
                 'I search the foot of the split stone.'):
        play.say(line)
    play.gm()


ERRANDS = ('I look over the stalls and buy nothing.', 'I ask a stallholder about the price of salt.',
           'I watch the carts come in from the Cyrel road.', 'I ask the cheese seller where she is from.',
           'I wander along the stalls and count the guild coats.', 'I ask a carter how the road is.',
           'I watch a boy steal an apple and say nothing.', 'I ask the knife grinder for the news.',
           'I sit on a barrel and watch the crowd thin.', 'I ask a woman with geese how much for one.',
           'I look for anyone selling ink.', 'I ask the ink seller what paper costs.',
           'I watch the light go on the stalls.', 'I ask the cheese seller if she will be here tomorrow.',
           'I go round the market once more.', 'I ask a guard what time the gate shuts.',
           'I stand by the well and drink.', 'I watch two boys fight over a dog.',
           "I ask the dog's owner its name.", 'I count the coins in my purse.',
           'I look at the sky for rain.', 'I ask the knife grinder about the factor.',
           'I watch the stallholders pack up.', 'I stretch my legs along the empty stalls.',
           'I wait a while by the well.', 'I ask a passing logger if the bunkhouses are full.')


def memory(play):
    """M3: layered recall and forgetting over a long session: the story so far folds into a summary, an early detail
    fades, and trying to remember it takes a Mind roll."""
    play.start('tobin-pell')
    play.say('I ask the keeper, Corin, the name of the ferryman at the ford, and what he looks like.')
    play.say('I thank him and ask what the ferryman charges for a crossing.')
    play.move('crossroads-market')
    for line in ERRANDS:
        play.say(line, {'max_words': 600})
    play.say('I try to remember the ferryman at the ford, what Corin told me about him.', {'roll': True})
    play.journal()


def legacy(play):
    """M3: export the story as a book and the campaign as a file, import it as a new world, and start a new story
    in another world with the old character as a villain."""
    play.start('tobin-pell')
    play.say('I tell the keeper I mean to skim the Guild one last time and leave town rich.')
    play.say('I sleep the night at the Wayhouse.')
    play.say("I go to the guild factor's office and take the week's tally ledger off the desk while the clerk is out.")
    play.attempt('End the chapter', 'POST', '/api/story/chapters/close', {'title': 'The last skim'})
    content = play.export()
    play.write(f"- worlds before import: {json.dumps(play.dungeon.call('GET', '/api/worlds'), ensure_ascii=False)[:600]}\n")
    if content:
        response = play.dungeon.http.post('/api/worlds/import', content=content)
        play.write(f'### Import the campaign as a new world: {response.status_code} {response.text[:300]}\n')
        if response.status_code not in (200, 201):
            play.flag(f'Campaign import failed: {response.status_code} {response.text[:200]}')
    made = play.attempt('Make a new world', 'POST', '/api/worlds', {'name': 'After Tobin'}) or {}
    play.write(f'- made: {json.dumps(made, ensure_ascii=False)[:600]}\n')
    new_id = made.get('id') or (made.get('world') or {}).get('id') or made.get('world_id')
    if not new_id:
        play.flag("Could not tell the new world's id from the response.")
        return
    play.attempt('Switch to the new world', 'POST', f'/api/worlds/{new_id}/switch')
    candidates = play.dungeon.call('GET', '/api/story/start').get('legacy') or []
    play.write(f'- legacy candidates: {json.dumps(candidates, ensure_ascii=False)[:600]}\n')
    if not candidates:
        play.flag('No legacy characters offered at the start of the new world.')
        return
    world_id = candidates[0].get('world_id') or candidates[0].get('id')
    play.start('agna-holt', legacy={'world_id': world_id, 'role': 'villain'})
    play.say('I ask the keeper whether anyone remembers a clerk called Tobin Pell.')
    play.say("I ask what became of the Guild's ledgers.")
    play.journal()


def fivee_checks(play):
    """M4: a made 5E character (class, species, background, the standard array, skills): skill checks against DCs,
    a haggle, and the sheet."""
    choices = play.dungeon.call('GET', '/api/story/start')
    srd = choices.get('srd52') or {}
    classes = {item['id']: item for item in srd.get('classes') or []}
    if 'rogue' not in classes or not srd.get('backgrounds'):
        play.flag(f"No 5E rogue or backgrounds offered: {sorted(classes)}")
        return
    rogue, background = classes['rogue'], srd['backgrounds'][0]
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    taken = set(background.get('skills') or [])
    picks = [ids.get(name, name) for name in rogue['skills']['from'] if name not in taken]
    play.start(persona={'name': 'Maren Voss', 'gender': 'woman', 'age': 27,
                        'about': 'A lockpick from Cyrel who came north owing the wrong people.'},
               ruleset='srd52', build={'class_id': 'rogue', 'species_id': 'human', 'background_id': background['id'],
                                       'scores': {'dex': 15, 'int': 14, 'con': 13, 'wis': 12, 'cha': 10, 'str': 8},
                                       'skills': picks[:rogue['skills']['count']]})
    play.sheet()
    play.say('I climb the back wall of the Felled Oak to the shuttered window above the cellar door.', {'roll': True})
    play.say('I pick the lock on the shutter, quiet as I can.', {'roll': True})
    play.say('I listen at the door of the room beyond for anyone awake.', {'roll': True})
    play.move('pell-provisions')
    play.say('I haggle over a coil of rope, all charm and a sad story.', {'roll': True})
    play.say('I lie to the keeper that the Guild sent me to check her scales.', {'roll': True})
    play.gear()


def fivee_fight(play):
    """M4: 5E fights: SRD stat blocks, attacks on AC, hit points, death saves, and going back."""
    play.start('agna-holt', ruleset='srd52')
    play.sheet()
    play.move('the-heartwood')
    for line in ('I push into the Heartwood along the old trail, sword drawn.',
                 'I go deeper, toward the oldest trees.',
                 'I keep going, marking the bark as I go.',
                 'I press on toward the hum in the ground.',
                 'I go on, slow and watchful.'):
        view = play.say(line)
        if view and (view.get('fight') or {}).get('fight'):
            break
    for line in ('I attack the nearest one with my sword.', 'I attack again, putting my weight behind it.',
                 'I keep fighting.', 'I swing at whoever is still standing.', 'I fight on.', 'I fight on.'):
        view = play.say(line)
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        # Dead in the Heartwood: back to before the woods so the brawl can still be played.
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'Heartwood' in line['text']))
        play.say('I turn round and head back to town instead.')
    play.move('the-sawpit')
    play.say('I look for the biggest logger in the place.')
    play.say('I punch him in the jaw.', {'fight': True})
    play.say('I hit him again.')
    draft = play.back(2)
    play.say(draft)


def fivee_caster(play):
    """M4: a 5E wizard: cantrips and prepared spells, slots spent and failing when gone, spell attacks in a fight,
    XP for a won fight, and a long rest giving the slots back."""
    srd = play.dungeon.call('GET', '/api/story/start').get('srd52') or {}
    background = next((item for item in srd.get('backgrounds') or [] if item['id'] == 'sage'),
                      (srd.get('backgrounds') or [{}])[0])
    wizard = next(item for item in srd.get('classes') or [] if item['id'] == 'wizard')
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    picks = [ids.get(name, name) for name in wizard['skills']['from'] if name not in (background.get('skills') or [])]
    play.start(persona={'name': 'Oriel Fenn', 'gender': 'man', 'age': 34,
                        'about': 'A hedge scholar from Eriane who reads ley lines for the Guild and lies about it.'},
               ruleset='srd52', build={'class_id': 'wizard', 'species_id': 'human', 'background_id': background['id'],
                                       'scores': {'int': 15, 'con': 14, 'dex': 13, 'wis': 12, 'cha': 10, 'str': 8},
                                       'skills': picks[:wizard['skills']['count']]})
    sheet = play.sheet()
    spells = sheet.get('spells') or {}

    def spoken(spell_id: str) -> str:
        return spell_id.replace('-', ' ').title()

    cantrips = [spoken(spell) for spell in spells.get('cantrips') or []]
    levelled = [spoken(spell) for spell in spells.get('prepared') or []]
    play.write(f"- cantrips {cantrips}; prepared {levelled}; slots {spells.get('slots')}\n")
    if not cantrips:
        play.flag('The wizard has no cantrips on the sheet.')
        return
    cantrip = next((name for name in cantrips if name == 'Fire Bolt'), cantrips[0])
    play.say(f'I cast {cantrip} at the empty bottle on the fence post outside.', {'roll': True})
    # Two first-level slots: the third cast should fail for want of one.
    for _ in range(3):
        if levelled:
            play.say(f'I cast {levelled[0]} at the scarecrow in the stump field.')
    names = [cantrip]
    play.sheet()
    play.move('the-heartwood')
    for line in ('I walk into the Heartwood, reading the ley in the bark.', 'I go deeper toward the hum.',
                 'I keep going, slow, a spell ready.', 'I press on.'):
        view = play.say(line)
        if view and (view.get('fight') or {}).get('fight'):
            break
    for _ in range(5):
        view = play.say(f'I cast {names[0]} at the nearest one.')
        fight = (view or {}).get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
    play.sheet()
    play.move('the-wayhouse')
    play.say('I sleep the night at the Wayhouse.')
    play.sheet()


def ironsworn(play):
    """M4: an Ironsworn character (3, 2, 2, 1, 1 and three assets): moves read from the words, the action roll with
    momentum, a fight with a thug on health and harm, a day's travel, the Heartwood contract as a vow, and rest."""
    choices = play.dungeon.call('GET', '/api/story/start').get('ironsworn') or {}
    stats = [stat['id'] for stat in choices.get('stats') or []]
    assets = choices.get('assets') or []
    if len(stats) != 5 or len(assets) < 3:
        play.flag(f'Ironsworn choices look wrong: stats {stats}, {len(assets)} assets.')
        return
    placed = dict(zip(('iron', 'edge', 'wits', 'heart', 'shadow'), choices.get('array') or [3, 2, 2, 1, 1]))
    by_category = {}
    for asset in assets:
        by_category.setdefault(asset['category'], asset['id'])
    picks = list(by_category.values())[:choices.get('count') or 3]
    play.start(persona={'name': 'Hald Brenner', 'gender': 'man', 'age': 41,
                        'about': 'A sworn sword out of Bastion who keeps his oaths and little else.'},
               ruleset='ironsworn', ironsworn={'stats': placed, 'assets': picks})
    play.sheet()
    play.say('I ask the keeper who in Kingswood needs a sword they can trust.')
    play.say('I search the notice post on the green for anything about the Heartwood.')
    play.say('I talk the factor round to telling me the truth about the double wages.', {'roll': True})
    play.say('I swear an iron vow to see the Heartwood contract through, whatever it costs, and I mean it.')
    play.move('the-sawpit')
    play.say('I pick out the loudest thug in the room.')
    play.say('I shove him off his stool and hit him.', {'fight': True})
    for line in ('I hit him again.', 'I keep at him.', 'I finish it.', 'I fight on.'):
        view = play.say(line)
        if not ((view or {}).get('fight') or {}).get('fight'):
            break
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        # Dead in a bar brawl: go back to before the fight so the rest of the scenario can play.
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'shove him' in line['text']))
    play.say('I set out for Convila along the forest road.')
    play.sheet()
    play.say('I make camp outside the walls for the night and keep a watch.')
    play.sheet()
    play.journal()


def percentile(play):
    """M4: a Percentile (BRP) character bought on the start screen: skill rolls named by the words, experience checks
    after a night's rest, a fight with weapon skills and dodge, wounds, First Aid and slow healing."""
    choices = play.dungeon.call('GET', '/api/story/start').get('brp') or {}
    if not choices.get('professions'):
        play.flag('No Percentile professions offered.')
        return
    # 24 points over 10s, DEX, INT and POW at 3 a point: STR 16, CON 14, SIZ 13, CHA 12, DEX 12, INT 11, POW 10.
    play.start(persona={'name': 'Sefa Dunmore', 'gender': 'woman', 'age': 32,
                        'about': 'A sell-sword who came north with a Cyrel caravan and stayed for the wages.'},
               ruleset='brp', brp={'characteristics': {'str': 16, 'con': 14, 'siz': 13, 'cha': 12, 'dex': 12,
                                                       'int': 11, 'pow': 10},
                                   'profession': 'warrior', 'personality': 'brutal'})
    before = play.sheet()
    play.say('I climb onto the Felled Oak roof to see over the town.', {'roll': True})
    play.say('I look about the square for anyone watching me.', {'roll': True})
    play.move('pell-provisions')
    play.say('I haggle over a whetstone, hard.', {'roll': True})
    play.say('I sleep the night at the Wayhouse.')
    after = play.sheet()
    if json.dumps(before.get('skills'), sort_keys=True) == json.dumps(after.get('skills'), sort_keys=True):
        play.write('- no skill rose from the experience checks this night\n')
    play.move('the-sawpit')
    play.say('I pick out the biggest bruiser in the room.')
    play.say('I draw my sword and go for him.', {'fight': True})
    for line in ('I dodge his swing and cut at him.', 'I attack again.', 'I keep fighting.', 'I fight on.'):
        view = play.say(line)
        if not ((view or {}).get('fight') or {}).get('fight'):
            break
    play.sheet()
    if (play.story().get('fight') or {}).get('dead'):
        play.back(next(n for n, line in enumerate(reversed(play.lines()), 1) if 'draw my sword' in line['text']))
        play.say('I let him be and drink instead.')
    for _ in range(3):
        if not (play.story().get('fight') or {}).get('fight'):
            break
        play.say('I break away and run for the door.')
    play.say('I climb the Sawpit stairs two at a time and look about for anyone following.')
    hurt = (play.story().get('fight') or {}).get('hp', 0) < (play.story().get('fight') or {}).get('max_hp', 0)
    view = play.say('I bind my wounds with a strip of my shirt.', {'roll': hurt})
    rolled = [roll for m in (view or {}).get('messages') or [] if m['role'] == 'user' for roll in m.get('rolls') or []]
    if hurt and not any('First Aid' in (roll.get('skill') or '') for roll in rolled[-2:]):
        play.flag('Binding a real wound did not roll First Aid.')
    play.say('I sleep three nights at the Wayhouse to heal.')
    play.sheet()


def lore(play):
    """M5: a fresh Vallarith campaign carries the world package's lore book, and naming a place pulls in its entry."""
    play.start('agna-holt')
    books = play.dungeon.call('GET', '/api/lore')
    names = [book.get('name') or book.get('title') for book in (books.get('books') if isinstance(books, dict) else books)
             or []]
    play.write(f'- lore books: {names}\n')
    if not any('world package' in (name or '') for name in names):
        play.flag(f'No "(world package)" lore book on a fresh Vallarith campaign: {names}')
    view = play.say('I ask the keeper what news there is from Dun Aldun, and whether the dwarves still sell their '
                    'steel south.')
    told = next((m['text'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    if 'Stoneheart' not in told and 'dwar' not in told.lower():
        play.flag('The narration about Dun Aldun shows nothing from its lore entry.')
    play.say('I ask what the Kingdom of Cyrel and the High Elves of Brynwyr are to each other these days.')
    # Keywords beyond the entry's name: "dwarven steel" is Dun Aldun's, "the badlands" The Badlands'.
    view = play.say('I ask a carter where the best dwarven steel comes from.')
    told = next((m['text'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    play.write(f"- dwarven steel brought up Dun Aldun: {'Aldun' in told or 'Ley' in told}\n")
    view = play.say('I ask him what lies out past the badlands, and whether anyone comes back.')
    told = next((m['text'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    play.write(f"- the badlands brought up its entry: {any(word in told for word in ('Dragon King', 'corpse', 'tribe'))}\n")


def narrative(play):
    """M4: Narrative Only: the About text is the sheet; a judge rules No, No but, Yes but or Yes from who the character
    is, the words and how people feel. An unlikely seduction by an ill-suited character, then plausible actions."""
    play.start(persona={'name': 'Osric Vell', 'gender': 'man', 'age': 52,
                        'about': 'A stooped, nervous bookkeeper with ink-black fingers, a wheeze and a bad wig. '
                                 'He has never once been flirted with and would not know it if he were.'},
               ruleset='narrative', narrative={'good_at': ['sums and ledgers', 'noticing a cooked book'],
                                              'bad_at': ['talking to strangers', 'anything physical']},
               table={'gm_view': True})
    play.sheet()
    play.say("I lean across the bar and seduce the keeper with a slow, smouldering look and a line about her eyes.",
             {'roll': True})
    play.say('I try again, bolder, and ask her up to my room.', {'roll': True})
    play.move('guild-factor')
    play.say('I ask to see the week\'s tally ledger and check its sums for anything cooked.', {'roll': True})
    play.say('I vault the counter and wrestle the clerk for the key to the chest.', {'roll': True})
    play.say('I explain politely that I am a bookkeeper and offer to balance their accounts for a fee.')


def fivee_defeat(play, rule: str):
    """A fragile 5E wizard in the Heartwood until a fight takes them down: under `rule`, how the defeat lands."""
    srd = play.dungeon.call('GET', '/api/story/start').get('srd52') or {}
    wizard = next(item for item in srd.get('classes') or [] if item['id'] == 'wizard')
    background = next((item for item in srd.get('backgrounds') or [] if item['id'] == 'sage'), srd['backgrounds'][0])
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    picks = [ids.get(name, name) for name in wizard['skills']['from'] if name not in (background.get('skills') or [])]
    play.start(persona={'name': 'Ivo Marsh', 'gender': 'man', 'age': 24, 'about': 'A hedge wizard, short of breath.'},
               ruleset='srd52', table={'defeat': rule},
               build={'class_id': 'wizard', 'species_id': 'human', 'background_id': background['id'],
                      'scores': {'int': 15, 'con': 8, 'dex': 13, 'wis': 12, 'cha': 10, 'str': 14},
                      'skills': picks[:wizard['skills']['count']]})
    play.move('the-heartwood')
    for _ in range(24):
        view = play.say('I go deeper into the Heartwood.') if not ((play.story().get('fight') or {}).get('fight')) \
            else play.say('I swing my staff at the nearest one.')
        state = (view or play.story()).get('fight') or {}
        if state.get('dead') or state.get('captors'):
            break
    final = play.story().get('fight') or {}
    play.write(f"- after the fight: dead {final.get('dead')}, captors {final.get('captors')}\n")
    return final


def fivee_defeat_aim(play):
    """M4: 5E with "Foes decide a defeat" on: wardens who want the character taken take them prisoner."""
    final = fivee_defeat(play, 'by_aim')
    if final.get('dead') and 'warden' in json.dumps(play.story().get('fight') or {}):
        play.flag('Under "Foes decide a defeat", wardens who want capture killed the character.')
    if final.get('captors') and final.get('injuries'):
        play.flag(f"The captors maimed the character they took: {final.get('injuries')}")


def fivee_defeat_written(play):
    """M4: 5E with the defeat as written: death saves run whatever the foes want."""
    fivee_defeat(play, 'as_written')


def importer(play):
    """M5: the world importer: two documents and a lorebook become a draft; a section drafted by the model, reviewed
    and approved; the package written and listed."""
    files = [{'name': 'overview.md', 'text': (
                 '# The Saltmarch\n\nA drowned coast of reed islands under the rule of the Tidewardens, a council '
                 'of seven families who own every causeway. Salt and eels are the only trade. The town of Brackwater '
                 'sits on the largest island; the hamlet of Low Reed on the edge of the open sea. Inland lies the '
                 'Mire of Ash, where nobody goes. The Tidewardens secretly pay the Mire\'s witch for calm weather.')},
             {'name': 'people.md', 'text': (
                 '# People\n\n- Marra Quill, eldest Tidewarden, keeps the causeway tolls.\n- Fenwick, a salt boiler in '
                 'Low Reed who smuggles eels past the tolls.\n- The Mire witch, never named, owed a child every '
                 'seventh winter.')},
             {'name': 'saltmarch-lore.json', 'text': json.dumps({'entries': {
                 '0': {'key': ['causeway', 'causeways'], 'content': 'The causeways flood at spring tide; crossing '
                       'without a Tidewarden token costs a silver penny.'},
                 '1': {'key': ['eel', 'eels'], 'content': 'Saltmarch eels are smoked over reed fires and sold '
                       'south by the barrel.'}}})}]
    draft = play.attempt('Start a world import', 'POST', '/api/packages/drafts', {'name': 'The Saltmarch',
                                                                                   'files': files}) or {}
    draft_id = draft.get('id') or (draft.get('draft') or {}).get('id')
    play.write(f'- draft: {json.dumps(draft, ensure_ascii=False)[:800]}\n')
    lore_titles = [entry.get('title') for item in draft.get('sections') or [] if item.get('id') == 'lore'
                   for entry in item.get('entries') or []]
    if any((title or '').startswith('Entry ') for title in lore_titles):
        play.flag(f'Lorebook entries are titled by number, not by their keywords: {lore_titles}')
    if not draft_id:
        play.flag('No draft id from the import.')
        return
    play.attempt('Approve the lorebook as the lore section', 'PUT', f'/api/packages/drafts/{draft_id}/sections/lore',
                 {'status': 'approved'})
    for section in ('regions', 'settlements', 'cast'):
        drafted = play.attempt(f'Draft {section} with the model', 'POST',
                               f'/api/packages/drafts/{draft_id}/sections/{section}/draft') or {}
        found = next((item for item in drafted.get('sections') or [] if item.get('id') == section), {})
        play.write(f"- {section}: {json.dumps(found.get('entries'), ensure_ascii=False)[:900]}\n")
        if not found.get('entries'):
            play.flag(f'The model drafted no {section}.')
        play.attempt(f'Approve {section}', 'PUT', f'/api/packages/drafts/{draft_id}/sections/{section}',
                     {'status': 'approved'})
    view = play.attempt('Read the draft', 'GET', f'/api/packages/drafts/{draft_id}') or {}
    play.write(f'- draft now: {json.dumps(view, ensure_ascii=False)[:1200]}\n')
    finished = play.attempt('Write the package', 'POST', f'/api/packages/drafts/{draft_id}/finish', {})
    play.write(f'- finished: {json.dumps(finished, ensure_ascii=False)[:600]}\n')
    listed = play.dungeon.call('GET', '/api/packages')
    names = json.dumps(listed, ensure_ascii=False)
    if 'Saltmarch' not in names:
        play.flag('The imported world is not listed among the packages.')
    play.write(f'- packages: {names[:800]}\n')


def editor(play):
    """M5: the world editor on a built-in world: find an entry, edit it, see a bad edit refused, undo, edit again and
    play it, then reset the world to how it shipped."""
    base = '/api/packages/vallarith'
    found = play.attempt('Search the lore for Dun Aldun', 'GET', f'{base}/entries?section=lore&q=Dun%20Aldun') or {}
    play.write(f'- search: {json.dumps(found, ensure_ascii=False)[:700]}\n')
    entry_id = next((hit['id'] for hit in found.get('entries') or [] if hit.get('section') == 'lore'), None)
    if not entry_id:
        play.flag('No lore entry found for Dun Aldun.')
        return
    shown = play.attempt('Open the entry', 'GET', f'{base}/entries/lore/{entry_id}') or {}
    entry = shown.get('entry') or shown
    play.write(f'- entry: {json.dumps(entry, ensure_ascii=False)[:600]}\n')
    original = entry.get('text', '')
    edited = dict(entry, text=original + ' Since the spring, the Stoneheart Clan sells its steel only through Mordun, '
                                          'and only for silver weighed on dwarven scales.')
    play.attempt('Save an edit', 'PUT', f'{base}/entries/lore/{entry_id}', {'entry': edited})
    play.attempt('Save a bad id', 'PUT', f'{base}/entries/lore/{entry_id}', {'entry': dict(entry, id='Not Kebab Case')},
                 expect_refusal=True)
    said = getattr(play, 'last_error', '')
    if entry_id not in said and 'Dun Aldun' not in said and 'Not Kebab Case' not in said:
        play.flag(f"The bad-id error doesn't name the entry: {said}")
    play.attempt('Undo', 'POST', f'{base}/undo')
    after = (play.attempt('Read it back', 'GET', f'{base}/entries/lore/{entry_id}') or {})
    if (after.get('entry') or after).get('text') != original:
        play.flag('Undo did not restore the entry as it was.')
    play.attempt('Save the edit again', 'PUT', f'{base}/entries/lore/{entry_id}', {'entry': edited})
    history = play.attempt('Read the history', 'GET', f'{base}/history') or {}
    play.write(f"- history entries: {len(history.get('history') or [])}\n")
    play.start('agna-holt')
    view = play.say('I ask the keeper how a body buys dwarven steel these days, and from where.')
    told = next((m['text'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    play.write(f"- the edit on the page: {'silver' in told.lower() and 'mordun' in told.lower()}\n")
    reset = play.attempt('Reset the built-in world', 'POST', f'{base}/reset') or {}
    play.write(f'- after reset: {json.dumps(reset, ensure_ascii=False)[:300]}\n')
    back = play.attempt('Read the entry after reset', 'GET', f'{base}/entries/lore/{entry_id}') or {}
    if (back.get('entry') or back).get('text') != original:
        play.flag('Reset did not bring the entry back as it shipped.')


def pictures(play):
    """M6: pictures on request (Picture me, This place, The scene, Someone you met, a passage) and passive art. With
    no image backend set up, each request is refused with a clear message; the EPUB book still exports."""
    play.start('agna-holt')
    view = play.say('I ask the keeper her name and what she makes of the rain.')
    met = next((person.get('key') for person in (view or {}).get('people') or []), '')
    narration = next((m['id'] for m in reversed((view or {}).get('messages') or []) if m['role'] == 'narrator'), '')
    for label, kind, subject in (('Picture me', 'portrait', 'player'), ('This place', 'place', ''),
                                 ('The scene', 'scene', ''), ('Someone you met', 'portrait', met),
                                 ('Picture this passage', 'passage', narration)):
        response = play.dungeon.http.post('/api/story/art', json={'kind': kind, 'subject': subject})
        body = response.text[:300]
        play.write(f'### {label}: {response.status_code} {body}\n')
        gallery = play.dungeon.call('GET', '/api/story/art').get('art') or []
        latest = gallery[0] if gallery else {}
        play.write(f"- gallery newest: {json.dumps(latest, ensure_ascii=False)[:300]}\n")
        said = (body + json.dumps(latest)).lower()
        if 'backend' not in said and 'no image' not in said:
            play.flag(f'{label} without an image backend gave no clear "No image backend" message.')
    play.dungeon.call('PUT', '/api/settings', {'passive_art': True})
    play.say('I step out onto the green and watch the crews come in from the stump fields.')
    play.write(f"- gallery after a turn with passive art: {len(play.dungeon.call('GET', '/api/story/art').get('art') or [])}\n")
    epub = play.dungeon.http.get('/api/story/export/book', params={'format': 'epub'})
    play.write(f'### Export the EPUB: {epub.status_code}, {len(epub.content)} bytes\n')
    if epub.status_code != 200:
        play.flag(f'The EPUB export failed with no pictures: {epub.status_code}')


def havenbrooke(play):
    """M5: a short Havenbrooke start: a premade sophomore in Haven in autumn 2009, the dorm, a class, the coffee
    place, and a drive to Ithaca by car."""
    play.dungeon.call('PUT', '/api/story/scene', {'city_id': 'haven', 'place_id': 'nexus-housing'})
    play.dungeon.call('DELETE', '/api/story')
    premades = play.dungeon.call('GET', '/api/story/start').get('premades') or []
    play.write(f"- premades: {[item.get('name') for item in premades]}\n")
    if not premades:
        play.flag('No Havenbrooke premades offered in Haven.')
        return
    play.start(premades[0]['id'])
    play.sheet()
    play.say('I look around the third floor of the Nexus and knock on the door across the hall.')
    play.say('I introduce myself and ask what they make of our floor so far.')
    play.say('I check my schedule and head to my first class of the day.')
    play.say('After class I go to Commons Coffee and grab a table by the window.')
    play.say('OOC: what is my character enrolled in, and where can I drive from here?', {'no_roll': True})
    play.say('I borrow a car and drive to Ithaca for the afternoon.')
    play.journal()


def tone(play):
    """M6: per-category intensity, veils and the voice. Sex off the page, violence mature, torture veiled, a wry
    voice; then a preset resets the categories but keeps the veils and the voice."""
    play.start('agna-holt', table={'levels': {'sex': 0, 'violence': 2}, 'veils': ['torture'], 'voice': 'wry'})
    rules = play.dungeon.call('GET', '/api/story/table')
    play.write(f"- table: levels {rules.get('levels')}, veils {rules.get('veils')}, voice {rules.get('voice')}\n")
    play.say('I flirt shamelessly with the keeper, and when she laughs I ask her to come upstairs with me tonight.')
    play.say('We go up to my room together and I take her to bed.')
    play.say('In the morning I catch a thief going through my pack and drag him out to the woodshed.')
    play.say('I torture him for the name of whoever sent him, breaking his fingers one by one.')
    play.say('I put my knife to his throat and finish it.')
    play.attempt('Pick the Restrained preset', 'PUT', '/api/story/table', {'intensity': 'restrained'})
    after = play.dungeon.call('GET', '/api/story/table')
    play.write(f"- after the preset: levels {after.get('levels')}, veils {after.get('veils')}, "
               f"voice {after.get('voice')}\n")
    if after.get('levels'):
        play.flag(f"The preset did not reset the categories: {after.get('levels')}")
    if 'torture' not in (after.get('veils') or []) or after.get('voice') != 'wry':
        play.flag('The preset dropped the veils or the voice.')


def restrained_wounds(play):
    """M6: violence at Restrained: a maiming never leaves a lost eye, a ruined hand or lost fingers."""
    play.start('tobin-pell', table={'levels': {'violence': 1}})
    play.move('the-heartwood')
    for _ in range(20):
        fighting = (play.story().get('fight') or {}).get('fight')
        play.say('I hit the nearest one with my fist.' if fighting else 'I go deeper into the Heartwood.')
        state = play.story().get('fight') or {}
        if state.get('dead') or state.get('captors') or state.get('injuries'):
            break
    injuries = (play.story().get('fight') or {}).get('injuries') or []
    play.write(f'- lasting injuries at Restrained: {injuries}\n')
    if any(word in ' '.join(injuries) for word in ('eye', 'hand', 'finger')):
        play.flag(f'Restrained violence still left a lost eye, ruined hand or lost fingers: {injuries}')


def stage(play):
    """M6: the stage without an image backend: no place picture and no portraits; a portrait of someone present
    before they are met is still asked for (and refused for want of a backend)."""
    play.start('agna-holt')
    view = play.say('I take a stool at the bar and watch the keeper work.')
    staged = play.attempt('Read the stage', 'GET', '/api/story/art/stage') or {}
    play.write(f'- stage: {json.dumps(staged, ensure_ascii=False)[:400]}\n')
    if staged.get('place') or staged.get('portraits'):
        play.flag('The stage shows pictures with no image backend.')
    present = (view or {}).get('scene', {}).get('present') or []
    for _ in range(3):
        # The tavern can be empty in the small hours: wait for a crowd.
        if present:
            break
        view = play.say('I wait six hours by the fire.')
        present = (view or {}).get('scene', {}).get('present') or []
    play.write(f'- present: {json.dumps(present, ensure_ascii=False)[:300]}\n')
    key = next((person.get('key') for person in present if isinstance(person, dict) and person.get('key')), '')
    if not key:
        play.flag('Nobody in scene.present to ask a portrait of.')
    response = play.dungeon.http.post('/api/story/art', json={'kind': 'portrait', 'subject': key})
    play.write(f'### A portrait of {key or "nobody"} before meeting them: {response.status_code} {response.text[:200]}\n')
    if response.status_code == 404:
        play.flag('A portrait of someone in the scene was refused because they are not met yet.')


def babel(play):
    """M5: a short BABEL start: a premade on Floor Zero, the Concourse under the dome, the market, the guilds and the
    gate onto the Stair."""
    play.dungeon.call('PUT', '/api/story/scene', {'city_id': 'the-concourse', 'place_id': 'the-plaza'})
    play.dungeon.call('DELETE', '/api/story')
    premades = play.dungeon.call('GET', '/api/story/start').get('premades') or []
    play.write(f"- premades: {[item.get('name') for item in premades]}\n")
    if not premades:
        play.flag('No BABEL premades offered on the Concourse.')
        return
    play.start(premades[0]['id'])
    play.sheet()
    play.say('I walk up to the Waystone and lay my hand on it.')
    play.say("I go to Hamid's cart and buy whatever passes for breakfast here.")
    play.say('I head to the guild halls and ask what a newcomer can sign up for.')
    play.say('OOC: what do I know about the Stair and where can I go from here?', {'no_roll': True})
    play.say('I go out through the gate arch onto the Stair and look up.')
    play.journal()


def fate_points(play) -> int | None:
    sheet = play.dungeon.call('GET', '/api/story/sheet')
    return sheet.get('fate_points', sheet.get('points'))


def fate_made(play):
    """M4: a Fate character made on the start screen: aspects, approaches and stunts; actions that fit them, Fate
    points spent on invokes and earned on compels, refresh after sleep, and a fight on the shared wound levels."""
    play.start(persona={'name': 'Wren Halloway', 'gender': 'woman', 'age': 30,
                        'about': 'A disgraced Guild surveyor who reads land like a ledger and cannot leave a debt alone.'},
               ruleset='fate', fate={'high_concept': 'Disgraced Guild surveyor with a map for every lie',
                                    'trouble': 'I always pay my debts, whatever they cost',
                                    'aspects': ['Knows every path through the stump fields', 'Owes Corin a favour'],
                                    'approaches': {'Clever': 3, 'Careful': 2, 'Sneaky': 2, 'Quick': 1, 'Forceful': 1,
                                                   'Flashy': 0},
                                    'stunts': ['Because I read land like a ledger, I get +2 when I cleverly survey '
                                               'ground or find a path']})
    play.sheet()
    before = fate_points(play)
    play.say('I cleverly survey the ground outside the tavern and find the path the arrow-carrier took.',
             {'roll': True})
    play.say('I flashily stand on the bar and give a rousing speech about the Guild.', {'roll': True})
    play.say('I sneak into the guild factor\'s office at night to copy the contract ledger.', {'roll': True})
    play.say('A creditor demands I settle a debt I owe him tonight, and I agree to pay it whatever it costs me.')
    after = fate_points(play)
    play.write(f'- Fate points: {before} at the start, {after} now\n')
    play.say('I sleep the night at the Wayhouse.')
    play.write(f'- Fate points after sleep: {fate_points(play)}\n')
    play.move('the-sawpit')
    play.say('I pick out the loudest drunk in the room.')
    play.say('I punch him hard in the jaw.', {'fight': True})
    for line in ('I hit him again.', 'I keep at him.', 'I finish it.'):
        view = play.say(line)
        if not ((view or {}).get('fight') or {}).get('fight'):
            break
    play.sheet()


def fate_premade(play):
    """M4: a Kingswood premade played under Fate: its high concept from its About, approaches from its stats."""
    play.start('tobin-pell', ruleset='fate')
    play.sheet()
    play.say('I carefully check the tally ledger for the skimmed boards before the factor does.', {'roll': True})
    play.say('I charm the clerk into letting me take the ledger home for the night.', {'roll': True})


def marvel_start(play):
    """Regression: a plain Prospero start still plays."""
    play.start('agna-holt')
    play.say('I ask the keeper for a room and climb the stairs to it.')


def hex_view(play, label: str) -> dict:
    """Where the map has the character and the hexes known, written to the transcript."""
    found = play.story().get('map') or {}
    hexes = found.get('hexes') or []
    play.write(f"- map after {label}: at {json.dumps(found.get('at'))}, {len(hexes)} hexes known, "
               f"sites {[cell['site'] for cell in hexes if isinstance(cell, dict) and cell.get('site')]}\n")
    return found


def terrain_of(found: dict) -> dict:
    return {(cell.get('q'), cell.get('r')): cell.get('land') or cell.get('terrain') for cell in found.get('hexes') or []
            if isinstance(cell, dict)}


def hex_vallarith(play):
    """Hex crawl: a journey hex by hex, striking out into the wild past the authored map's edge, searching, sites,
    getting lost, and the same generated land on coming back."""
    play.start('lirien-of-the-ford')
    play.say('I set out for Eriane.')
    hex_view(play, 'the journey to Eriane')
    play.say('I strike out north-east, off the road.')
    first = hex_view(play, 'striking out north-east')
    for day in range(4):
        if (play.story().get('fight') or {}).get('fight') or (play.story().get('fight') or {}).get('dead'):
            break
        play.say('I keep heading north-east, as far as I can get by dark.')
        hex_view(play, f'day {day + 2} north-east')
        play.say('I make camp for the night, no fire.')
    play.say('I search the area for anything worth finding.', {'roll': True})
    far = hex_view(play, 'searching')
    play.say('I set out for Kingswood.')
    hex_view(play, 'heading home')
    # The same land, generated past the edge, should be the same on the way back out.
    before = terrain_of(far)
    play.say('I strike out north-east again, the way I went before.')
    again = terrain_of(hex_view(play, 'going back out'))
    changed = [cell for cell, land in again.items() if cell in before and before[cell] != land]
    if changed:
        play.flag(f'Hexes changed their land on returning: {changed[:5]}')
    walked = terrain_of(first)
    same = all(walked[cell] == land for cell, land in again.items() if cell in walked)
    play.write(f"- first walk's hexes still the same: {same}\n")
    play.journal()


def hex_woods(play):
    """Havenbrooke's woods: an on-foot crawl of one-mile hexes from Ironroot Woods, a search, back to Haven, and the
    car road still a road from the trailhead."""
    play.dungeon.call('PUT', '/api/story/scene', {'city_id': 'haven', 'place_id': 'ironroot-woods'})
    play.dungeon.call('DELETE', '/api/story')
    play.start('piper-marsh')
    play.say('I head out north into the woods, off the trail.')
    hex_view(play, 'heading into the woods')
    play.say('I keep going north for an hour or so.')
    hex_view(play, 'deeper in')
    play.say('I search the area for anything odd.', {'roll': True})
    hex_view(play, 'searching the woods')
    play.say('I head back to the Riverwalk.')
    hex_view(play, 'back to the Riverwalk')
    play.say('I take the bus to Ithaca.')
    hex_view(play, 'the bus to Ithaca')


def hamlet(play):
    """Hex crawl: walking toward the nearest hamlet the campaign's seed put near Kingswood, coming upon it, and the
    found hamlet being a place of its own on the Road with its own name and people."""
    from dungeon import hexes, travel  # the harness runs beside the app's code
    play.start('agna-holt')
    play.say('I set out for Convila.')  # a first journey sets the campaign's seed
    with play.dungeon.database() as connection:
        connection.row_factory = __import__('sqlite3').Row
        seed = connection.execute('SELECT seed FROM story_campaign').fetchone()['seed']
    board = hexes.Grid(next(item for item in travel.maps() if hexes.is_hex(item) and hexes.key(item) == 'vallarith'),
                       seed)
    here = tuple((play.story().get('map') or {}).get('at', {}).get(axis) for axis in 'qr')
    near = sorted(((cell, site) for radius in range(1, 12) for cell in hexes.ring(here, radius)
                   if (site := board.site(cell)) and site['kind'] == 'hamlet' and site['visible']),
                  key=lambda pair: hexes.distance(here, pair[0]))
    if not near:
        play.flag('No hamlet within eleven hexes to walk to.')
        return
    cell, site = near[0]
    play.write(f"- nearest hamlet: {site['name']} at {cell}, {hexes.distance(here, cell)} hexes "
               f"{hexes.bearing(here, cell)}\n")
    for _ in range(4):
        at = tuple((play.story().get('map') or {}).get('at', {}).get(axis) for axis in 'qr')
        if at == cell or play.story()['scene']['place']['id'].startswith('hamlet-'):
            break
        play.say(f'I strike out {hexes.bearing(at, cell)}.')
    scene = play.story()['scene']
    play.write(f"- scene: {scene['place']['id']} / {scene['place']['name']}, around: "
               f"{[str(person) for person in scene.get('around') or []]}\n")
    if not scene['place']['id'].startswith('hamlet-'):
        play.flag(f"Reaching {site['name']} did not make it a place of its own (scene {scene['place']['id']}).")
    play.say('I look for whoever is in charge here and ask what news there is.')


def narration_format(play):
    """How it's written: a new campaign starts in close third person, past tense, short; first person present and
    long at the Table; then second person past, the next line following the change."""
    play.start('agna-holt')
    rules = play.dungeon.call('GET', '/api/story/table')
    play.write(f"- format at start: pov {rules.get('pov')}, tense {rules.get('tense')}, length {rules.get('length')}\n")
    if (rules.get('pov'), rules.get('tense'), rules.get('length')) != ('third', 'past', 'short'):
        play.flag(f"A new campaign did not start in third person, past tense, short: {rules}")
    play.say('I take a seat by the fire and watch who comes in.')
    play.attempt('First person, present tense, long', 'PUT', '/api/story/table',
                 {'pov': 'first', 'tense': 'present', 'length': 'long'})
    play.say('I order an ale and ask the keeper what news there is from the Heartwood.', {'max_words': 1600})
    play.attempt('Second person, past tense, medium', 'PUT', '/api/story/table',
                 {'pov': 'second', 'tense': 'past', 'length': 'medium'})
    play.say('I finish my ale and head up to bed.', {'max_words': 550})


def selling(play):
    """Shops: selling in the story, the keeper's till, stolen goods refused by an honest shop, and Mother Mag's fence
    buying them at a quarter."""
    play.start('tobin-pell')
    play.move('pell-provisions')
    play.gear()
    play.say('I sell my blanket over the counter.')  # Tobin carries no blanket: the sale should be refused
    play.say('I sell my ledger book over the counter.')
    play.gear()
    stolen = []
    for line in ('I pocket a lantern from the shelf while the keeper is turned away.',
                 'I slip a coil of rope under my coat when nobody is looking.',
                 'I palm a flint and steel off the counter.'):
        play.say(line)
        stolen = [item['name'] for item in play.gear().get('items') or [] if item.get('stolen')]
        if stolen:
            break
    play.write(f'- stolen: {stolen}\n')
    if stolen:
        play.say(f'I try to sell the {stolen[0].lower()} back to the keeper.')
        play.gear()
    play.move('mother-mags')
    if not (play.gear().get('shop') or {}).get('open'):
        play.say("I wait outside Mother Mag's until she opens for the evening.")
        play.gear()
    if stolen:
        play.say(f'I fence the {stolen[0].lower()} to Mother Mag.')
    play.say('I sell Mother Mag everything else I can spare, all of it.')
    play.gear()


def fence(play):
    """Stolen goods: an honest shop turns them away, and Mother Mag's fence buys them at a quarter, out of a small
    till. The goods are marked stolen and the clock set to evening by the test itself."""
    play.start('tobin-pell')
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        connection.execute("UPDATE story_inventory SET stolen=1 WHERE item_id IN ('candles', 'gloves')")
    play.write('- candles and gloves marked stolen for the test\n')
    play.move('pell-provisions')
    play.gear()
    play.say('I sell the candles over the counter.')
    play.gear()
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        at = connection.execute('SELECT at FROM story_clock WHERE id=1').fetchone()[0]
        connection.execute('UPDATE story_clock SET at=? WHERE id=1', (at[:11] + '20:30:00' + at[19:],))
    play.move('mother-mags')
    before = play.gear()
    play.say('I fence the candles to Mother Mag.')
    play.say('I sell Mother Mag my gloves and my cloak too.')
    after = play.gear()
    if after.get('coins') == before.get('coins'):
        play.flag("Mother Mag's fence bought nothing.")


def wayhouse(play):
    """Services: a private room, a hot meal and a bath at the Wayhouse, kept for the day and not carried; a night's
    rest in the paid bed."""
    play.start('agna-holt')
    play.move('the-wayhouse')
    coins = play.gear().get('coins')
    play.say('I take a private room for the night.')
    if play.gear().get('coins') == coins:
        play.flag('"I take a private room for the night" paid for nothing.')
        play.say('I rent the private room for the night, then.')
    play.say('I order a hot meal and eat it by the fire.')
    play.say('I pay for a hot bath and soak until the water goes cold.')
    gear = play.gear()
    carried = [item['name'] for item in gear.get('items') or [] if item.get('category') == 'service']
    if carried:
        play.flag(f'Services ended up in the pack: {carried}')
    play.say('I go up to my room and sleep until morning.')
    play.gear()


def grime(play):
    """How you look: a hard day's work makes the character grimy, washing at the ford takes it down a step, and
    undressing and dressing move the layers."""
    play.start('tobin-pell')
    play.move('timber-yards')
    play.gear()
    play.say('I spend the whole day hauling logs and stacking planks at the timber yards for a day wage.')
    before = play.gear().get('looks') or {}
    play.move('the-ford')
    play.say('I take off my coat and shirt and wash in the river.')
    after = play.gear().get('looks') or {}
    if before.get('grime') == after.get('grime') and before.get('grime') not in (None, 'clean'):
        play.flag(f"Washing did not change how grimy the character is: {before.get('cleanliness')}")
    play.say('I put my shirt and coat back on and walk back into town.')
    play.gear()


def spoils(play):
    """The fallen: a fight won leaves a body; searching it shows what it carried, and taking the coins is not
    stolen."""
    play.start('agna-holt')
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:  # the Sawpit fills at night
        at = connection.execute('SELECT at FROM story_clock WHERE id=1').fetchone()[0]
        connection.execute('UPDATE story_clock SET at=? WHERE id=1', (at[:11] + '20:30:00' + at[19:],))
    play.move('the-sawpit')
    play.write(f"- around: {[str(person) for person in play.story()['scene'].get('around') or []]}\n")
    play.say('I pick out the loudest logger in the place, call him a coward, and cut at him with my sword.',
             {'fight': True})
    for line in ('I cut at him.', 'I drive the point at his chest.', 'I swing again.', 'I press the attack.',
                 'I keep fighting.', 'I finish him.'):
        fight = play.story().get('fight') or {}
        if not fight.get('fight') or fight.get('dead'):
            break
        play.say(line)
    play.gear()
    play.say('I search the body.')
    play.say('I take the coins.')
    gear = play.gear()
    if any(item.get('stolen') for item in gear.get('items') or []):
        play.flag('Something taken from a body is marked stolen.')


def mending(play):
    """Wear and repair: a damaged sword mended at the Blackwood smithy for a price, not bought anew."""
    play.start('agna-holt')
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:  # the test's own damage
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT id, item_id FROM story_inventory WHERE item_id LIKE '%sword%' "
                                 "OR item_id LIKE '%blade%'").fetchone()
        if row:
            connection.execute("UPDATE story_inventory SET condition='damaged' WHERE id=?", (row['id'],))
    if not row:
        play.flag('No sword in the pack to damage.')
        return
    play.write(f"- damaged {row['item_id']} for the test\n")
    play.move('blackwood-smithy')
    before = play.gear()
    if not (before.get('shop') or {}).get('open'):
        play.say('I sleep rough by the smithy and wait for the smith to come to work in the morning.')
        before = play.gear()
    play.say('I have the smith mend my sword.')
    after = play.gear()
    swords = [item for item in after.get('items') or [] if item['item_id'] == row['item_id']]
    if len(swords) != 1 or sum(item.get('qty', 1) for item in swords) != 1:
        play.flag(f'Mending bought a sword, or lost one: {swords}')
    if swords and swords[0].get('condition') != 'sound':
        play.flag(f"The sword is still {swords[0].get('condition')} after the smith mended it.")
    if after.get('coins') == before.get('coins'):
        play.flag('The repair cost nothing.')


def town_map(play):
    """The Town widget: Kingswood's street map, looking at a blank building, and walking to it by name."""
    play.start('agna-holt')
    town = play.dungeon.call('GET', '/api/story/town')['town']
    if not town:
        play.flag('Kingswood has no street map.')
        return
    lots = town.get('lots') or []
    blank = [lot for lot in lots if not lot.get('place')]
    play.write(f"- {town.get('name')}: {len(lots)} lots, {len(blank)} blank, here {town.get('here')}, "
               f"keys {sorted(town)}\n")
    named = [lot['place']['name'] for lot in lots if lot.get('place')]
    play.write(f'- on the map: {named[:30]}\n')
    if not blank:
        play.flag('No blank building to look at.')
        return
    looked = play.dungeon.call('POST', f"/api/story/town/lots/{blank[0]['id']}/look")
    found = looked.get('found') or {}
    play.write(f"- looked at {blank[0]['id']}: {json.dumps(found)[:400]}\n")
    again = play.dungeon.call('POST', f"/api/story/town/lots/{blank[0]['id']}/look")
    if again.get('found') != found:
        play.flag('Looking at the same building twice gave a different answer.')
    name = found.get('name') or (found.get('place') or {}).get('name')
    if not name:
        play.flag(f'The looked-at building has no name: {found}')
        return
    play.say(f'I walk over to {name}.')
    scene = play.story()['scene']
    play.write(f"- scene: {scene['place']['id']} / {scene['place']['name']}\n")
    if name.lower() not in scene['place']['name'].lower():
        play.flag(f"Walking to {name} put the scene at {scene['place']['name']}.")
    play.say('I walk to the Blackwood smithy.')
    play.write(f"- scene: {play.story()['scene']['place']['id']}\n")
    if play.story()['scene']['place']['id'] != 'blackwood-smithy':
        play.flag('Walking to the smithy by name did not move the scene there.')


def set_fight(play, spec: dict, zone: str = 'near'):
    """Put a fight with these foes on, as a road encounter would (the test's own setup, so it doesn't hang on the
    encounter dice)."""
    import random

    from dungeon import combat, combat5e, combat_brp, combat_iron  # the harness runs beside the app's code
    ruleset = (play.dungeon.call('GET', '/api/story/sheet') or {}).get('ruleset')
    made = (combat5e.foes_from(spec, zone, random.Random()) if ruleset == 'srd52' else
            combat_brp.foes_from(spec, zone) if ruleset == 'brp' else
            combat_iron.foes_from(spec, zone) if ruleset == 'ironsworn' else combat.foes_from(spec, zone))
    foes = [foe | ({'ranged': True} if spec.get('ranged') else {}) for foe in made]
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        connection.execute('INSERT INTO story_fight (id, round, wants, foes, initiative, bare) VALUES (1, 1, ?, ?, '
                           'NULL, 0)', (spec['wants'], json.dumps(foes)))
    play.write(f"- fight set: {spec['count']} × {spec['name']}, wants {spec['wants']}\n")


def fight_on(play) -> dict:
    return (play.story().get('fight') or {})


def robbers(play):
    """What the foes want: robbers who have hurt the character demand the purse, and handing it over ends the fight
    with the purse gone."""
    play.start('agna-holt')
    play.move('the-ford')
    set_fight(play, {'name': 'road bandit', 'count': 2, 'vitality': 10, 'resolve': 8, 'weapon': 0, 'wants': 'rob'})
    play.say('Two bandits have come out of the reeds by the ford with cudgels. I draw my sword and go for the nearer '
             'one.')
    for _ in range(5):
        state = fight_on(play)
        if not state.get('fight') or state.get('dead') or state.get('condition') not in ('unhurt', 'scratched'):
            break
        play.say('I keep swinging at the nearer bandit.')
    play.gear()
    if fight_on(play).get('fight'):
        play.say('"Fine. Take it." I toss him my purse.')
        gear = play.gear()
        if fight_on(play).get('fight'):
            play.flag('Handing the purse over to robbers did not end the fight.')
        if gear.get('coins'):
            play.flag(f"The purse is still {gear.get('coins')} after handing it to the robbers.")


def captors(play):
    """Captors fight to take the character whole: their blows stop at Maimed, and a surrender makes the character
    their prisoner. The first line fights on a plan until they break or a turning point."""
    play.start('lirien-of-the-ford')
    play.move('the-ford')
    set_fight(play, {'name': 'press-gang man', 'count': 3, 'vitality': 10, 'resolve': 10, 'weapon': 0,
                     'wants': 'capture'})
    play.say('A press gang has come down to the ford with a rope. I put my back to the water, hold my ground and '
             'cut down whoever comes, and fight on until they break.')
    state = fight_on(play)
    if state.get('fight') and not state.get('captors'):
        play.say('I drop my sword and surrender.')
        state = fight_on(play)
        play.write(f'- after surrendering: {json.dumps(state)}\n')
        if not state.get('captors'):
            play.flag('Surrendering to captors did not make the character their prisoner.')
    if state.get('dead'):
        play.flag('Captors killed the character.')


def brawler(play):
    """A brawl in the Sawpit at night: attacking a man the narrator brings in rolls and starts a fight, and backing
    off ends it."""
    play.start('tobin-pell')
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:  # the Sawpit fills at night
        at = connection.execute('SELECT at FROM story_clock WHERE id=1').fetchone()[0]
        connection.execute('UPDATE story_clock SET at=? WHERE id=1', (at[:11] + '20:30:00' + at[19:],))
    play.move('the-sawpit')
    play.say('I throw my drink in the face of the biggest logger in the place and punch him.', {'fight': True})
    if fight_on(play).get('fight'):
        play.say('I put my hands up and back off toward the door. "All right, all right, I\'m going."')
        if fight_on(play).get('fight'):
            play.flag('Backing off from a brawler did not end the fight.')


def ambush(play):
    """Surprise: a stealthy first blow rolls Sneak up unseen, and a danger's foes roll to take the character
    unawares (Spot the ambush)."""
    play.start('agna-holt')
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        at = connection.execute('SELECT at FROM story_clock WHERE id=1').fetchone()[0]
        connection.execute('UPDATE story_clock SET at=? WHERE id=1', (at[:11] + '20:30:00' + at[19:],))
    play.move('the-sawpit')
    play.say('I creep up behind the loudest drunk in the place and hit him over the head with my sword hilt.')
    if fight_on(play).get('fight'):
        play.say('I fight it out, cutting at whatever comes at me.')
    if not fight_on(play).get('fight'):
        play.say('I search the body.')
        play.say('I take the coins.')
        play.gear()
    play.move('the-heartwood')
    for _ in range(6):
        if fight_on(play).get('fight'):
            break
        play.say('I go deeper into the Heartwood, sword ready.')


def set_clock(play, hour: str):
    """Set the story clock to this hour today (the test's own setup, e.g. '20:30')."""
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        at = connection.execute('SELECT at FROM story_clock WHERE id=1').fetchone()[0]
        connection.execute('UPDATE story_clock SET at=? WHERE id=1', (at[:11] + hour + ':00' + at[19:],))
    play.clock = None  # the test turned it back, not the story
    play.write(f'- clock set to {hour}\n')


def lie_cards(play):
    """The secret insight rolls on lies so far (no roll card shows them)."""
    with play.dungeon.database() as connection:
        for card_id, lines in connection.execute("SELECT card_id, lines FROM story_cards WHERE scene='lie'"):
            play.write(f'- lie read ({card_id}): {lines[:400]}\n')


def lies(play):
    """Secrets and lies: questioning someone with something to hide makes them lie, and the character's insight is
    rolled in secret; asked again that day they keep to the same story."""
    play.start('agna-holt')
    for hour, place, line in (('09:00', 'reeves-hall', 'I ask Aldous Marr why he wants the first crews past the '
                               'border stones so fast.'),
                              ('14:00', 'reeves-hall', 'I ask Aldous Marr what he is hiding about the Heartwood.'),
                              ('08:00', 'shrine-of-tidum', 'I ask Ilse Rook why she wants the felling stopped.'),
                              ('17:00', 'shrine-of-tidum', 'I ask Ilse Rook what she knows about the Heartwood.'),
                              ('20:30', 'mother-mags', 'I ask Mag Hollin whether the watch ever looks in on what '
                               'she buys.'),
                              ('21:00', 'mother-mags', 'I ask Mag Hollin again who she pays to look the other way.')):
        set_clock(play, hour)
        play.move(place)
        around = [str(person) for person in play.story()['scene'].get('around') or []]
        play.write(f'- around: {around}\n')
        play.say(line)
    lie_cards(play)


def labour(play):
    """Day labour pays the town's wage pro rata; an empty tavern stays empty."""
    play.start('tobin-pell')
    set_clock(play, '07:00')
    play.move('timber-yards')
    before = play.gear().get('coins')
    play.say('I take an all-day hauling job at the timber yards.')
    after = play.gear().get('coins')
    if after == before:
        play.flag('A day of hauling paid nothing.')
    play.say('I work the saws for three more hours.')
    more = play.gear().get('coins')
    if more == after:
        play.flag('Three hours at the saws paid nothing.')
    set_clock(play, '15:00')
    play.move('the-sawpit')
    play.write(f"- around at the Sawpit: {[str(person) for person in play.story()['scene'].get('around') or []]}\n")
    play.say('I look around the room for someone to drink with.')


def ranges(play):
    """Range bands: an archer shoots from far off and a charge only closes to near; then, against men at arm's
    length, falling back to the stairs breaks away and moves the fight's area."""
    play.start('agna-holt')
    play.move('the-wayhouse')
    set_fight(play, {'name': 'drunk brawler', 'count': 2, 'vitality': 9, 'resolve': 9, 'weapon': 0, 'wants': 'kill'},
              zone='engaged')
    play.say('Two drunks come at me with knives. I fall back to the stairs.')
    state = fight_on(play).get('fight') or {}
    play.write(f'- fight: {json.dumps(state)}\n')
    if state and 'stair' not in (state.get('area') or ''):
        play.flag(f"Falling back to the stairs left the fight's area at {state.get('area')}.")
    for _ in range(3):
        if not fight_on(play).get('fight') or fight_on(play).get('dead'):
            break
        play.say('I hold the stairs and cut at whoever comes up.')
    if fight_on(play).get('fight') or fight_on(play).get('dead'):
        return
    set_fight(play, {'name': 'warden archer', 'count': 1, 'vitality': 9, 'resolve': 9, 'weapon': 0, 'wants': 'kill',
                     'ranged': True}, zone='far')
    play.say('An archer has come in at the far end of the common room, bow drawn. I charge him.')
    play.write(f"- fight: {json.dumps(fight_on(play).get('fight'))}\n")
    if fight_on(play).get('fight'):
        play.say('I throw my belt knife at the archer.')
        play.write(f"- fight: {json.dumps(fight_on(play).get('fight'))}\n")


def shut_shop(play):
    """A shut counter: at night, buying or selling at Pell's is told the shop is shut, and no money moves."""
    play.start('tobin-pell')
    play.move('pell-provisions')
    set_clock(play, '22:30')
    before = play.gear()
    play.say('I buy a hooded lantern.')
    play.say('I sell my ledger book over the counter.')
    after = play.gear()
    if after.get('coins') != before.get('coins'):
        play.flag(f"Money moved at a shut shop: {before.get('coins')} to {after.get('coins')}.")


def dice_log(play):
    """The dice log: every roll of the branch, turn by turn, newest first, with a tally; nothing while the dice are
    hidden."""
    play.start('agna-holt')
    play.say('I arm-wrestle the biggest logger in the Felled Oak for a round of drinks.')
    play.say('I try to talk the keeper into a free bowl of stew.')
    play.say('I take a seat by the fire.')
    log = play.dungeon.call('GET', '/api/story/dice-log')
    turns = log.get('turns') or []
    play.write(f"- dice log: shown {log.get('shown')}, {len(turns)} turns, tally {json.dumps(log.get('tally'))}\n")
    for turn in turns:
        play.write(f'  - {json.dumps(turn, ensure_ascii=False)[:400]}\n')
    rolled = sum(len(turn.get('rolls') or []) for turn in turns)
    if not turns or not rolled:
        play.flag('The dice log shows no rolls after two rolling lines.')
    play.attempt('Hide the dice', 'PUT', '/api/story/table', {'show_odds': False})
    hidden = play.dungeon.call('GET', '/api/story/dice-log')
    play.write(f"- hidden: shown {hidden.get('shown')}, {len(hidden.get('turns') or [])} turns\n")
    if hidden.get('turns'):
        play.flag('The dice log still lists rolls with the dice hidden.')


def haggling(play):
    """Opposed haggling: the keeper's Resolve against the character's Allure, held at the counter for the day."""
    play.start('tobin-pell')
    play.move('pell-provisions')
    play.gear()
    play.say('I haggle hard over the hooded lantern, reminding Margery I am family and the Guild pays late.',
             {'roll': True})
    gear = play.gear()
    play.write(f"- haggled: {(gear.get('shop') or {}).get('haggled')}\n")
    play.say('I buy the hooded lantern at that price.')
    play.gear()


def life_cards(play):
    """Life Cards that do what they say: several days in Kingswood, with every card drawn logged, and the journal and
    sheet after (quests, rumors, fates, pursuers)."""
    play.start('agna-holt')
    for line in ('I spend the day around the Felled Oak, listening for work.',
                 'I sleep until morning.',
                 'I spend the day at the Crossroads market, asking after news.',
                 'I sleep until morning.',
                 'I spend the day on the green, watching who signs the contract.',
                 'I sleep until morning.'):
        play.say(line)
    play.journal()
    play.sheet()


def bonds(play):
    """Bonds: swearing to stand by someone there forges a bond; it shows on the sheet and in People you've met."""
    play.start('agna-holt')
    play.say('I take a seat at the bar and talk with Corin Ashby about the Heartwood contract.')
    play.say('I clasp Corin\'s hand. "I swear to stand by you, Corin, whatever comes of this contract."')
    view = play.story()
    bonded = [person.get('name') for person in view.get('people') or [] if person.get('bond')]
    play.write(f'- bonded in People: {bonded}\n')
    sheet = play.sheet()
    if not bonded:
        play.flag('Swearing to stand by Corin made no bond in People you have met.')
    if 'bond' not in json.dumps(sheet).lower():
        play.flag('The sheet shows no Bonds track after swearing a bond.')
    play.say('I ask Corin to watch my back tomorrow at the border stones.')


def party(play):
    """Companions: someone bonded comes along when asked, is in every scene with the character, fights beside them,
    and leaves when told to go home."""
    play.start('agna-holt')
    set_clock(play, '12:00')  # Corin keeps the Felled Oak by day
    play.say('I take a seat at the bar and talk with Corin Ashby about the Heartwood contract.')
    play.say('I clasp Corin\'s hand. "I swear to stand by you, Corin."')
    play.say('"Come with me, Corin. I could use someone at my back."')
    view = play.story()
    play.write(f"- party: {[person.get('name') for person in view.get('people') or [] if person.get('party')]}\n")
    play.move('the-sawpit')
    around = [str(person) for person in play.story()['scene'].get('around') or []]
    play.write(f'- around at the Sawpit: {around}\n')
    if not any('Corin' in person for person in around):
        play.flag(f'Corin did not come along to the Sawpit: {around}')
    set_fight(play, {'name': 'drunk brawler', 'count': 2, 'vitality': 9, 'resolve': 9, 'weapon': 0, 'wants': 'kill'},
              zone='engaged')
    for line in ('Two drunks come at us with knives. I draw my sword and go for the nearer one.',
                 'I keep at the nearer drunk.', 'I keep fighting.'):
        if not fight_on(play).get('fight'):
            break
        play.say(line)
    play.say('"Go home, Corin. I can take it from here."')
    view = play.story()
    play.write(f"- party after: {[person.get('name') for person in view.get('people') or [] if person.get('party')]}\n")


def ironsworn_vows(play):
    """Ironsworn progress: an iron vow, a landed roll that names it (Reach a Milestone), a sworn bond on the bonds
    track, and the vow fulfilled with a progress roll."""
    choices = play.dungeon.call('GET', '/api/story/start').get('ironsworn') or {}
    placed = dict(zip(('iron', 'edge', 'wits', 'heart', 'shadow'), choices.get('array') or [3, 2, 2, 1, 1]))
    by_category = {}
    for asset in choices.get('assets') or []:
        by_category.setdefault(asset['category'], asset['id'])
    picks = list(by_category.values())[:choices.get('count') or 3]
    play.start(persona={'name': 'Hald Brenner', 'gender': 'man', 'age': 41,
                        'about': 'A sworn sword out of Bastion who keeps his oaths and little else.'},
               ruleset='ironsworn', ironsworn={'stats': placed, 'assets': picks})
    set_clock(play, '12:00')
    play.say('I swear an iron vow to find whoever is breaking the saws at the mill, whatever it costs.')
    play.sheet()
    for line in ('I question the mill hands about who has been breaking the saws at the mill.',
                 'I watch the mill from the timber stacks, looking for whoever is breaking the saws.',
                 'I follow the tracks from the broken saws at the mill.'):
        play.say(line, {'roll': True})
    play.sheet()
    play.say('I clasp Corin Ashby\'s hand. "I swear to stand by you, Corin."')
    play.say('I catch the man breaking the saws at the mill red-handed and drag him to the guild factor. The vow '
             'is done: I found whoever was breaking the saws.')
    play.sheet()
    play.journal()


def fate_stress(play):
    """Fate stress and consequences: blows taken in a fight mark stress boxes, then consequences in words; nights of
    rest heal them."""
    play.start('tobin-pell', ruleset='fate')
    set_clock(play, '20:30')
    play.move('the-sawpit')
    play.say('I throw my drink in the face of the biggest logger in the place and punch him.', {'fight': True})
    for line in ('I punch him again.', 'I keep swinging.', 'I duck and hit back.', 'I keep at it.'):
        state = fight_on(play)
        if not state.get('fight') or state.get('dead'):
            break
        play.say(line)
    play.sheet()
    if fight_on(play).get('fight'):
        play.say('I put my hands up and back off toward the door. "All right, I\'m going."')
    for _ in range(3):
        play.say('I sleep until morning.')
    play.sheet()


def away(play, hours: float):
    """Pretend the player closed the app this many hours ago (the real-time mark, story_real, moved back)."""
    from datetime import datetime, timedelta
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        row = connection.execute('SELECT at FROM story_real WHERE id=1').fetchone()
        if row:
            at = datetime.fromisoformat(row[0]) - timedelta(hours=hours)
            connection.execute('UPDATE story_real SET at=? WHERE id=1', (at.isoformat(),))
    play.write(f"- away for {hours} hours ({'mark moved back' if row else 'no real-time mark kept'})\n")
    return bool(row)


def real_time(play):
    """Real-time worlds: Havenbrooke keeps moving while the app is closed (time since the last line passes before the
    next, and the narrator hears about the gap); the Table's World clock set to story time stops it."""
    play.dungeon.call('PUT', '/api/story/scene', {'city_id': 'haven', 'place_id': 'nexus-housing'})
    play.dungeon.call('DELETE', '/api/story')
    premades = play.dungeon.call('GET', '/api/story/start').get('premades') or []
    if not premades:
        play.flag('No Havenbrooke premades offered in Haven.')
        return
    play.start(premades[0]['id'])
    rules = play.dungeon.call('GET', '/api/story/table')
    play.write(f"- World clock: {rules.get('clock')}\n")
    play.say('I unpack the last of my boxes and put my posters up.')
    before = play.story()['scene']['local_time']
    if away(play, 5):
        play.clock = None
        play.say('I check my phone and head down to the dining hall.')
        after = play.story()['scene']['local_time']
        play.write(f'- story time {before} then {after}\n')
        if after[:13] <= before[:13]:
            play.flag(f'Five hours away passed no time in a real-time world: {before} then {after}.')
    else:
        play.flag('Havenbrooke keeps no real-time mark.')
    play.attempt('World clock: story time', 'PUT', '/api/story/table', {'clock': 'story'})
    before = play.story()['scene']['local_time']
    away(play, 5)
    play.say('I grab a tray and find a table.')
    after = play.story()['scene']['local_time']
    play.write(f'- story time {before} then {after} with the clock on story time\n')
    if after[:13] > before[:13]:
        play.flag(f'With the World clock on story time, five hours away still passed: {before} then {after}.')


def fivee_start(play, class_id: str, name: str, about: str, scores: dict, levels: int = 2, hurt: int = 0):
    """A 5E character of this class, raised `levels` levels as written (the test's own advance, to reach the
    subclass), and `hurt` hit points down."""
    from dungeon.rules import srd52  # the harness runs beside the app's code
    srd = play.dungeon.call('GET', '/api/story/start').get('srd52') or {}
    chosen = next(item for item in srd.get('classes') or [] if item['id'] == class_id)
    background = (srd.get('backgrounds') or [{}])[0]
    ids = {skill['name']: skill['id'] for skill in srd.get('skills') or []}
    picks = [ids.get(skill, skill) for skill in chosen['skills']['from'] if skill not in (background.get('skills') or [])]
    play.start(persona={'name': name, 'gender': 'woman', 'age': 33, 'about': about}, ruleset='srd52',
               build={'class_id': class_id, 'species_id': 'human', 'background_id': background['id'], 'scores': scores,
                      'skills': picks[:chosen['skills']['count']]})
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:
        sheet = json.loads(connection.execute('SELECT data FROM story_sheet WHERE id=1').fetchone()[0])
        for _ in range(levels):
            sheet, gained = srd52.advance(sheet)
            play.write(f"- advanced to level {sheet['level']}: {gained}\n")
        sheet['xp'] = srd52.xp_for(sheet['level']) or sheet.get('xp', 0)
        sheet['hp'] = max(1, sheet['hp'] - hurt)
        connection.execute('UPDATE story_sheet SET data=? WHERE id=1', (json.dumps(sheet),))
    return play.sheet()


def fivee_cleric(play):
    """5E subclasses and upcasting: a Life Domain cleric at level 3 heals with Cure Wounds at 2nd level (Disciple of
    Life adds 2 + the slot's level), then lays Hold Person on a thug and hits him while he is paralyzed."""
    fivee_start(play, 'cleric', 'Maren Holt', 'A field priest of Tidum who followed the levy north and stayed.',
                {'wis': 15, 'con': 14, 'str': 13, 'dex': 12, 'cha': 10, 'int': 8}, hurt=8)
    play.say('I cast Cure Wounds at 2nd level on myself.', {'roll': True})
    play.sheet()
    play.move('the-ford')
    set_fight(play, {'name': 'road thug', 'count': 1, 'vitality': 10, 'resolve': 8, 'weapon': 0, 'wants': 'rob'})
    sqlite3 = __import__('sqlite3')
    with sqlite3.connect(play.dungeon.data_dir / 'dungeon.sqlite3') as connection:  # hurt again, for Healing Word
        sheet = json.loads(connection.execute('SELECT data FROM story_sheet WHERE id=1').fetchone()[0])
        sheet['hp'] = max(1, sheet['hp'] - 10)
        connection.execute('UPDATE story_sheet SET data=? WHERE id=1', (json.dumps(sheet),))
    play.write(f"- hurt to {sheet['hp']} hit points\n")
    play.say('A thug comes at me by the ford. I cast Healing Word on myself and hit the thug with my mace.')
    play.write(f"- fight: {json.dumps(fight_on(play).get('fight'))}\n")
    if fight_on(play).get('fight'):
        play.say('I cast Guiding Bolt at the thug with a 2nd-level slot.')
    play.sheet()


def fivee_evoker(play):
    """An Evoker wizard at level 3: Magic Missile with a 2nd-level slot (three darts, always hitting), and a cantrip
    whose made save still does half (Potent Cantrip)."""
    fivee_start(play, 'wizard', 'Oriel Fenn', 'A hedge scholar from Eriane who reads ley lines for the Guild.',
                {'int': 15, 'con': 14, 'dex': 13, 'wis': 12, 'cha': 10, 'str': 8})
    play.move('the-ford')
    set_fight(play, {'name': 'road thug', 'count': 2, 'vitality': 10, 'resolve': 8, 'weapon': 0, 'wants': 'kill'})
    play.say('Two thugs come at me by the ford. I cast Burning Hands at the nearer one at 2nd level.')
    for line in ('I cast Magic Missile at the other thug.', 'I cast Ice Knife at whoever is still standing.',
                 'I cast Fire Bolt again.'):
        if not fight_on(play).get('fight') or fight_on(play).get('dead'):
            break
        play.say(line)
    play.sheet()


def brp_magic(play):
    """BRP magic: a wizard casts Light out of a fight and Blast 2 in one on power points, never spending the last;
    sleep brings the points back."""
    choices = play.dungeon.call('GET', '/api/story/start').get('brp') or {}
    professions = [item.get('id') for item in choices.get('professions') or []]
    play.write(f'- professions: {professions}\n')
    if 'wizard' not in professions:
        play.flag('No wizard profession offered under Percentile.')
        return
    play.start(persona={'name': 'Ysolde Varr', 'gender': 'woman', 'age': 40,
                        'about': 'A guild-trained wizard from Eriane who came north to read the ley stones.'},
               ruleset='brp', brp={'characteristics': {'str': 10, 'con': 11, 'siz': 11, 'cha': 11, 'dex': 11,
                                                       'int': 13, 'pow': 13},
                                   'profession': 'wizard', 'personality': 'cunning'})
    play.sheet()
    play.say('I cast a Light spell so I can read the notice on the green.', {'roll': True})
    play.move('the-ford')
    set_fight(play, {'name': 'road thug', 'count': 1, 'vitality': 10, 'resolve': 8, 'weapon': 0, 'wants': 'kill'})
    play.say('A thug comes at me by the ford. I cast Blast 2 at him.')
    for line in ('I cast Protection 2 on myself.', 'I cast Blast 3 at the thug.', 'I cast Blast 3 at the thug again.'):
        if not fight_on(play).get('fight') or fight_on(play).get('dead'):
            break
        play.say(line)
    play.sheet()
    play.say('I sleep the night at the Wayhouse.')
    play.sheet()


def town_quests(play):
    """Town adventures: a BABEL start on the Concourse begins its quests; reaching Hollin mid-campaign begins
    Hollin's (once, deadlines from the arrival); a dangerous place there and a search with its finds."""
    play.dungeon.call('PUT', '/api/story/scene', {'city_id': 'the-concourse', 'place_id': 'the-plaza'})
    play.dungeon.call('DELETE', '/api/story')
    premades = play.dungeon.call('GET', '/api/story/start').get('premades') or []
    if not premades:
        play.flag('No BABEL premades offered on the Concourse.')
        return
    play.start(premades[0]['id'])
    play.journal()
    play.say('I set out for Hollin.')
    play.write(f"- scene: {play.story()['scene']['place']['id']} in {play.story()['scene']['city']['name']}\n")
    play.journal()
    play.say('I go down into the bone-cellar with a lamp and look around.')
    play.say('I search the bone-cellar for anything worth carrying.')
    play.gear()


SCENARIOS = {'town': town, 'shop': shop, 'heartwood': heartwood, 'brawl': brawl, 'road': road,
             'director': director, 'chapters': chapters, 'ironman': ironman, 'gm_view': gm_view, 'memory': memory,
             'legacy': legacy, 'fivee_checks': fivee_checks, 'fivee_fight': fivee_fight,
             'fivee_caster': fivee_caster, 'ironsworn': ironsworn, 'percentile': percentile,
             'lore': lore, 'narrative': narrative, 'fivee_defeat_aim': fivee_defeat_aim,
             'fivee_defeat_written': fivee_defeat_written, 'importer': importer,
             'editor': editor, 'pictures': pictures, 'havenbrooke': havenbrooke,
             'tone': tone, 'restrained_wounds': restrained_wounds, 'stage': stage, 'babel': babel,
             'fate_made': fate_made, 'fate_premade': fate_premade, 'marvel_start': marvel_start,
             'hex_vallarith': hex_vallarith, 'hex_woods': hex_woods, 'hamlet': hamlet, 'fence': fence,
             'narration_format': narration_format, 'selling': selling, 'wayhouse': wayhouse, 'grime': grime,
             'spoils': spoils, 'mending': mending, 'town_map': town_map,
             'robbers': robbers, 'captors': captors, 'brawler': brawler, 'ambush': ambush,
             'lies': lies, 'labour': labour, 'ranges': ranges, 'shut_shop': shut_shop,
             'dice_log': dice_log, 'haggling': haggling, 'life_cards': life_cards, 'bonds': bonds, 'party': party,
             'ironsworn_vows': ironsworn_vows, 'fate_stress': fate_stress, 'real_time': real_time,
             'fivee_cleric': fivee_cleric, 'fivee_evoker': fivee_evoker, 'brp_magic': brp_magic, 'town_quests': town_quests}
