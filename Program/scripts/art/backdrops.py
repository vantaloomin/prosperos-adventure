"""Makes the worlds' default backdrops (dungeon/art.py backdrop) with ChatGPT image generation, through the app's own
Codex adapter (dungeon/images/adapters/codex.py): one image at a time under your `codex login`.

Each world lists its backdrops in its package, dungeon/world/packages/<world>/engine/art/<world>.json, with a prompt
for each and the world's style (`backdrop_style`): painterly for Vallarith and BABEL, photographic for Havenbrooke.
An image is written to the package's assets/backdrops/<id>.webp at 1200x800; an outdoor backdrop also gets
<id>-night.webp, made from the day picture so it shows the same place. The full-size PNGs ChatGPT sends are kept in
Program/.tools/backdrops-raw. Images already there are skipped, so the run can be stopped and started again; delete
one to have it made again.

`--backend openai` sends the same requests to the OpenAI Images API instead (dungeon/images/adapters/hosted.py), with
the key in CHATGPT_API_KEY or OPENAI_API_KEY; a night picture goes through /images/edits with the day one attached.
The key is read from the environment only and never printed.

Requests are spaced to at most --per-hour (60 by default). A sign-in, quota or missing-CLI error stops the run, and
so do STREAK failures in a row for the same reason (a ChatGPT plan without image generation fails every image alike);
a single refused or failed image is reported and skipped.

    python scripts/art/backdrops.py                      # every world
    python scripts/art/backdrops.py --world havenbrooke  # one world
    python scripts/art/backdrops.py --only smithy tavern # some backdrops
    python scripts/art/backdrops.py --list               # what would be made, nothing sent
    python scripts/art/backdrops.py --backend openai     # through the OpenAI API (--model to pick the image model)

Windows/backdrops.bat runs it with the app's Python and Pillow (which the app itself does not need).
"""
import argparse
import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dungeon.images.adapters.base import AdapterError, ImageRequest  # noqa: E402
from dungeon.images.adapters.codex import CodexAdapter  # noqa: E402
from dungeon.images.adapters.hosted import HostedAdapter  # noqa: E402

PACKAGES = ROOT / 'dungeon' / 'world' / 'packages'
RAW = ROOT / '.tools' / 'backdrops-raw'
SIZE = (1536, 1024)
SAVED = (1200, 800)
QUALITY = 80
# Errors after which no later request can succeed until you do something.
STOPPING = {'auth', 'rate_limited', 'unavailable', 'incompatible'}
# Failures in a row for the same reason that stop the run: something is wrong with every request, not one prompt.
STREAK = 3
KEYS = ('CHATGPT_API_KEY', 'OPENAI_API_KEY')
OPENAI = 'https://api.openai.com/v1'
NIGHT = ('The attached picture shows this place by day. Make the same place, from the same viewpoint with the same '
         'composition, at night: moonlight and starlight, warm lamplight or firelight from windows, lanterns or street '
         'lights where the place would have them, deep blue shadows.')


def worlds() -> list[str]:
    return sorted(path.parent.parent.parent.name for path in PACKAGES.glob('*/engine/art/*.json'))


def manifest(world: str) -> dict:
    return json.loads((PACKAGES / world / 'engine' / 'art' / f'{world}.json').read_text(encoding='utf-8'))


def jobs(world: str, only: set[str]) -> list[dict]:
    """Every image the world's list asks for that is not made yet, day before night."""
    data, folder = manifest(world), PACKAGES / world / 'assets' / 'backdrops'
    found = []
    for entry in data['backdrops']:
        if entry.get('from') or (only and entry['id'] not in only):
            continue
        day = folder / f"{entry['id']}.webp"
        prompt = f"{data['backdrop_style']}. {entry['prompt']} No people in the picture."
        if not day.exists():
            found.append({'world': world, 'id': entry['id'], 'out': day, 'prompt': prompt, 'reference': None})
        if entry.get('outdoor') and not (folder / f"{entry['id']}-night.webp").exists():
            found.append({'world': world, 'id': f"{entry['id']}-night", 'out': folder / f"{entry['id']}-night.webp",
                          'prompt': f'{NIGHT} {prompt}', 'reference': day})
    return [job | {'avoid': data.get('backdrop_avoid', '')} for job in found]


def save(png: bytes, out: Path):
    from PIL import Image
    picture = Image.open(io.BytesIO(png)).convert('RGB').resize(SAVED, Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    picture.save(out, 'WEBP', quality=QUALITY, method=6)


def api_key() -> str | None:
    return next((os.environ[name] for name in KEYS if os.environ.get(name)), None)


async def make(adapter, job: dict, args) -> bytes:
    raw = RAW / job['world']
    raw.mkdir(parents=True, exist_ok=True)
    reference = job['reference'].read_bytes() if job['reference'] else None
    if args.backend == 'openai':
        backend, config, key = {'kind': 'hosted', 'provider': 'openai'}, {'base_url': OPENAI, 'model': args.model}, api_key()
    else:
        backend, config, key = {'kind': 'codex'}, {'cli_path': args.codex or ''}, None
    request = ImageRequest(job_id=job['id'], prompt=job['prompt'], negative=job['avoid'], seed=0, width=SIZE[0],
                           height=SIZE[1], backend=backend, config=config, key=key, raw_dir=raw, reference=reference)
    data = (await adapter.generate(request)).data
    if args.backend == 'openai':
        (raw / f"{job['id']}.png").write_bytes(data)
    return data


async def run(args) -> int:
    chosen = args.world or worlds()
    queue = [job for world in chosen for job in jobs(world, set(args.only or ()))]
    print(f'{len(queue)} image(s) to make in {", ".join(chosen)}, at most {args.per_hour} an hour.')
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
        if job['reference'] and not job['reference'].exists():
            skipped.append(f"{job['world']}/{job['id']} (no day picture)")
            continue
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
                print('Stopped. Fix that, then run this again; finished images are kept.')
                return 1
            skipped.append(f"{job['world']}/{job['id']} ({error.code})")
            streak = [*streak, error.message] if streak and streak[-1] == error.message else [error.message]
            if len(streak) >= STREAK:
                print(f'Stopped: the last {STREAK} images all failed the same way:\n  {error.message}\n'
                      'Check that your ChatGPT plan includes image generation in Codex (a Free plan may not), then '
                      'run this again; finished images are kept.')
                return 1
            continue
        streak = []
        made += 1
        print(f"  saved {job['out']}")
    print(f'Done: {made} made.' + (f' Not made: {", ".join(skipped)}.' if skipped else ''))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Make the default location backdrops with ChatGPT images.')
    parser.add_argument('--world', action='append', choices=worlds(), help='only this world (repeatable)')
    parser.add_argument('--only', nargs='+', metavar='ID', help='only these backdrop ids (a night one comes with its day)')
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
