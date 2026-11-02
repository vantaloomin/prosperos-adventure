"""Makes the worlds' default NPC portraits (dungeon/art.py stock_portrait) with ChatGPT image generation, the same way
scripts/art/backdrops.py makes the backdrops: through the app's Codex adapter under your `codex login`, or with
`--backend openai` through the OpenAI Images API (key in CHATGPT_API_KEY or OPENAI_API_KEY, read from the environment
only and never printed).

Each world lists its portraits in its package, dungeon/world/packages/<world>/engine/art/<world>-portraits.json, with
a prompt for each and the world's style (`portrait_style`): painterly for Vallarith and BABEL, photographic for
Havenbrooke. An image is made at 1024x1536, cut to 3:4 (the stage's portrait shape, keeping the head) and written to
the package's assets/portraits/<id>.webp at 600x800. The full-size PNGs are kept in Program/.tools/portraits-raw.
Images already there are skipped, so the run can be stopped and started again; delete one to have it made again.

    python scripts/art/portraits.py                      # every world
    python scripts/art/portraits.py --world babel        # one world
    python scripts/art/portraits.py --only smith-man     # some portraits
    python scripts/art/portraits.py --list               # what would be made, nothing sent
    python scripts/art/portraits.py --backend openai     # through the OpenAI API
"""
import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backdrops import KEYS, OPENAI, PACKAGES, ROOT, STOPPING, STREAK, api_key  # noqa: E402

from dungeon.images.adapters.base import AdapterError, ImageRequest  # noqa: E402
from dungeon.images.adapters.codex import CodexAdapter  # noqa: E402
from dungeon.images.adapters.hosted import HostedAdapter  # noqa: E402

RAW = ROOT / '.tools' / 'portraits-raw'
SIZE = (1024, 1536)
SAVED = (600, 800)
QUALITY = 82
# Of the height cut away to make 3:4, the share taken from the top: little, so the head stays in.
TOP = 0.2


def worlds() -> list[str]:
    return sorted(path.parent.parent.parent.name for path in PACKAGES.glob('*/engine/art/*-portraits.json'))


def manifest(world: str) -> dict:
    return json.loads((PACKAGES / world / 'engine' / 'art' / f'{world}-portraits.json').read_text(encoding='utf-8'))


def jobs(world: str, only: set[str]) -> list[dict]:
    """Every portrait the world's list asks for that is not made yet."""
    data, folder = manifest(world), PACKAGES / world / 'assets' / 'portraits'
    return [{'world': world, 'id': entry['id'], 'out': folder / f"{entry['id']}.webp",
             'prompt': f"{data['portrait_style']}. {entry['prompt']} Only this one person in the picture, an adult.",
             'avoid': data.get('portrait_avoid', '')}
            for entry in data['portraits']
            if not (only and entry['id'] not in only) and not (folder / f"{entry['id']}.webp").exists()]


def save(png: bytes, out: Path):
    from PIL import Image
    picture = Image.open(io.BytesIO(png)).convert('RGB')
    width, height = picture.size
    keep = min(height, round(width * SAVED[1] / SAVED[0]))
    top = round((height - keep) * TOP)
    picture = picture.crop((0, top, width, top + keep)).resize(SAVED, Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    picture.save(out, 'WEBP', quality=QUALITY, method=6)


async def make(adapter, job: dict, args) -> bytes:
    raw = RAW / job['world']
    raw.mkdir(parents=True, exist_ok=True)
    if args.backend == 'openai':
        backend, config, key = {'kind': 'hosted', 'provider': 'openai'}, {'base_url': OPENAI, 'model': args.model}, api_key()
    else:
        backend, config, key = {'kind': 'codex'}, {'cli_path': args.codex or ''}, None
    request = ImageRequest(job_id=job['id'], prompt=job['prompt'], negative=job['avoid'], seed=0, width=SIZE[0],
                           height=SIZE[1], backend=backend, config=config, key=key, raw_dir=raw, reference=None)
    data = (await adapter.generate(request)).data
    if args.backend == 'openai':
        (raw / f"{job['id']}.png").write_bytes(data)
    return data


async def run(args) -> int:
    chosen = args.world or worlds()
    queue = [job for world in chosen for job in jobs(world, set(args.only or ()))]
    print(f'{len(queue)} portrait(s) to make in {", ".join(chosen)}, at most {args.per_hour} an hour.')
    if args.list:
        for job in queue:
            print(f"  {job['world']}/{job['id']}: {job['prompt'][:110]}...")
        return 0
    if args.backend == 'openai' and not api_key():
        print(f'Set {" or ".join(KEYS)} to an OpenAI API key first.')
        return 1
    adapter = HostedAdapter() if args.backend == 'openai' else CodexAdapter()
    gap, last, made, skipped, streak = 3600 / args.per_hour, 0.0, 0, [], []
    for index, job in enumerate(queue, 1):
        if (wait := last + gap - time.monotonic()) > 0:
            print(f'  waiting {wait:.0f}s (throttle)')
            await asyncio.sleep(wait)
        last = time.monotonic()
        print(f"[{index}/{len(queue)}] {job['world']}/{job['id']}")
        try:
            save(await make(adapter, job, args), job['out'])
        except AdapterError as error:
            print(f'  failed ({error.code}): {error.message}')
            if error.code in STOPPING:
                print('Stopped. Fix that, then run this again; finished portraits are kept.')
                return 1
            skipped.append(f"{job['world']}/{job['id']} ({error.code})")
            streak = [*streak, error.message] if streak and streak[-1] == error.message else [error.message]
            if len(streak) >= STREAK:
                print(f'Stopped: the last {STREAK} portraits all failed the same way:\n  {error.message}')
                return 1
            continue
        streak = []
        made += 1
        print(f"  saved {job['out']}")
    print(f'Done: {made} made.' + (f' Not made: {", ".join(skipped)}.' if skipped else ''))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Make the default NPC portraits with ChatGPT images.')
    parser.add_argument('--world', action='append', choices=worlds(), help='only this world (repeatable)')
    parser.add_argument('--only', nargs='+', metavar='ID', help='only these portrait ids')
    parser.add_argument('--per-hour', type=float, default=60, help='most images to ask for in an hour (default 60)')
    parser.add_argument('--backend', choices=('codex', 'openai'), default='codex',
                        help='codex: your ChatGPT sign-in (default); openai: the OpenAI API with CHATGPT_API_KEY')
    parser.add_argument('--model', default='gpt-image-1.5', help='OpenAI image model for --backend openai')
    parser.add_argument('--codex', help='where the Codex CLI is, if it is not on PATH')
    parser.add_argument('--list', action='store_true', help='show what would be made and send nothing')
    args = parser.parse_args()
    if args.per_hour <= 0:
        parser.error('--per-hour must be more than 0')
    return asyncio.run(run(args))


if __name__ == '__main__':
    sys.exit(main())
