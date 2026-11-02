"""Makes the art for each world's Life Cards (dungeon/life/cards.py) with the OpenAI Images API, in the world's
backdrop style (scripts/art/backdrops.py), so a drawn card shows a picture in the story (dungeon/happenings.py shown).

Every card in life/decks/<world>.json gets one, deck cards and d100 table rows alike, plus the world's card back
(`back`), which stands in for a card with no picture and for a veiled one. The prompt is the card's title and what
the character sees, with its {placeholders} put in plain words. A picture is written to the world package's
assets/cards/<id>.webp at 512x768; the full-size PNGs are kept in Program/.tools/cards-raw. Pictures already there are
skipped, so the run can be stopped and started again; delete one to have it made again.

The key is read from CHATGPT_API_KEY or OPENAI_API_KEY and never printed. Requests are spaced to at most --per-hour,
and stop on the same errors backdrops.py stops on; a single refused card is reported and skipped (it shows the back).

    python scripts/art/cards.py                         # every world
    python scripts/art/cards.py --world babel           # one world
    python scripts/art/cards.py --only bad-water back   # some cards
    python scripts/art/cards.py --list                  # what would be made, nothing sent
"""
import argparse
import asyncio
import io
import sys
import time

from backdrops import KEYS, OPENAI, PACKAGES, ROOT, STOPPING, STREAK, api_key, manifest

from dungeon.images.adapters.base import AdapterError, ImageRequest
from dungeon.images.adapters.hosted import HostedAdapter
from dungeon.life import cards

RAW = ROOT / '.tools' / 'cards-raw'
SIZE = (1024, 1536)
SAVED = (512, 768)
QUALITY = 80
AVOID = 'text, lettering, words, numbers, watermark, logo, card border, frame'
# How a card's placeholders read in a picture: whoever the story fills in is someone, not a name.
PLAIN = {'pc': 'a traveller', 'npc': 'a local', 'bond': 'a close companion', 'them': 'someone the traveller knows',
         'faction': 'a powerful faction', 'town': 'the town'}
CARD = ('The illustration for a tall playing card called "{title}". {seen} Show it as one striking moment, close '
        'enough to read the faces and hands. No text, lettering or card frame in the picture.')
# Only for a card that needs some intensity: asking a photographic style to "imply sex" gets an ordinary card refused.
GRIM = ' Imply violence, cruelty and sex rather than showing them outright.'
# A scene of its own for a card whose own words the image model refuses: the same moment, told by what is around it.
SCENES = {
    ('babel', 'marked-at-the-ford'): 'A crowded stone bridge over a ford; in the middle of the crowd a woman in plain '
                                     'grey walks behind a guard who holds a rope, a dark sigil inked on her neck. '
                                     'Everyone around them looks the other way.',
    ('havenbrooke', 'drink-spiked'): 'A college house party late at night: red plastic cups on a sticky kitchen counter, '
                                     'one cup left apart with a faint residue at the bottom, the party blurred and '
                                     'uneasy behind it, the back door left open onto the dark.',
    ('havenbrooke', 'deer-strike'): 'A dented car hood on a dark rural road at night, one headlight cracked, its beam '
                                    'on the empty wet asphalt and the autumn trees, hazard lights blinking.',
    ('havenbrooke', 'beat-hookup'): 'Nine in the morning in a college dorm hallway: a pair of high heels dropped by a '
                                    'half-open door, a party wristband and a borrowed men\'s jacket on the floor beside '
                                    'them, bright morning sun through the window.',
}
BACK = ('The back of a tall playing card for this world: a symmetrical ornamental pattern around one central emblem '
        'that suits the world, rich but quiet, no text or lettering.')


def style(world: str) -> str:
    return manifest(world)['backdrop_style'].removesuffix(', wide establishing shot')


def plain(text: str) -> str:
    for key, words in PLAIN.items():
        text = text.replace('{' + key + '}', words)
    return text


