"""Play real sessions of the Dungeon end to end, with a real model, and write what happened.

Each scenario starts its own Dungeon (scripts/acceptance/serve.py) on a fresh data folder, sets up a Claude Code
profile for the narrator, Referee and Continuity jobs, and plays its lines through the API the screen uses. The
transcript (narration, rolls, the fight, gear, journal, the director's hidden note) goes in a Markdown file per
scenario, with checks that flag what looks wrong.

    python scripts/playtest/playtest.py --account-dir C:/Users/me/.claude-account2 --out playtests
    python scripts/playtest/playtest.py --only shop,heartwood --model sonnet

--account-dir is a Claude Code account folder (CLAUDE_CONFIG_DIR) already signed in with `claude`, so playtests
can run on a second account. Without it the usual account is used.
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path

import httpx
from scenarios import SCENARIOS

PROGRAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROGRAM))
from dungeon.identity import CLIENT_HEADER  # noqa: E402


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class Dungeon:
    """One running Dungeon on its own data folder."""

    def __init__(self, data_dir: Path, log):
        self.data_dir = data_dir
        self.port = free_port()
        environment = {**os.environ, 'DUNGEON_DATA_DIR': str(data_dir), 'PYTHONPATH': str(PROGRAM)}
        self.process = subprocess.Popen([sys.executable, str(PROGRAM / 'scripts' / 'acceptance' / 'serve.py'),
                                         '--port', str(self.port)], cwd=PROGRAM, env=environment,
                                        stdout=log, stderr=subprocess.STDOUT)
        self.http = httpx.Client(base_url=f'http://127.0.0.1:{self.port}', timeout=900,
                                  headers={CLIENT_HEADER: 'workspace'})
        for _ in range(120):
            try:
                if self.http.get('/api/health').status_code == 200:
                    return
            except httpx.TransportError:
                pass
            if self.process.poll() is not None:
                raise RuntimeError('The Dungeon stopped while starting; see the server log.')
            time.sleep(0.5)
        raise RuntimeError('The Dungeon did not start.')

    def call(self, method: str, path: str, body=None, ok=(200, 201)):
        response = self.http.request(method, path, json=body)
        if response.status_code not in ok:
            raise ApiError(response.status_code, response.text)
        return response.json() if response.content else None

    def database(self):
        return sqlite3.connect(f'file:{self.data_dir / "dungeon.sqlite3"}?mode=ro', uri=True)

    def stop(self):
        self.http.close()
        self.process.terminate()
        try:
            self.process.wait(10)
        except subprocess.TimeoutExpired:
            self.process.kill()


def label(thing) -> str:
    if isinstance(thing, dict):
        return str(thing.get('label') or thing.get('name') or thing.get('key') or thing)
    return str(thing)


class ApiError(Exception):
    def __init__(self, status, text):
        super().__init__(f'{status}: {text[:400]}')
        self.status = status


def set_up(dungeon: Dungeon, account_dir: str, model: str, helper_model: str, effort: str | None):
    dungeon.call('PUT', '/api/settings', {'show_odds': True, 'ai_notice_confirmed': True})
    common = {'provider': 'claude_code', 'cli_account_dir': account_dir, 'timeout_seconds': 600,
              'max_output_tokens': 1200}
    if effort:
        common['reasoning_effort'] = effort
    narrator = dungeon.call('POST', '/api/models/profiles', {'name': f'Playtest {model}',
                                                             'config': common | {'model': model}})
    helper = dungeon.call('POST', '/api/models/profiles', {'name': f'Playtest {helper_model}',
                                                           'config': common | {'model': helper_model}})
    who = dungeon.call('POST', f"/api/models/profiles/{narrator['id']}/check")
    jobs = {job['key'] for job in dungeon.call('GET', '/api/models')['jobs']}
    for job, profile in (('chat', narrator), ('story', narrator), ('referee', helper), ('continuity', helper),
                         ('director', helper), ('importer', narrator)):
        if job in jobs:
            dungeon.call('PUT', '/api/models/routes', {'job': job, 'profile_id': profile['id']})
    return who.get('note', '')


class Play:
    """A scenario's lines played against one Dungeon, written to its transcript as they go."""

    def __init__(self, dungeon: Dungeon, out):
        self.dungeon = dungeon
        self.out = out
        self.problems: list[str] = []
        self.turns = 0

    def write(self, text: str = ''):
        self.out.write(text + '\n')
        self.out.flush()

    def flag(self, text: str):
        self.problems.append(text)
        self.write(f'> **FLAG:** {text}')

    def story(self):
        return self.dungeon.call('GET', '/api/story')

    def start(self, premade=None, persona=None, stats=None, **choices):
        body = {'premade_id': premade} if premade else {'persona': persona, 'stats': stats}
        # The dice show, so the transcript has every roll (the Table keeps it per campaign).
        choices['table'] = {'show_odds': True} | (choices.get('table') or {})
        self.dungeon.call('POST', '/api/story/start', body | choices)
        view = self.story()
        scene = view['scene']
        self.write(f"## Start: {premade or persona['name']}\n")
        self.write(f"{scene['place']['name']}, {scene['city']['name']}, {scene['local_time']}\n")
        for message in view['messages']:
            self.write(f"_{message['role']}:_ {message['text']}\n")

    def move(self, place_id: str, city_id='kingswood'):
        try:
            self.dungeon.call('PUT', '/api/story/scene', {'city_id': city_id, 'place_id': place_id})
            self.write(f'### Move to {place_id}\n')
        except ApiError as error:
            self.write(f'### Move to {place_id} refused ({error})\n')

    def say(self, text: str, expect: dict | None = None):
        """One line, streamed as the screen does; then what code decided, and checks on it."""
        self.turns += 1
        self.write(f'### {self.turns}. > {text}\n')
        started = time.monotonic()
        done, error, first = None, None, None
        with self.dungeon.http.stream('POST', '/api/story/messages/stream',
                                      json={'text': text, 'client_id': uuid.uuid4().hex}) as response:
            if response.status_code != 200:
                response.read()
                error = f'{response.status_code}: {response.text[:400]}'
            else:
                for line in response.iter_lines():
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if 'text' in item and first is None:
                        first = time.monotonic() - started
                    done = item.get('done', done)
                    if 'error' in item:
                        error = f"{item.get('status')} {item.get('code')}: {item['error']}"
        took = time.monotonic() - started
        error = error or (None if done else 'the stream ended with no reply and no error')
        if error:
            self.write(f'**Error:** {error}\n')
            if not (expect or {}).get('error'):
                self.flag(f'Turn {self.turns} failed: {error}')
            return None
        reply = done['reply']
        self.write(reply.get('text') or f"_(no text; status {reply.get('status')}: {reply.get('error')})_")
        self.write()
        if reply.get('status') == 'failed':
            self.flag(f"Turn {self.turns} reply failed: {reply.get('error')}")
        view = self.story()
        user = next((m for m in reversed(view['messages']) if m['role'] == 'user'), {})
        # The story clock only moves forward, except when going back (which resets this).
        now = view['scene']['local_time']
        if getattr(self, 'clock', None) and now < self.clock:
            self.flag(f'The story clock ran backwards: {self.clock} then {now}.')
        self.clock = now
        self.details(view, user, took, first)
        self.check(text, reply.get('text') or '', view, user, expect or {})
        return view

    def details(self, view: dict, user: dict, took: float, first):
        for roll in user.get('rolls') or []:
            self.write(f"- roll: {json.dumps(roll, ensure_ascii=False)}")
        pace = user.get('pace') or {}
        self.write(f"- time: {took:.0f}s total, first text {first or 0:.0f}s; steps "
                   f"{json.dumps(pace.get('steps'), ensure_ascii=False)}; skipped {pace.get('skipped')}")
        fight = view.get('fight') or {}
        if fight.get('fight') or fight.get('dead') or fight.get('condition'):
            self.write(f"- fight: {json.dumps(fight, ensure_ascii=False)}")
        scene = view['scene']
        self.write(f"- scene: {scene['place']['name']} ({scene['city']['name']}), {scene['local_time']}, "
                   f"around: {', '.join(label(p) for p in scene.get('around') or [])}")
        for card in self.cards(user.get('id')):
            self.write(f'- {card[0]}: {card[1]}')
        for line in self.rounds(user.get('id')):
            self.write(f'- round: {line}')
        flags = next((m for m in reversed(view['messages']) if m['role'] == 'narrator'), {}).get('flags')
        if flags:
            self.write(f'- flagged passages: {json.dumps(flags, ensure_ascii=False)}')
        self.write()

    def rounds(self, message_id) -> list[str]:
        """The fight round kept with the line, if one was fought (a fight can start and end on the same line)."""
        if not message_id:
            return []
        with self.dungeon.database() as connection:
            row = connection.execute('SELECT lines FROM story_rounds WHERE message_id=?', (message_id,)).fetchone()
        return json.loads(row[0]) if row else []

    def cards(self, message_id):
        """The hidden things kept with the line: the director's note, beats, Life Cards (story_cards)."""
        if not message_id:
            return []
        with self.dungeon.database() as connection:
            rows = connection.execute('SELECT scene, lines FROM story_cards WHERE message_id=?', (message_id,))
            return [(scene, ' / '.join(str(line) for line in json.loads(lines or '[]'))) for scene, lines in rows
                    if lines and lines != '[]']

    def check(self, text: str, narration: str, view: dict, user: dict, expect: dict):
        if '—' in narration:
            self.flag('An em dash got through.')
        lowered = narration.lower()
        for tell in ('as an ai', 'language model', 'i cannot', "i can't continue"):
            if tell in lowered:
                self.flag(f'Narration breaks character ("{tell}").')
        if expect.get('roll') and not user.get('rolls'):
            self.flag(f'Expected a roll for "{text}" and none was made.')
        if expect.get('no_roll') and user.get('rolls'):
            self.flag(f'Expected no roll for "{text}", got {len(user["rolls"])}.')
        if expect.get('fight') and not (view.get('fight') or {}).get('fight') and not self.rounds(user.get('id')):
            self.flag(f'Expected a fight after "{text}" and none is on.')
        if expect.get('place') and view['scene']['place']['id'] != expect['place']:
            self.flag(f"Expected to be at {expect['place']}, at {view['scene']['place']['id']}.")
        words = len(narration.split())
        if words > expect.get('max_words', 450):
            self.flag(f'Narration is long: {words} words.')

    def gear(self):
        gear = self.dungeon.call('GET', '/api/story/gear')
        items = ', '.join(f"{i.get('name')} x{i.get('qty', 1)}"
                          + (' (stolen)' if i.get('stolen') else '')
                          + (f" ({i['condition']})" if i.get('condition') not in (None, 'sound') else '')
                          for i in gear.get('items') or [])
        self.write(f"- purse {gear.get('coins')} {gear.get('currency')}, slots {json.dumps(gear.get('slots'))}, "
                   f"pack: {items}")
        if gear.get('looks'):
            self.write(f"- looks: {json.dumps(gear['looks'])}")
        if gear.get('shop'):
            shop = gear['shop']
            stock = ', '.join(f"{s.get('name')} {s.get('price')}" for s in (shop.get('stock') or [])[:12])
            cash = f" cash={shop['cash']}" if 'cash' in shop else ''
            self.write(f"- shop open={shop.get('open')} keeper={shop.get('keeper')}{cash}: {stock}")
        self.write()
        return gear

    def buy(self, item_id: str, qty=1):
        try:
            self.dungeon.call('POST', '/api/story/shop/buy', {'item_id': item_id, 'qty': qty})
            self.write(f'### Buy {qty} {item_id} at the counter\n')
        except ApiError as error:
            self.write(f'### Buy {item_id} refused ({error})\n')

    def journal(self):
        journal = self.dungeon.call('GET', '/api/story/journal')
        self.write('#### Journal')
        for quest in journal.get('quests') or []:
            self.write(f"- quest {quest.get('title')}: {quest.get('status')}, left {quest.get('left')}")
        for thread in journal.get('threads') or []:
            self.write(f"- loose end: {json.dumps(thread, ensure_ascii=False)[:300]}")
        for entry in (journal.get('entries') or [])[:25]:
            self.write(f"- {entry.get('kind')} / {entry.get('subject')}: {entry.get('text')}")
        self.write()
        return journal

    def sheet(self):
        sheet = self.dungeon.call('GET', '/api/story/sheet')
        self.write(f"- sheet: {json.dumps(sheet, ensure_ascii=False)[:2000]}\n")
        return sheet

    def people(self):
        view = self.story()
        for person in view.get('people') or []:
            self.write(f"- met {person.get('name')}: {person.get('meetings')} meetings, "
                       f"{json.dumps(person.get('feelings'), ensure_ascii=False)}")
        self.write()

    def back(self, turns_ago: int):
        """Go back to before the player's line `turns_ago` lines from the end, as the screen's "Go back here"."""
        view = self.story()
        lines = [m for m in view['messages'] if m['role'] == 'user']
        target = lines[-turns_ago]
        result = self.dungeon.call('POST', '/api/story/back', {'message_id': target['id']})
        self.clock = None
        self.write(f"### Go back to before \"{target['text']}\" (draft: {result.get('draft')!r})\n")
        return result.get('draft') or target['text']

    # Milestone 3: chapters, bookmarks, the notebook, the GM view, export ----------------------------------------

    def attempt(self, label: str, method: str, path: str, body=None, expect_refusal=False):
        """A screen action that may be refused; a refusal is a finding unless the scenario expects one."""
        try:
            result = self.dungeon.call(method, path, body)
        except ApiError as error:
            self.last_error = str(error)
            self.write(f'### {label}: refused ({error})\n')
            if not expect_refusal:
                self.flag(f'{label} was refused: {error}')
            return None
        self.write(f'### {label}\n')
        if path.endswith(('/back', '/go')) or '/switch' in path:
            # Playing from a chapter, a bookmark or another branch puts the clock where that line was.
            self.clock = None
        if expect_refusal:
            self.flag(f'{label} should have been refused.')
        return result

    def lines(self) -> list[dict]:
        return [m for m in self.story()['messages'] if m['role'] == 'user']

    def chapters(self):
        campaign = self.story().get('campaign') or {}
        self.write('#### Chapters')
        for chapter in campaign.get('chapters') or []:
            self.write(f"- {chapter.get('number')}. {chapter.get('title') or '(untitled)'} "
                       f"[{'open' if chapter.get('open') else 'closed'}, {chapter.get('turns')} lines, "
                       f"by {chapter.get('ended_by') or chapter.get('reason') or '-'}]: {chapter.get('summary') or ''}"
                       + (f" Still open: {chapter['hook']}" if chapter.get('hook') else ''))
        for branch in campaign.get('tree') or []:
            self.write(f"- branch {json.dumps(branch, ensure_ascii=False)[:300]}")
        for mark in campaign.get('bookmarks') or []:
            self.write(f"- bookmark {json.dumps(mark, ensure_ascii=False)[:200]}")
        self.write(f"- ironman: {campaign.get('ironman')}, pending break: {campaign.get('pending')}\n")
        return campaign

    def gm(self):
        behind = self.dungeon.call('GET', '/api/story/gm')
        self.write('#### Behind the story (GM view)')
        for quest in behind.get('quests') or []:
            self.write(f"- quest {quest.get('title')}: {quest.get('status')}, known {quest.get('known')}")
        for seed in behind.get('seeds') or []:
            self.write(f"- seed [{seed.get('status')}] {seed.get('text')}")
        for plan in behind.get('plans') or []:
            for beat in plan.get('beats') or []:
                self.write(f"- beat {plan['arc_id']} stage {plan['stage']} [{beat.get('source')}"
                           f"{', used' if beat.get('used') else ''}{', cut' if beat.get('cut') else ''}]: "
                           f"{beat.get('text')}")
        for person in behind.get('people') or []:
            self.write(f"- person {person.get('name')}: {json.dumps(person.get('feelings'), ensure_ascii=False)}")
        self.write(f"- corrections: {len(behind.get('corrections') or [])}\n")
        return behind

    def export(self):
        for format in ('md', 'epub', 'pdf'):
            response = self.dungeon.http.get('/api/story/export/book', params={'format': format})
            self.write(f"### Export the book as {format}: {response.status_code}, {len(response.content)} bytes, "
                       f"{response.headers.get('content-type')}")
            if response.status_code != 200 or not response.content:
                self.flag(f'Book export as {format} failed: {response.status_code} {response.text[:200]}')
            elif format == 'md':
                self.write('```\n' + response.text[:1500] + '\n```')
        campaign = self.dungeon.http.get('/api/story/export/campaign')
        self.write(f'### Export the campaign: {campaign.status_code}, {len(campaign.content)} bytes\n')
        if campaign.status_code != 200:
            self.flag(f'Campaign export failed: {campaign.status_code} {campaign.text[:200]}')
            return None
        return campaign.content


