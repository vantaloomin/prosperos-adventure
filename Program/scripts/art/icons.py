"""Makes the worlds' faction emblems and item icons (dungeon/icons.py) with the OpenAI Images API, the same way
scripts/art/backdrops.py --backend openai makes backdrops, with the key in CHATGPT_API_KEY or OPENAI_API_KEY (read
from the environment only, never printed).

Each world lists them in its package's art file, dungeon/world/packages/<world>/engine/art/<world>.json: `emblems`
(one per faction id, in the world's `emblem_style`) and `icons` (one per item id, or for several ids in `items`, or a
whole `category` of items, in the world's `icon_style`). They are made on a transparent background and written to
the package's assets/emblems/<id>.webp and assets/icons/<id>.webp at 256x256. The PNGs the API sends are kept in
Program/.tools/icons-raw. Images already there are skipped, so the run can be stopped and started again; delete one
to have it made again.

    python scripts/art/icons.py                       # every world, emblems and icons
    python scripts/art/icons.py --world babel --kind emblems
    python scripts/art/icons.py --only knife rope     # some ids
    python scripts/art/icons.py --list                # what would be made, nothing sent
"""
import argparse
import asyncio
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backdrops import KEYS, OPENAI, PACKAGES, ROOT, STOPPING, STREAK, api_key, manifest, worlds  # noqa: E402

from dungeon.images.adapters.base import AdapterError, ImageRequest  # noqa: E402
from dungeon.images.adapters.hosted import HostedAdapter  # noqa: E402

RAW = ROOT / '.tools' / 'icons-raw'
SIZE = 1024
SAVED = 256
QUALITY = 85
KINDS = {'emblems': 'emblem', 'icons': 'icon'}


def jobs(world: str, kinds: list[str], only: set[str]) -> list[dict]:
    data, found = manifest(world), []
    for kind in kinds:
        style, avoid = data.get(f'{KINDS[kind]}_style', ''), data.get(f'{KINDS[kind]}_avoid', '')
        for entry in data.get(kind, []):
            out = PACKAGES / world / 'assets' / kind / f"{entry['id']}.webp"
            if out.exists() or (only and entry['id'] not in only):
                continue
            found.append({'world': world, 'kind': kind, 'id': entry['id'], 'out': out, 'avoid': avoid,
                          'prompt': f"{style}. {entry['prompt']}"})
    return found


def save(png: bytes, out: Path):
    from PIL import Image
    picture = Image.open(io.BytesIO(png)).convert('RGBA').resize((SAVED, SAVED), Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    picture.save(out, 'WEBP', quality=QUALITY, method=6)


async def make(adapter, job: dict, args) -> bytes:
    raw = RAW / job['world'] / job['kind']
    raw.mkdir(parents=True, exist_ok=True)
    config = {'base_url': OPENAI, 'model': args.model, 'background': 'transparent', 'quality': args.quality}
    request = ImageRequest(job_id=job['id'], prompt=job['prompt'], negative=job['avoid'], seed=0, width=SIZE,
                           height=SIZE, backend={'kind': 'hosted', 'provider': 'openai'}, config=config,
                           key=api_key(), raw_dir=raw)
    data = (await adapter.generate(request)).data
    (raw / f"{job['id']}.png").write_bytes(data)
    return data


async def run(args) -> int:
    chosen, kinds = args.world or worlds(), args.kind or list(KINDS)
    queue = [job for world in chosen for job in jobs(world, kinds, set(args.only or ()))]
    print(f'{len(queue)} image(s) to make in {", ".join(chosen)}, at most {args.per_hour} an hour.')
    if args.list:
        for job in queue:
            print(f"  {job['world']}/{job['kind']}/{job['id']}: {job['prompt'][:110]}...")
        return 0
    if not api_key():
        print(f'Set {" or ".join(KEYS)} to an OpenAI API key first.')
        return 1
    adapter = HostedAdapter()
    gap, last, made, skipped, streak = 3600 / args.per_hour, 0.0, 0, [], []
    for index, job in enumerate(queue, 1):
        if (wait := last + gap - time.monotonic()) > 0:
            await asyncio.sleep(wait)
        last = time.monotonic()
        print(f"[{index}/{len(queue)}] {job['world']}/{job['kind']}/{job['id']}", flush=True)
        try:
            save(await make(adapter, job, args), job['out'])
        except AdapterError as error:
            print(f'  failed ({error.code}): {error.message}', flush=True)
            if error.code in STOPPING:
                print('Stopped. Fix that, then run this again; finished images are kept.')
                return 1
            skipped.append(f"{job['world']}/{job['id']} ({error.code})")
            streak = [*streak, error.message] if streak and streak[-1] == error.message else [error.message]
            if len(streak) >= STREAK:
                print(f'Stopped: the last {STREAK} images all failed the same way:\n  {error.message}')
                return 1
            continue
        streak = []
        made += 1
    print(f'Done: {made} made.' + (f' Not made: {", ".join(skipped)}.' if skipped else ''))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Make the faction emblems and item icons with the OpenAI API.')
    parser.add_argument('--world', action='append', choices=worlds(), help='only this world (repeatable)')
    parser.add_argument('--kind', action='append', choices=list(KINDS), help='only emblems or only icons')
    parser.add_argument('--only', nargs='+', metavar='ID', help='only these faction or icon ids')
    parser.add_argument('--per-hour', type=float, default=240, help='most images to ask for in an hour (default 240)')
    parser.add_argument('--model', default='gpt-image-1.5', help='OpenAI image model')
    parser.add_argument('--quality', default='medium', choices=('low', 'medium', 'high', 'auto'))
    parser.add_argument('--list', action='store_true', help='show what would be made and send nothing')
    args = parser.parse_args()
    if args.per_hour <= 0:
        parser.error('--per-hour must be more than 0')
    return asyncio.run(run(args))


if __name__ == '__main__':
    sys.exit(main())