def jobs(world: str, only: set[str]) -> list[dict]:
    """Every card picture the world's deck asks for that is not made yet, the back first."""
    folder, look = PACKAGES / world / 'assets' / 'cards', style(world)
    wanted = [('back', f'{look}. {BACK}')] + [
        (item['id'], f"{look}. {CARD.format(title=plain(item['title']), seen=SCENES[world, item['id']])}"
         if (world, item['id']) in SCENES else
         f"{look}. {CARD.format(title=plain(item['title']), seen=plain(item['seen']))}"
         + (GRIM if item['intensity'] else ''))
        for item in cards.cards(world)]
    return [{'world': world, 'id': key, 'out': folder / f'{key}.webp', 'prompt': prompt}
            for key, prompt in wanted if (not only or key in only) and not (folder / f'{key}.webp').exists()]


def save(png: bytes, job: dict):
    from PIL import Image
    picture = Image.open(io.BytesIO(png)).convert('RGB').resize(SAVED, Image.Resampling.LANCZOS)
    job['out'].parent.mkdir(parents=True, exist_ok=True)
    picture.save(job['out'], 'WEBP', quality=QUALITY, method=6)


async def make(adapter, job: dict, model: str) -> bytes:
    raw = RAW / job['world']
    raw.mkdir(parents=True, exist_ok=True)
    request = ImageRequest(job_id=job['id'], prompt=job['prompt'], negative=AVOID, seed=0, width=SIZE[0],
                           height=SIZE[1], backend={'kind': 'hosted', 'provider': 'openai'},
                           config={'base_url': OPENAI, 'model': model}, key=api_key(), raw_dir=raw, reference=None)
    data = (await adapter.generate(request)).data
    (raw / f"{job['id']}.png").write_bytes(data)
    return data


async def run(args) -> int:
    chosen = args.world or [world for world in cards.worlds() if (PACKAGES / world).is_dir()]
    queue = [job for world in chosen for job in jobs(world, set(args.only or ()))]
    print(f'{len(queue)} card picture(s) to make in {", ".join(chosen)}, at most {args.per_hour} an hour.')
    if args.list:
        for job in queue:
            print(f"  {job['world']}/{job['id']}: {job['prompt'][:110]}...")
        return 0
    if not api_key():
        print(f'Set {" or ".join(KEYS)} to an OpenAI API key first.')
        return 1
    adapter, gap, last, made, skipped, streak = HostedAdapter(), 3600 / args.per_hour, 0.0, 0, [], []
    for index, job in enumerate(queue, 1):
        if (wait := last + gap - time.monotonic()) > 0:
            await asyncio.sleep(wait)
        last = time.monotonic()
        print(f"[{index}/{len(queue)}] {job['world']}/{job['id']}")
        try:
            save(await make(adapter, job, args.model), job)
        except AdapterError as error:
            print(f'  failed ({error.code}): {error.message}')
            if error.code in STOPPING:
                print('Stopped. Fix that, then run this again; finished pictures are kept.')
                return 1
            skipped.append(f"{job['world']}/{job['id']} ({error.code})")
            streak = [*streak, error.message] if streak and streak[-1] == error.message else [error.message]
            if len(streak) >= STREAK:
                print(f'Stopped: the last {STREAK} pictures all failed the same way:\n  {error.message}')
                return 1
            continue
        streak = []
        made += 1
    print(f'Done: {made} made.' + (f' Not made: {", ".join(skipped)}.' if skipped else ''))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Make the art for the worlds' Life Cards with OpenAI images.")
    parser.add_argument('--world', action='append', choices=cards.worlds(), help='only this world (repeatable)')
    parser.add_argument('--only', nargs='+', metavar='ID', help='only these card ids (`back` for the card back)')
    parser.add_argument('--per-hour', type=float, default=120, help='most pictures to ask for in an hour (default 120)')
    parser.add_argument('--model', default='gpt-image-1.5', help='OpenAI image model')
    parser.add_argument('--list', action='store_true', help='show what would be made and send nothing')
    args = parser.parse_args()
    if args.per_hour <= 0:
        parser.error('--per-hour must be more than 0')
    return asyncio.run(run(args))


if __name__ == '__main__':
    sys.exit(main())