def run(name: str, scenario, args, out_dir: Path):
    data_dir = Path(tempfile.mkdtemp(prefix=f'playtest-{name}-'))
    log = open(out_dir / f'{name}.server.log', 'w', encoding='utf-8')
    dungeon = Dungeon(data_dir, log)
    path = out_dir / f'{name}.md'
    with open(path, 'w', encoding='utf-8') as out:
        play = Play(dungeon, out)
        try:
            note = set_up(dungeon, args.account_dir, args.model, args.helper_model, args.effort)
            play.write(f'# Playtest: {name}\n\n{scenario.__doc__ or ""}\n\nModel {args.model}, helpers '
                       f'{args.helper_model}. {note}\nData: {data_dir}\n')
            scenario(play)
        except Exception as error:  # noqa: BLE001 - a crashed scenario is a finding, written down
            play.flag(f'Scenario stopped: {type(error).__name__}: {error}')
            play.write(f'```\n{traceback.format_exc()}```')
        finally:
            play.write('## Flags\n')
            play.write('\n'.join(f'- {p}' for p in play.problems) or '- none')
            dungeon.stop()
            log.close()
    return path, play.problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--account-dir', default='', help='Claude Code account folder (CLAUDE_CONFIG_DIR)')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--helper-model', default='haiku', help='for the Referee and Continuity jobs')
    parser.add_argument('--effort', default=None)
    parser.add_argument('--only', default='', help='comma-separated scenario names')
    parser.add_argument('--out', default='playtests')
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    chosen = [n for n in args.only.split(',') if n] or list(SCENARIOS)
    summary = []
    for name in chosen:
        path, problems = run(name, SCENARIOS[name], args, out_dir)
        summary.append((name, path, problems))
        print(f'{name}: {len(problems)} flags -> {path}', flush=True)
    for name, _, problems in summary:
        for problem in problems:
            print(f'  [{name}] {problem}')


if __name__ == '__main__':
    main()
