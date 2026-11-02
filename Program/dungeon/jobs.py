"""Jobs from factions' needs (requirements "Quests and factions"; docs/story.md "Jobs and oaths").

Each faction in play lists the jobs it needs done in the towns it holds (world/data/factions/<world>.json `jobs`).
On a day in town, while a faction holding the town has no job open, it may offer one (OFFER in 100): a quest of the
job's own, known to the character, with its deadline on the story clock, its pay in the town's day wages and the
standing it earns. Whether it is done is the Continuity model's call, as for any quest (dungeon/quests.py); a job
that lapses costs nothing but what happens, one failed costs standing. Each job carries the loose ends it leaves
(`ties`) for the story director.
"""
import random
import re
from datetime import datetime, timedelta

from dungeon import director, factions, inventory, quests, tiers
from dungeon.database import many

OFFER = 50
# A line that goes looking for work: lower-tier work comes only to those who do.
SEEKING = re.compile(r"\b(work|jobs?|notices?|notice board|hiring|errands?|anyone need)\b", re.I)


def seeking(text: str) -> bool:
    return bool(SEEKING.search(text))


def offer(connection, world: str, node_id: str, city_id: str, wage: int, currency: dict, now: datetime,
          rng=None, looking: bool = False) -> list[str]:
    """A job a faction holding the town may offer today, at the character's tier (or below, when they go
    `looking`); the line that tells the narrator."""
    if not factions.ACTIVE:
        return []
    rng = rng or random.SystemRandom()
    character = tiers.tier(connection, world)
    at, stretch = tiers.offer_tiers(character, looking, rng)
    rows = many(connection, "SELECT faction_id, title, status FROM story_quests WHERE kind='job' AND institution IS NULL")
    busy = {row['faction_id'] for row in rows if row['status'] == 'open'}
    offered = {(row['faction_id'], row['title']) for row in rows}
    open_jobs = [(faction, job) for faction in factions.local(world, node_id) if faction['id'] not in busy
                 for job in faction.get('jobs', []) if (faction['id'], job['title']) not in offered
                 and job.get('tier', 1) in at]
    if not open_jobs or (not looking and rng.randint(1, 100) > OFFER):
        return []
    faction, job = rng.choice(open_jobs)
    pay = job['wages'] * wage
    # Some work links straight into an arc in play, and leaves one of its seeds behind (dungeon/director.py).
    arc_id, clue = director.link(connection, world, rng)
    quests.create(connection, 'job', city_id, job['title'], job['hook'], job['truth'], job['missed'],
                  (now + timedelta(days=job['days'])).isoformat(), faction_id=faction['id'], giver=job['giver'],
                  reward=pay, standing=job['standing'], ties=job['ties'] + clue, tier=job.get('tier', 1),
                  arc_id=arc_id)
    warned = [tiers.stretch_text(job.get('tier', 1), character)] if stretch else []
    return [f"Work is going: {job['giver']} ({faction['name']}) wants it done within {job['days']} days, for "
            f"{inventory.money_text(pay, currency)}: {job['hook']}", *warned]
