"""Makes the key art: the title screen's picture and one for each world, shown on the title screen's world cards
(src/features/story/TitleScreen.tsx). It sends its requests the way scripts/art/backdrops.py does, through the same
Codex adapter or, with `--backend openai`, the OpenAI Images API with the key in CHATGPT_API_KEY or OPENAI_API_KEY
(read from the environment only, never printed).

A world's key art is asked for in its package's art list, engine/art/<world>.json `keyart` (`prompt`, `avoid`), in
the world's `backdrop_style`, and written to the package's assets/keyart.webp; the title's prompt is TITLE below and
its picture public/title.webp. Both are 1536x1024. Pictures already there are skipped; delete one to make it again.

    python scripts/art/keyart.py                        # the title and every world
    python scripts/art/keyart.py --only title babel     # some of them
    python scripts/art/keyart.py --list                 # what would be made, nothing sent
    python scripts/art/keyart.py --backend openai       # through the OpenAI API
"""
import argparse
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backdrops  # noqa: E402

SIZE = (1536, 1024)
QUALITY = 82
AVOID = 'text, lettering, words, title, logo, watermark'
TITLE = ("Dark painterly oil illustration, visible brushwork, candlelight and deep shadow. Key art for a tabletop "
         "roleplaying game called Prospero's Dungeon: a vaulted stone undercroft where a worn stair descends into "
         "darkness; on an old oak table, an open spellbook, a hand-drawn map, a guttering candle and a scatter of "
         "carved bone dice; the candle smoke curls up and opens into three faint visions of other worlds, a ruined "
         "keep on a crag under a storm, a gothic college clock tower in autumn leaves, and an impossibly tall tower "
         "glowing cyan above the clouds. Wondrous, adult and ominous. Open dark space in the left third.")
TITLE_OUT = backdrops.ROOT / 'public' / 'title.webp'


def jobs(only: set[str]) -> list[dict]:
    found = [{'world': 'title', 'id': 'title', 'out': TITLE_OUT, 'prompt': TITLE, 'avoid': AVOID}]
    for world in backdrops.worlds():
        data = backdrops.manifest(world)
        if keyart := data.get('keyart'):
            found.append({'world': world, 'id': f'{world}-keyart', 'out': backdrops.PACKAGES / world / 'assets' / 'keyart.webp',
                          'prompt': f"{data['backdrop_style']}. {keyart['prompt']}", 'avoid': keyart.get('avoid', AVOID)})
    wanted = [job for job in found if not only or job['world'] in only]
    return [job | {'reference': None} for job in wanted if not job['out'].exists()]


def save(png: bytes, out: Path):
    from PIL import Image
    picture = Image.open(io.BytesIO(png)).convert('RGB').resize(SIZE, Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    picture.save(out, 'WEBP', quality=QUALITY, method=6)


async def run(args) -> int:
    queue = jobs(set(args.only or ()))
    print(f'{len(queue)} picture(s) to make.')
    if args.list:
        for job in queue:
            print(f"  {job['world']}: {job['prompt'][:110]}...")
        return 0
    if args.backend == 'openai' and not backdrops.api_key():
        print(f'Set {" or ".join(backdrops.KEYS)} to an OpenAI API key first.')
        return 1
    adapter = backdrops.HostedAdapter() if args.backend == 'openai' else backdrops.CodexAdapter()
    # make() reads the image size from backdrops.SIZE; key art is asked for at the same 1536x1024.
    results = await asyncio.gather(*(backdrops.make(adapter, job, args) for job in queue), return_exceptions=True)
    failed = 0
    for job, result in zip(queue, results):
        if isinstance(result, backdrops.AdapterError):
            failed += 1
            print(f"  {job['world']} failed ({result.code}): {result.message}")
        elif isinstance(result, BaseException):
            raise result
        else:
            save(result, job['out'])
            print(f"  saved {job['out']}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Make the title and world key art with ChatGPT images.')
    parser.add_argument('--only', nargs='+', metavar='NAME', help="only these: 'title' or a world id")
    parser.add_argument('--backend', choices=('codex', 'openai'), default='codex',
                        help='codex: your ChatGPT sign-in (default); openai: the OpenAI API with CHATGPT_API_KEY')
    parser.add_argument('--model', default='gpt-image-1.5', help='OpenAI image model for --backend openai')
    parser.add_argument('--codex', help='where the Codex CLI is, if it is not on PATH')
    parser.add_argument('--list', action='store_true', help='show what would be made and send nothing')
    return asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
